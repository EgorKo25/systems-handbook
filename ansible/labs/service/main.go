package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"log"
	"net"
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

var version = "dev"

type config struct {
	Listen   string `json:"listen"`
	DataFile string `json:"data_file"`
	Message  string `json:"message"`
}

func loadConfig(path string) (config, error) {
	var cfg config
	file, err := os.Open(path)
	if err != nil {
		return cfg, err
	}
	defer file.Close()
	decoder := json.NewDecoder(io.LimitReader(file, 65537))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&cfg); err != nil {
		return cfg, err
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		return cfg, errors.New("configuration must contain one JSON object")
	}
	if _, _, err := net.SplitHostPort(cfg.Listen); err != nil {
		return cfg, fmt.Errorf("listen: %w", err)
	}
	if !filepath.IsAbs(cfg.DataFile) {
		return cfg, errors.New("data_file must be absolute")
	}
	if len(cfg.Message) > 1024 {
		return cfg, errors.New("message is too long")
	}
	return cfg, nil
}

type store struct {
	mu    sync.Mutex
	path  string
	count uint64
}

func openStore(path string) (*store, error) {
	s := &store{path: path}
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return s, nil
	}
	if err != nil {
		return nil, err
	}
	s.count, err = strconv.ParseUint(strings.TrimSpace(string(data)), 10, 64)
	if err != nil {
		return nil, fmt.Errorf("invalid persisted count: %w", err)
	}
	return s, nil
}

func (s *store) increment() (uint64, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.count == ^uint64(0) {
		return s.count, errors.New("counter exhausted")
	}
	next := s.count + 1
	file, err := os.CreateTemp(filepath.Dir(s.path), ".counter-")
	if err != nil {
		return s.count, err
	}
	name := file.Name()
	defer os.Remove(name)
	if err = file.Chmod(0640); err == nil {
		_, err = fmt.Fprintf(file, "%d\n", next)
	}
	if err == nil {
		err = file.Sync()
	}
	closeErr := file.Close()
	if err == nil {
		err = closeErr
	}
	if err != nil {
		return s.count, err
	}
	if err = os.Rename(name, s.path); err != nil {
		return s.count, err
	}
	s.count = next // Rename succeeded: never repeat this value inside this process.
	directory, err := os.Open(filepath.Dir(s.path))
	if err != nil {
		return next, err
	}
	err = directory.Sync()
	_ = directory.Close()
	return next, err
}

func (s *store) value() uint64 { s.mu.Lock(); defer s.mu.Unlock(); return s.count }

func handler(cfg config, s *store) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}
		_, _ = fmt.Fprintln(w, "ok")
	})
	mux.HandleFunc("/version", func(w http.ResponseWriter, r *http.Request) { _, _ = fmt.Fprintln(w, version) })
	mux.HandleFunc("/counter", func(w http.ResponseWriter, r *http.Request) {
		value := s.value()
		if r.Method == http.MethodPost {
			var err error
			value, err = s.increment()
			if err != nil {
				http.Error(w, "persistence failed", http.StatusInternalServerError)
				return
			}
		} else if r.Method != http.MethodGet {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"count": value, "message": cfg.Message})
	})
	return mux
}

// serveUntilStopped owns shutdown, so main cannot exit during the drain.
func serveUntilStopped(ctx context.Context, server *http.Server, listener net.Listener, grace time.Duration) error {
	served := make(chan error, 1)
	go func() { served <- server.Serve(listener) }()
	select {
	case err := <-served:
		return err
	case <-ctx.Done():
		deadline, cancel := context.WithTimeout(context.Background(), grace)
		defer cancel()
		if err := server.Shutdown(deadline); err != nil {
			// A finite grace period: close transports and report incomplete drain.
			_ = server.Close()
			<-served
			return fmt.Errorf("graceful shutdown: %w", err)
		}
		err := <-served
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return err
	}
}

func main() {
	configPath := flag.String("config", "/etc/counter/config.json", "JSON configuration path")
	checkPath := flag.String("check-config", "", "validate this JSON file and exit without creating data or listening")
	showVersion := flag.Bool("version", false, "print the compiled release version and exit")
	flag.Parse()
	if *showVersion {
		fmt.Println(version)
		return
	}
	if *checkPath != "" {
		if _, err := loadConfig(*checkPath); err != nil {
			log.Fatal(err)
		}
		fmt.Println("configuration valid")
		return
	}
	cfg, err := loadConfig(*configPath)
	if err != nil {
		log.Fatal(err)
	}
	s, err := openStore(cfg.DataFile)
	if err != nil {
		log.Fatal(err)
	}
	server := &http.Server{Addr: cfg.Listen, Handler: handler(cfg, s), ReadHeaderTimeout: 3 * time.Second, IdleTimeout: 30 * time.Second}
	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()
	listener, err := net.Listen("tcp", cfg.Listen)
	if err != nil {
		log.Fatal(err)
	}
	if err := serveUntilStopped(ctx, server, listener, 5*time.Second); err != nil {
		log.Fatal(err)
	}
}
