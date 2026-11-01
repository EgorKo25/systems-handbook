// Original teaching service. A durable single-file counter is not a database.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

var version = "lesson1"

type counter struct {
	mu        sync.Mutex
	dir       string
	value     uint64
	uncertain bool
}

func openCounter(dir string) (*counter, error) {
	info, err := os.Stat(dir)
	if err != nil {
		return nil, err
	}
	if !info.IsDir() {
		return nil, errors.New("counter path is not a directory")
	}
	c := &counter{dir: dir}
	data, err := os.ReadFile(filepath.Join(dir, "counter"))
	if errors.Is(err, os.ErrNotExist) {
		return c, nil
	}
	if err != nil {
		return nil, err
	}
	c.value, err = strconv.ParseUint(strings.TrimSpace(string(data)), 10, 64)
	return c, err
}
func (c *counter) current() uint64 { c.mu.Lock(); defer c.mu.Unlock(); return c.value }
func (c *counter) increment() (uint64, error) {
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.uncertain {
		return 0, errors.New("previous write outcome uncertain: inspect storage and restart")
	}
	if c.value == ^uint64(0) {
		return 0, errors.New("counter exhausted")
	}
	next := c.value + 1
	f, err := os.CreateTemp(c.dir, ".counter-")
	if err != nil {
		return 0, err
	}
	name := f.Name()
	defer os.Remove(name)
	if _, err = fmt.Fprintf(f, "%d\n", next); err != nil {
		f.Close()
		return 0, err
	}
	if err = f.Sync(); err != nil {
		f.Close()
		return 0, err
	}
	if err = f.Close(); err != nil {
		return 0, err
	}
	if err = os.Rename(name, filepath.Join(c.dir, "counter")); err != nil {
		return 0, err
	}
	// A failure after rename gives an uncertain persistence outcome. Do not
	// silently repeat writes against stale in-memory state.
	d, err := os.Open(c.dir)
	if err != nil {
		c.uncertain = true
		return 0, err
	}
	err = d.Sync()
	closeErr := d.Close()
	if err != nil {
		c.uncertain = true
		return 0, err
	}
	if closeErr != nil {
		c.uncertain = true
		return 0, closeErr
	}
	c.value = next
	return next, nil
}
func env(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
func check() error {
	client := http.Client{Timeout: 2 * time.Second}
	response, err := client.Get(env("APP_CHECK_URL", "http://127.0.0.1:8080/health"))
	if err != nil {
		return err
	}
	defer response.Body.Close()
	_, _ = io.Copy(io.Discard, response.Body)
	if response.StatusCode != http.StatusOK {
		return fmt.Errorf("health status %d", response.StatusCode)
	}
	return nil
}
func main() {
	if len(os.Args) > 1 && os.Args[1] == "check" {
		if err := check(); err != nil {
			log.Print(err)
			os.Exit(1)
		}
		return
	}
	var store *counter
	if dir := os.Getenv("APP_DATA_DIR"); dir != "" {
		var err error
		store, err = openCounter(dir)
		if err != nil {
			log.Fatal(err)
		}
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /health", func(w http.ResponseWriter, r *http.Request) { fmt.Fprintln(w, "ok") })
	mux.HandleFunc("GET /version", func(w http.ResponseWriter, r *http.Request) { fmt.Fprintln(w, version) })
	mux.HandleFunc("GET /greet", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]string{"greeting": "hello", "name": r.URL.Query().Get("name"), "version": version})
	})
	mux.HandleFunc("/counter", func(w http.ResponseWriter, r *http.Request) {
		if store == nil {
			http.Error(w, "APP_DATA_DIR is not configured", http.StatusServiceUnavailable)
			return
		}
		switch r.Method {
		case http.MethodGet:
			fmt.Fprintln(w, store.current())
		case http.MethodPost:
			value, err := store.increment()
			if err != nil {
				log.Printf("counter write: %v", err)
				http.Error(w, "write failed; investigate outcome before retry", http.StatusServiceUnavailable)
				return
			}
			fmt.Fprintln(w, value)
		default:
			w.Header().Set("Allow", "GET, POST")
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		}
	})
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		mux.ServeHTTP(w, r)
		// Log bounded known dimensions, not query strings or credentials.
		method := r.Method
		switch method {
		case http.MethodGet, http.MethodPost, http.MethodHead:
		default:
			method = "OTHER"
		}
		route := r.Pattern
		if route == "" {
			route = "unmatched"
		}
		log.Printf("method=%q route=%q elapsed_us=%d", method, route, time.Since(start).Microseconds())
	})
	server := &http.Server{Addr: env("APP_ADDR", ":8080"), Handler: handler, ReadHeaderTimeout: 5 * time.Second, IdleTimeout: 30 * time.Second, MaxHeaderBytes: 1 << 20}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, syscall.SIGINT)
	defer stop()
	finished := make(chan struct{})
	go func() {
		<-ctx.Done()
		deadline, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()
		if err := server.Shutdown(deadline); err != nil {
			log.Printf("shutdown: %v", err)
			_ = server.Close()
		}
		close(finished)
	}()
	log.Printf("version=%s listen=%s data_enabled=%t", version, server.Addr, store != nil)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatal(err)
	}
	if ctx.Err() != nil {
		<-finished
	}
	log.Print("stopped")
}
