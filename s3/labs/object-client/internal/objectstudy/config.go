package objectstudy

import (
	"bytes"
	"crypto/x509"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"syscall"
	"time"
	"unicode/utf8"
)

type Target struct {
	Backend         string
	Endpoint        string
	Region          string
	Bucket          string
	Addressing      string
	Profile         string
	CredentialsFile string
	CAFile          string
}

type Profile struct {
	AccessKeyID     string
	SecretAccessKey string
	SessionToken    string
	ExpiresAt       time.Time
	Temporary       bool
}

type Resolved struct {
	Target  Target
	Profile Profile
	Roots   *x509.CertPool
}

func configError() error {
	return errors.New("invalid object-study configuration or profile")
}

func openRegularForRead(path string) (*os.File, os.FileInfo, error) {
	fd, err := syscall.Open(path,
		syscall.O_RDONLY|syscall.O_CLOEXEC|
			syscall.O_NONBLOCK|syscall.O_NOCTTY, 0)
	if err != nil {
		return nil, nil, configError()
	}
	f := os.NewFile(uintptr(fd), path)
	if f == nil {
		syscall.Close(fd)
		return nil, nil, configError()
	}
	info, err := f.Stat()
	if err != nil || !info.Mode().IsRegular() {
		f.Close()
		return nil, nil, configError()
	}
	return f, info, nil
}

func readDocument(path string, limit int64, private bool) ([]byte, error) {
	f, info, err := openRegularForRead(path)
	if err != nil {
		return nil, err
	}
	if private {
		st, ok := info.Sys().(*syscall.Stat_t)
		if !ok || int(st.Uid) != os.Geteuid() ||
			info.Mode().Perm()&0077 != 0 {
			f.Close()
			return nil, configError()
		}
	}
	data, readErr := io.ReadAll(io.LimitReader(f, limit+1))
	closeErr := f.Close()
	if readErr != nil || closeErr != nil ||
		int64(len(data)) > limit || !utf8.Valid(data) {
		return nil, configError()
	}
	return data, nil
}

func walkJSON(dec *json.Decoder) error {
	token, err := dec.Token()
	if err != nil {
		return configError()
	}
	delimiter, compound := token.(json.Delim)
	if !compound {
		return nil
	}
	switch delimiter {
	case '{':
		seen := map[string]bool{}
		for dec.More() {
			token, err := dec.Token()
			if err != nil {
				return configError()
			}
			key, ok := token.(string)
			if !ok || seen[key] {
				return configError()
			}
			seen[key] = true
			if err := walkJSON(dec); err != nil {
				return err
			}
		}
		token, err = dec.Token()
		if err != nil || token != json.Delim('}') {
			return configError()
		}
	case '[':
		for dec.More() {
			if err := walkJSON(dec); err != nil {
				return err
			}
		}
		token, err = dec.Token()
		if err != nil || token != json.Delim(']') {
			return configError()
		}
	default:
		return configError()
	}
	return nil
}

func checkDocument(data []byte) error {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.UseNumber()
	if err := walkJSON(dec); err != nil {
		return err
	}
	if _, err := dec.Token(); err != io.EOF {
		return configError()
	}
	return nil
}

func object(data []byte) (map[string]json.RawMessage, error) {
	data = bytes.TrimSpace(data)
	if len(data) == 0 || data[0] != '{' {
		return nil, configError()
	}
	var result map[string]json.RawMessage
	if err := json.Unmarshal(data, &result); err != nil || result == nil {
		return nil, configError()
	}
	return result, nil
}

func exactKeys(m map[string]json.RawMessage,
	required, optional []string) error {
	allowed := map[string]bool{}
	for _, name := range required {
		allowed[name] = true
		if _, ok := m[name]; !ok {
			return configError()
		}
	}
	for _, name := range optional {
		allowed[name] = true
	}
	for name := range m {
		if !allowed[name] {
			return configError()
		}
	}
	return nil
}

func text(m map[string]json.RawMessage, key string) (string, error) {
	raw, ok := m[key]
	raw = bytes.TrimSpace(raw)
	if !ok || len(raw) == 0 || raw[0] != '"' {
		return "", configError()
	}
	var result string
	if err := json.Unmarshal(raw, &result); err != nil ||
		strings.ContainsRune(result, utf8.RuneError) {
		return "", configError()
	}
	return result, nil
}

func documentMap(data []byte, name string) (
	map[string]json.RawMessage, error) {
	if err := checkDocument(data); err != nil {
		return nil, err
	}
	root, err := object(data)
	if err != nil {
		return nil, err
	}
	if err := exactKeys(root, []string{"schema_version", name}, nil); err != nil {
		return nil, err
	}
	var version int
	if err := json.Unmarshal(root["schema_version"], &version); err != nil ||
		version != 1 {
		return nil, configError()
	}
	entries, err := object(root[name])
	if err != nil {
		return nil, err
	}
	for id := range entries {
		if !validID(id) {
			return nil, configError()
		}
	}
	return entries, nil
}

func relativeTo(base, name string) string {
	if filepath.IsAbs(name) {
		return filepath.Clean(name)
	}
	return filepath.Join(base, name)
}

