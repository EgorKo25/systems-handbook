package main

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestPersistenceAcrossReopenAndConcurrentRequests(t *testing.T) {
	path := filepath.Join(t.TempDir(), "count.txt")
	s, err := openStore(path)
	if err != nil {
		t.Fatal(err)
	}
	h := handler(config{Message: "saved"}, s)
	var group sync.WaitGroup
	for i := 0; i < 20; i++ {
		group.Add(1)
		go func() {
			defer group.Done()
			r := httptest.NewRequest("POST", "/counter", nil)
			w := httptest.NewRecorder()
			h.ServeHTTP(w, r)
			if w.Code != 200 {
				t.Errorf("POST status %d", w.Code)
			}
		}()
	}
	group.Wait()
	reopened, err := openStore(path)
	if err != nil {
		t.Fatal(err)
	}
	if reopened.value() != 20 {
		t.Fatalf("count=%d", reopened.value())
	}
	w := httptest.NewRecorder()
	handler(config{Message: "after restart"}, reopened).ServeHTTP(w, httptest.NewRequest("GET", "/counter", nil))
	var result struct {
		Count uint64 `json:"count"`
	}
	if err := json.Unmarshal(w.Body.Bytes(), &result); err != nil {
		t.Fatal(err)
	}
	if result.Count != 20 {
		t.Fatalf("GET=%s", w.Body.String())
	}
}

func TestRejectMalformedStoredDataAndConfiguration(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "count.txt")
	if err := os.WriteFile(path, []byte("not a number"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := openStore(path); err == nil {
		t.Fatal("malformed data accepted")
	}
	cfg := filepath.Join(dir, "config.json")
	cases := []string{
		`{"listen":"127.0.0.1:8080","data_file":"relative"}`,
		`{"listen":"broken","data_file":"/tmp/count"}`,
		`{"listen":"127.0.0.1:8080","data_file":"/tmp/count","unknown":1}`,
		`{"listen":"127.0.0.1:8080","data_file":"/tmp/count"} {}`,
	}
	for _, text := range cases {
		if err := os.WriteFile(cfg, []byte(text), 0600); err != nil {
			t.Fatal(err)
		}
		if _, err := loadConfig(cfg); err == nil {
			t.Fatalf("accepted %s", text)
		}
	}
	valid := `{"listen":"127.0.0.1:8080","data_file":"` + strings.ReplaceAll(filepath.Join(dir, "missing-data"), `\`, `\\`) + `","message":"test"}`
	if err := os.WriteFile(cfg, []byte(valid), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := loadConfig(cfg); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(dir, "missing-data")); !os.IsNotExist(err) {
		t.Fatal("validation touched data")
	}
}

func TestShutdownWaitsForActivePersistentRequest(t *testing.T) {
	s, err := openStore(filepath.Join(t.TempDir(), "count.txt"))
	if err != nil {
		t.Fatal(err)
	}
	started, release, shutdownStarted := make(chan struct{}), make(chan struct{}), make(chan struct{})
	server := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		close(started)
		<-release
		handler(config{Message: "drained"}, s).ServeHTTP(w, r)
	})}
	server.RegisterOnShutdown(func() { close(shutdownStarted) })
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	finished := make(chan error, 1)
	go func() { finished <- serveUntilStopped(ctx, server, listener, 2*time.Second) }()
	requestResult := make(chan error, 1)
	go func() {
		client := &http.Client{Timeout: 3 * time.Second}
		resp, err := client.Post("http://"+listener.Addr().String()+"/counter", "", nil)
		if err == nil {
			_, err = io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
			if resp.StatusCode != http.StatusOK {
				err = errors.New("request failed")
			}
		}
		requestResult <- err
	}()
	select {
	case <-started:
	case <-time.After(3 * time.Second):
		t.Fatal("handler did not start")
	}
	cancel()
	select {
	case <-shutdownStarted:
	case <-time.After(3 * time.Second):
		t.Fatal("shutdown did not begin")
	}
	select {
	case err := <-finished:
		close(release)
		t.Fatalf("returned before active request completed: %v", err)
	case <-time.After(50 * time.Millisecond):
	}
	close(release)
	if err := <-requestResult; err != nil {
		t.Fatal(err)
	}
	if err := <-finished; err != nil {
		t.Fatal(err)
	}
	reopened, err := openStore(s.path)
	if err != nil || reopened.value() != 1 {
		t.Fatalf("persisted request after drain: %v", err)
	}
}

func TestShutdownDeadlineIsAnExplicitFailure(t *testing.T) {
	started, release := make(chan struct{}), make(chan struct{})
	server := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { close(started); <-release })}
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	defer close(release)
	finished := make(chan error, 1)
	go func() { finished <- serveUntilStopped(ctx, server, listener, 50*time.Millisecond) }()
	requestDone := make(chan struct{})
	go func() {
		defer close(requestDone)
		resp, _ := (&http.Client{Timeout: 3 * time.Second}).Get("http://" + listener.Addr().String())
		if resp != nil {
			resp.Body.Close()
		}
	}()
	select {
	case <-started:
	case <-time.After(3 * time.Second):
		t.Fatal("handler did not start")
	}
	cancel()
	select {
	case err := <-finished:
		if !errors.Is(err, context.DeadlineExceeded) {
			t.Fatalf("got %v", err)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("shutdown ignored its limit")
	}
	<-requestDone
}
