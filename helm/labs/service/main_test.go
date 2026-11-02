package main

import (
	"context"
	"encoding/json"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"
)

func TestRoutesAndReadiness(t *testing.T) {
	a := newApplication("test")
	h := a.routes()
	for _, path := range []string{"/livez", "/readyz", "/api/hello"} {
		r := httptest.NewRecorder()
		h.ServeHTTP(r, httptest.NewRequest("GET", path, nil))
		if r.Code != 200 {
			t.Fatalf("%s: %d", path, r.Code)
		}
	}
	r := httptest.NewRecorder()
	h.ServeHTTP(r, httptest.NewRequest("GET", "/api/hello", nil))
	var d map[string]string
	if err := json.Unmarshal(r.Body.Bytes(), &d); err != nil {
		t.Fatal(err)
	}
	if d["message"] != "test" {
		t.Fatal(d)
	}
	a.ready.Store(false)
	r = httptest.NewRecorder()
	h.ServeHTTP(r, httptest.NewRequest("GET", "/readyz", nil))
	if r.Code != http.StatusServiceUnavailable {
		t.Fatal(r.Code)
	}
	r = httptest.NewRecorder()
	h.ServeHTTP(r, httptest.NewRequest("GET", "/livez", nil))
	if r.Code != 200 {
		t.Fatal(r.Code)
	}
}
func TestConcurrentCounter(t *testing.T) {
	a := newApplication("x")
	h := a.routes()
	var wg sync.WaitGroup
	for i := 0; i < 100; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/api/hello", nil))
		}()
	}
	wg.Wait()
	r := httptest.NewRecorder()
	h.ServeHTTP(r, httptest.NewRequest("GET", "/metrics", nil))
	if !strings.Contains(r.Body.String(), "ledger_requests_total 100\n") {
		t.Fatal(r.Body.String())
	}
}

func TestGracefulDrainActiveRequest(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	entered, release, draining := make(chan struct{}), make(chan struct{}), make(chan struct{})
	server := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		close(entered)
		<-release
		_, _ = w.Write([]byte("complete"))
	})}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	done := make(chan error, 1)
	go func() { done <- serve(ctx, server, listener, func() { close(draining) }) }()
	response := make(chan string, 1)
	go func() {
		client := &http.Client{Timeout: 3 * time.Second}
		r, e := client.Get("http://" + listener.Addr().String())
		if e != nil {
			response <- "ERROR " + e.Error()
			return
		}
		defer r.Body.Close()
		b, e := io.ReadAll(r.Body)
		if e != nil {
			response <- "ERROR " + e.Error()
			return
		}
		response <- string(b)
	}()
	select {
	case <-entered:
	case <-time.After(3 * time.Second):
		t.Fatal("request did not enter handler")
	}
	cancel()
	select {
	case <-draining:
	case <-time.After(3 * time.Second):
		t.Fatal("shutdown did not start")
	}
	select {
	case e := <-done:
		t.Fatalf("returned before active request finished: %v", e)
	case <-time.After(40 * time.Millisecond):
	}
	close(release)
	select {
	case body := <-response:
		if body != "complete" {
			t.Fatal(body)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("response timeout")
	}
	select {
	case e := <-done:
		if e != nil {
			t.Fatal(e)
		}
	case <-time.After(3 * time.Second):
		t.Fatal("shutdown timeout")
	}
}
