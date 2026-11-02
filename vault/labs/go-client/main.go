// Original bounded example. HTTPS API, no third-party dependency, no secret output.
package main

import (
 "bytes"
 "context"
 "crypto/tls"
 "crypto/x509"
 "encoding/json"
 "errors"
 "flag"
 "fmt"
 "io"
 "net/http"
 "net/url"
 "os"
 "os/signal"
 "strings"
 "syscall"
 "time"
)

type Client struct { http *http.Client; base string; token string }
type Response struct { Data json.RawMessage `json:"data"`; Auth *struct { Renewable bool `json:"renewable"`; LeaseDuration int `json:"lease_duration"` } `json:"auth"` }
func (v *Client) call(ctx context.Context, method, path string, body []byte) (*Response,error) {
 req,err:=http.NewRequestWithContext(ctx,method,v.base+"/v1/"+path,bytes.NewReader(body)); if err!=nil{return nil,err}
 req.Header.Set("X-Vault-Token",v.token); req.Header.Set("Content-Type","application/json")
 r,err:=v.http.Do(req); if err!=nil{return nil,errors.New("Vault transport failed")}; defer r.Body.Close()
 if r.StatusCode!=http.StatusOK { io.Copy(io.Discard,io.LimitReader(r.Body,65536)); return nil,fmt.Errorf("Vault HTTP %d",r.StatusCode) }
 var out Response
 if err=json.NewDecoder(io.LimitReader(r.Body,1<<20)).Decode(&out); err!=nil{return nil,errors.New("Vault response decode failed")}
 return &out,nil
}
func run(ctx context.Context, base,caFile,tokenFile string,watch bool) error {
 u,err:=url.Parse(base); if err!=nil||u.Scheme!="https"||u.Host==""||u.User!=nil {return errors.New("HTTPS base URL required")}
 ca,err:=os.ReadFile(caFile); if err!=nil{return errors.New("CA file unavailable")}; roots:=x509.NewCertPool(); if !roots.AppendCertsFromPEM(ca){return errors.New("invalid CA PEM")}
 info,err:=os.Stat(tokenFile); if err!=nil||!info.Mode().IsRegular()||info.Mode().Perm()&0077!=0{return errors.New("token must be a private regular file (0600 or stricter)")}
 t,err:=os.ReadFile(tokenFile); if err!=nil{return errors.New("token file unavailable")}
 token:=strings.TrimSpace(string(t)); if token==""{return errors.New("empty token")}
 transport:=&http.Transport{TLSClientConfig:&tls.Config{RootCAs:roots,MinVersion:tls.VersionTLS12},MaxIdleConnsPerHost:2,IdleConnTimeout:30*time.Second}
 defer transport.CloseIdleConnections()
 v:=Client{base:strings.TrimRight(base,"/"),token:token,http:&http.Client{Transport:transport,Timeout:5*time.Second,CheckRedirect:func(*http.Request,[]*http.Request)error{return http.ErrUseLastResponse}}}
 out,err:=v.call(ctx,http.MethodGet,"secret/data/handbook/config",nil); if err!=nil{return err}
 var kv struct{ Metadata struct{Version int `json:"version"`} `json:"metadata"` }
 if json.Unmarshal(out.Data,&kv)!=nil||kv.Metadata.Version==0{return errors.New("invalid KVv2 envelope")}
 fmt.Printf("KVv2 response accepted; version=%d; secret body withheld\n",kv.Metadata.Version)
 if !watch{return nil}
 for {
  renewed,err:=v.call(ctx,http.MethodPost,"auth/token/renew-self",[]byte(`{"increment":"30s"}`))
  if err!=nil{return err}; if renewed.Auth==nil||!renewed.Auth.Renewable||renewed.Auth.LeaseDuration<2{return errors.New("token cannot be renewed; obtain new identity")}
  wait:=time.Duration(renewed.Auth.LeaseDuration)*time.Second/2
  timer:=time.NewTimer(wait)
  select{case <-ctx.Done(): timer.Stop(); return ctx.Err();case <-timer.C:}
 }
}
func main(){
 addr:=flag.String("address","https://127.0.0.1:18200","Vault HTTPS endpoint")
 ca:=flag.String("ca","","PEM CA file")
 token:=flag.String("token-file","","private application token file")
 watch:=flag.Bool("watch",false,"renew the token until signal or terminal error")
 flag.Parse()
 ctx,cancel:=signal.NotifyContext(context.Background(),os.Interrupt,syscall.SIGTERM);defer cancel()
 if err:=run(ctx,*addr,*ca,*token,*watch);err!=nil&&!errors.Is(err,context.Canceled){fmt.Fprintln(os.Stderr,err);os.Exit(1)}
}
