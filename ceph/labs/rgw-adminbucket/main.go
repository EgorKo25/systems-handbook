// Linux-only administrative bootstrap. It never transfers object payloads.
package main

import (
 "bytes"
 "context"
 "crypto/tls"
 "crypto/x509"
 "encoding/json"
 "errors"
 "flag"
 "io"
 "net"
 "net/http"
 "net/url"
 "os"
 "path/filepath"
 "regexp"
 "strings"
 "syscall"
 "time"

 "github.com/aws/aws-sdk-go-v2/aws"
 "github.com/aws/aws-sdk-go-v2/service/s3"
 "github.com/aws/smithy-go"
)

type target struct {
 Backend string `json:"backend"`
 Endpoint string `json:"endpoint"`
 Region string `json:"region"`
 Bucket string `json:"bucket"`
 Addressing string `json:"addressing"`
 Profile string `json:"profile"`
 CredentialsFile string `json:"credentials_file"`
 CAFile string `json:"ca_file"`
}
type targets struct {
 Version int `json:"schema_version"`
 Targets map[string]target `json:"targets"`
}
type profile struct {
 Access string `json:"access_key_id"`
 Secret string `json:"secret_access_key"`
 Token string `json:"session_token,omitempty"`
 Expires string `json:"expires_at,omitempty"`
}
type profiles struct {
 Version int `json:"schema_version"`
 Profiles map[string]profile `json:"profiles"`
}
type receipt struct {
 Command string `json:"command,omitempty"`
 Bucket string `json:"bucket,omitempty"`
 Outcome string `json:"outcome"`
 ServiceCode string `json:"service_code,omitempty"`
}
var bucketRE=regexp.MustCompile(`^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$`)
var regionRE=regexp.MustCompile(`^[A-Za-z0-9_-]{1,64}$`)
var codeRE=regexp.MustCompile(`^[A-Za-z0-9_.-]{1,96}$`)

