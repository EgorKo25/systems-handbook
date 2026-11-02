package main

import (
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"syscall"
	"testing"
	"time"
)

// No listener or MongoDB: exercise the exact body reader used before InsertOne.
func TestDecodeCreate(t *testing.T) {
	valid := `{"id":"body-test","tenant":"test","title":"Я"}`
	for _, tc := range []struct {
		name string
		body string
		ok   bool
	}{
		{"one-object", valid, true},
		{"whitespace", valid + " \n\t", true},
		{"exactly-4096", valid + strings.Repeat(" ", 4096-len(valid)), true},
		{"4097-bytes", valid + strings.Repeat(" ", 4097-len(valid)), false},
		{"second-object", valid + `{}`, false},
		{"second-value", valid + `0`, false},
		{"malformed-tail", valid + `!`, false},
		{"unknown-field", `{"id":"x","tenant":"test","title":"x","other":1}`, false},
		{"missing-title", `{"id":"x","tenant":"test"}`, false},
		{"empty", "", false},
		{"null", "null", false},
		{"title-200-utf8-bytes", `{"id":"x","tenant":"test","title":"` + strings.Repeat("Я", 100) + `"}`, true},
		{"title-202-utf8-bytes", `{"id":"x","tenant":"test","title":"` + strings.Repeat("Я", 101) + `"}`, false},
	} {
		t.Run(tc.name, func(t *testing.T) {
			r := httptest.NewRequest("POST", "/jobs", strings.NewReader(tc.body))
			defer r.Body.Close()
			_, err := decodeCreate(httptest.NewRecorder(), r)
			if (err == nil) != tc.ok {
				t.Fatalf("ok=%v, got error %v", tc.ok, err)
			}
		})
	}
}

// Only an owned ephemeral loopback listener; no process signal or MongoDB.
func TestShutdownWaitsForHandler(t *testing.T) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	entered := make(chan struct{})
	release := make(chan struct{})
	released := false
	server := &http.Server{Handler: http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		close(entered)
		<-release
		_, _ = io.WriteString(w, "handler completed")
	})}
	defer func() {
		if !released {
			close(release)
		}
		_ = server.Close()
	}()
	signals := make(chan os.Signal, 1)
	done := make(chan error, 1)
	go func() { done <- serveUntilSignal(server, ln, signals) }()
	response := make(chan string, 1)
	client := &http.Client{Timeout: 3 * time.Second}
	defer client.CloseIdleConnections()
	go func() {
		r, err := client.Get("http://" + ln.Addr().String())
		if err != nil {
			response <- "ERROR: " + err.Error()
			return
		}
		defer r.Body.Close()
		b, err := io.ReadAll(r.Body)
		if err != nil {
			response <- "ERROR: " + err.Error()
			return
		}
		response <- string(b)
	}()
	select {
	case <-entered:
	case <-time.After(2 * time.Second):
		t.Fatal("handler did not enter")
	}
	signals <- syscall.SIGTERM
	select {
	case err := <-done:
		t.Fatalf("returned before active handler released: %v", err)
	case <-time.After(100 * time.Millisecond):
	}
	close(release)
	released = true
	select {
	case body := <-response:
		if body != "handler completed" {
			t.Fatal(body)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("response missing")
	}
	select {
	case err := <-done:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(2 * time.Second):
		t.Fatal("shutdown did not drain")
	}
}