var bucketSyntax = regexp.MustCompile(
	"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
var regionSyntax = regexp.MustCompile("^[a-z0-9-]{1,128}$")

func validateTarget(t Target) error {
	if t.Backend != "aws" && t.Backend != "minio" &&
		t.Backend != "ceph-rgw" {
		return configError()
	}
	if !regionSyntax.MatchString(t.Region) ||
		!bucketSyntax.MatchString(t.Bucket) ||
		strings.Contains(t.Bucket, "..") ||
		net.ParseIP(t.Bucket) != nil {
		return configError()
	}
	if t.Addressing != "path" && t.Addressing != "virtual" {
		return configError()
	}
	if !validID(t.Profile) || t.CredentialsFile == "" {
		return configError()
	}
	if t.Endpoint == "" {
		if t.Backend != "aws" {
			return configError()
		}
		return nil
	}
	endpoint, err := url.Parse(t.Endpoint)
	if err != nil || endpoint.Hostname() == "" || endpoint.User != nil ||
		endpoint.RawQuery != "" || endpoint.ForceQuery ||
		endpoint.Fragment != "" || strings.Contains(t.Endpoint, "#") ||
		endpoint.Opaque != "" ||
		endpoint.Path != "" && endpoint.Path != "/" {
		return configError()
	}
	if endpoint.Scheme != "http" && endpoint.Scheme != "https" {
		return configError()
	}
	// An absent port is allowed. An explicitly empty port is not.
	if strings.HasSuffix(endpoint.Host, ":") {
		return configError()
	}
	if strings.Contains(endpoint.Hostname(), ":") &&
		!strings.HasPrefix(endpoint.Host, "[") {
		return configError()
	}
	if port := endpoint.Port(); port != "" {
		for _, c := range []byte(port) {
			if c < '0' || c > '9' {
				return configError()
			}
		}
		number, err := strconv.Atoi(port)
		if err != nil || number < 1 || number > 65535 {
			return configError()
		}
	}
	ip := net.ParseIP(endpoint.Hostname())
	if ip != nil && t.Addressing != "path" {
		return configError()
	}
	if endpoint.Scheme == "http" &&
		(ip == nil || !ip.IsLoopback() || t.CAFile != "") {
		return configError()
	}
	return nil
}

func LoadTarget(configFile, id string) (Target, error) {
	if runtime.GOOS != "linux" || !validID(id) {
		return Target{}, configError()
	}
	absolute, err := filepath.Abs(configFile)
	if err != nil {
		return Target{}, configError()
	}
	data, err := readDocument(absolute, 256<<10, false)
	if err != nil {
		return Target{}, err
	}
	entries, err := documentMap(data, "targets")
	if err != nil {
		return Target{}, err
	}
	fields := []string{
		"backend", "endpoint", "region", "bucket", "addressing",
		"profile", "credentials_file", "ca_file",
	}
	decoded := map[string]Target{}
	for name, raw := range entries {
		m, err := object(raw)
		if err != nil || exactKeys(m, fields, nil) != nil {
			return Target{}, configError()
		}
		values := make([]string, len(fields))
		for i, field := range fields {
			values[i], err = text(m, field)
			if err != nil {
				return Target{}, err
			}
		}
		decoded[name] = Target{
			values[0], values[1], values[2], values[3],
			values[4], values[5], values[6], values[7],
		}
	}
	target, ok := decoded[id]
	if !ok || validateTarget(target) != nil {
		return Target{}, configError()
	}
	base := filepath.Dir(absolute)
	target.CredentialsFile = relativeTo(base, target.CredentialsFile)
	if target.CAFile != "" {
		target.CAFile = relativeTo(base, target.CAFile)
	}
	return target, nil
}

func printableSecret(value string) bool {
	if value == "" {
		return false
	}
	for _, c := range []byte(value) {
		if c < 33 || c > 126 {
			return false
		}
	}
	return true
}

func LoadProfile(path, id string, now time.Time) (Profile, error) {
	data, err := readDocument(path, 64<<10, true)
	if err != nil {
		return Profile{}, err
	}
	entries, err := documentMap(data, "profiles")
	if err != nil {
		return Profile{}, err
	}
	for _, raw := range entries {
		m, err := object(raw)
		if err != nil ||
			exactKeys(m,
				[]string{"access_key_id", "secret_access_key"},
				[]string{"session_token", "expires_at"}) != nil {
			return Profile{}, configError()
		}
		for key := range m {
			if _, err := text(m, key); err != nil {
				return Profile{}, err
			}
		}
	}
	raw, ok := entries[id]
	if !ok {
		return Profile{}, configError()
	}
	m, err := object(raw)
	if err != nil {
		return Profile{}, err
	}
	access, err := text(m, "access_key_id")
	if err != nil || !printableSecret(access) {
		return Profile{}, configError()
	}
	secret, err := text(m, "secret_access_key")
	if err != nil || !printableSecret(secret) {
		return Profile{}, configError()
	}
	result := Profile{AccessKeyID: access, SecretAccessKey: secret}
	_, hasToken := m["session_token"]
	_, hasExpiry := m["expires_at"]
	if hasToken != hasExpiry {
		return Profile{}, configError()
	}
	if hasToken {
		token, err := text(m, "session_token")
		if err != nil || !printableSecret(token) {
			return Profile{}, configError()
		}
		stamp, err := text(m, "expires_at")
		if err != nil {
			return Profile{}, err
		}
		expiry, err := time.Parse(time.RFC3339, stamp)
		if err != nil || !expiry.After(now) {
			return Profile{}, configError()
		}
		result.SessionToken = token
		result.ExpiresAt = expiry
		result.Temporary = true
	}
	return result, nil
}

func LoadRoots(caFile string) (*x509.CertPool, error) {
	roots, err := x509.SystemCertPool()
	if caFile == "" {
		if err != nil {
			return nil, configError()
		}
		return roots, nil
	}
	if err != nil {
		roots = x509.NewCertPool()
	}
	data, err := readDocument(caFile, 1<<20, false)
	if err != nil || !roots.AppendCertsFromPEM(data) {
		return nil, configError()
	}
	return roots, nil
}
