package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"
	"time"
)

type application struct {
	ready    atomic.Bool
	requests atomic.Uint64
	message  string
}

func newApplication(message string) *application {
	a := &application{message: message}
	a.ready.Store(true)
	return a
}
func (a *application) routes() http.Handler {
	m := http.NewServeMux()
	m.HandleFunc("GET /livez", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusOK); fmt.Fprintln(w, "alive") })
	m.HandleFunc("GET /readyz", func(w http.ResponseWriter, r *http.Request) {
		if !a.ready.Load() {
			http.Error(w, "draining", http.StatusServiceUnavailable)
			return
		}
		fmt.Fprintln(w, "ready")
	})
	m.HandleFunc("GET /api/hello", func(w http.ResponseWriter, r *http.Request) {
		a.requests.Add(1)
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{"service": "ledger-api", "message": a.message})
	})
	m.HandleFunc("GET /metrics", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4")
		fmt.Fprintf(w, "# TYPE ledger_requests_total counter\nledger_requests_total %d\n", a.requests.Load())
	})
	return m
}
func serve(ctx context.Context, s *http.Server, listener net.Listener, beforeShutdown func()) error {
	errs := make(chan error, 1)
	go func() { errs <- s.Serve(listener) }()
	select {
	case err := <-errs:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	case <-ctx.Done():
		beforeShutdown()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
		defer cancel()
		if err := s.Shutdown(shutdownCtx); err != nil {
			return err
		}
		err := <-errs
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	}
}
func run(ctx context.Context, addr, message string) error {
	a := newApplication(message)
	s := &http.Server{Addr: addr, Handler: a.routes(), ReadHeaderTimeout: 3 * time.Second, IdleTimeout: 30 * time.Second}
	listener, err := net.Listen("tcp", addr)
	if err != nil {
		return err
	}
	return serve(ctx, s, listener, func() { a.ready.Store(false) })
}
func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	addr := os.Getenv("LISTEN_ADDR")
	if addr == "" {
		addr = ":8080"
	}
	message := os.Getenv("MESSAGE")
	if message == "" {
		message = "hello from handbook"
	}
	if err := run(ctx, addr, message); err != nil {
		log.Printf("server stopped: %v", err)
		os.Exit(1)
	}
}