// The parent directory is trusted and not concurrently changed.
// O_NONBLOCK prevents a FIFO open from waiting before fstat.
// O_NOFOLLOW rejects a final symlink; fstat checks the opened inode.
func readRegular(path string, private bool) ([]byte,error) {
 fd,err:=syscall.Open(path,syscall.O_RDONLY|syscall.O_NONBLOCK|syscall.O_NOFOLLOW|syscall.O_CLOEXEC,0)
 if err!=nil { return nil,err }
 f:=os.NewFile(uintptr(fd),path)
 defer f.Close()
 st,err:=f.Stat()
 if err!=nil { return nil,err }
 raw,ok:=st.Sys().(*syscall.Stat_t)
 if !st.Mode().IsRegular()||!ok||raw.Uid!=uint32(os.Getuid())||st.Mode().Perm()&0022!=0 {
  return nil,errors.New("unsafe input")
 }
 if private && st.Mode().Perm()!=0600 { return nil,errors.New("private mode") }
 b,err:=io.ReadAll(io.LimitReader(f,65537))
 if err!=nil { return nil,err }
 if len(b)>65536 { return nil,errors.New("input too large") }
 return b,nil
}
func decode(b []byte,out any) error {
 d:=json.NewDecoder(bytes.NewReader(b))
 d.DisallowUnknownFields()
 if err:=d.Decode(out);err!=nil { return err }
 var extra any
 if err:=d.Decode(&extra);err!=io.EOF { return errors.New("trailing JSON") }
 return nil
}
func validate(t target) error {
 u,err:=url.Parse(t.Endpoint)
 if err!=nil||u.Scheme!="https"||u.Hostname()==""||u.User!=nil||u.RawQuery!=""||u.ForceQuery||u.Fragment!=""||
  (u.Path!=""&&u.Path!="/")||u.Opaque!="" {
  return errors.New("endpoint")
 }
 if t.Backend!="ceph-rgw"||t.Addressing!="path"||!bucketRE.MatchString(t.Bucket)||
  strings.Contains(t.Bucket,"..")||strings.HasSuffix(t.Bucket,"--x-s3")||
  strings.HasSuffix(t.Bucket,"-s3alias")||strings.HasSuffix(t.Bucket,".mrap")||net.ParseIP(t.Bucket)!=nil||
  !regionRE.MatchString(t.Region)||t.Profile==""||t.CredentialsFile==""||t.CAFile=="" {
  return errors.New("target")
 }
 return nil
}
func emit(r receipt) { _=json.NewEncoder(os.Stdout).Encode(r) }
func run(args []string) int {
 fs:=flag.NewFlagSet("rgw-adminbucket",flag.ContinueOnError)
 fs.SetOutput(io.Discard)
 config:=fs.String("config","","targets JSON")
 id:=fs.String("target","","target id")
 wait:=fs.Duration("timeout",30*time.Second,"operation timeout")
 if err:=fs.Parse(args);err!=nil||*config==""||*id==""||*wait<=0||*wait>15*time.Minute||
  len(fs.Args())!=1||(fs.Arg(0)!="create"&&fs.Arg(0)!="head") {
  emit(receipt{Outcome:"validation_failed"});return 2
 }
 command:=fs.Arg(0)
 cb,err:=readRegular(*config,false)
 var all targets
 if err!=nil||decode(cb,&all)!=nil||all.Version!=1 { emit(receipt{Outcome:"validation_failed"});return 2 }
 t,ok:=all.Targets[*id]
 if !ok||validate(t)!=nil { emit(receipt{Outcome:"validation_failed"});return 2 }
 base,err:=filepath.Abs(filepath.Dir(*config))
 if err!=nil { emit(receipt{Outcome:"validation_failed"});return 2 }
 resolve:=func(p string) string { if filepath.IsAbs(p){return p};return filepath.Join(base,p) }
 pb,err:=readRegular(resolve(t.CredentialsFile),true)
 var ps profiles
 if err!=nil||decode(pb,&ps)!=nil||ps.Version!=1 { emit(receipt{Outcome:"validation_failed"});return 2 }
 p,ok:=ps.Profiles[t.Profile]
 if !ok||p.Access==""||p.Secret==""||(p.Token=="")!=(p.Expires=="") {
  emit(receipt{Outcome:"validation_failed"});return 2
 }
 var expires time.Time
 if p.Expires!="" {
  expires,err=time.Parse(time.RFC3339,p.Expires)
  if err!=nil||!expires.After(time.Now().Add(*wait)) { emit(receipt{Outcome:"validation_failed"});return 2 }
 }
 pem,err:=readRegular(resolve(t.CAFile),false)
 roots:=x509.NewCertPool()
 if err!=nil||!roots.AppendCertsFromPEM(pem) { emit(receipt{Outcome:"validation_failed"});return 2 }
 tr:=&http.Transport{
  DialContext:(&net.Dialer{Timeout:10*time.Second,KeepAlive:30*time.Second}).DialContext,
  TLSClientConfig:&tls.Config{RootCAs:roots,MinVersion:tls.VersionTLS12},
  TLSHandshakeTimeout:10*time.Second,ResponseHeaderTimeout:*wait,
 }
 defer tr.CloseIdleConnections()
 hc:=&http.Client{Transport:tr,CheckRedirect:func(*http.Request,[]*http.Request)error{return http.ErrUseLastResponse}}
 provider:=aws.CredentialsProviderFunc(func(context.Context)(aws.Credentials,error){
  return aws.Credentials{AccessKeyID:p.Access,SecretAccessKey:p.Secret,SessionToken:p.Token,
   CanExpire:!expires.IsZero(),Expires:expires,Source:"explicit-rgw-admin-profile"},nil
 })
 client:=s3.NewFromConfig(aws.Config{Region:t.Region,Credentials:provider,HTTPClient:hc},
  func(o *s3.Options){o.BaseEndpoint=aws.String(t.Endpoint);o.UsePathStyle=true;o.RetryMaxAttempts=1})
 ctx,cancel:=context.WithTimeout(context.Background(),*wait)
 defer cancel()
 if command=="create" {
  // No LocationConstraint: this helper targets the accepted single-zone default placement.
  _,err=client.CreateBucket(ctx,&s3.CreateBucketInput{Bucket:aws.String(t.Bucket)})
 } else {
  _,err=client.HeadBucket(ctx,&s3.HeadBucketInput{Bucket:aws.String(t.Bucket)})
 }
 if err==nil { emit(receipt{Command:command,Bucket:t.Bucket,Outcome:"confirmed_exists"});return 0 }
 outcome:="unconfirmed"
 if command=="create" { outcome="unknown" }
 r:=receipt{Command:command,Bucket:t.Bucket,Outcome:outcome}
 var api smithy.APIError
 if errors.As(err,&api) {
  if codeRE.MatchString(api.ErrorCode()){r.ServiceCode=api.ErrorCode()}else{r.ServiceCode="ServiceError"}
  emit(r);return 3
 }
 emit(r);return 4
}
func main(){os.Exit(run(os.Args[1:]))}
