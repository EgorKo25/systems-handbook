// Original teaching service. Flyway is a separate deployment process.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

// decodeNote consumes exactly one JSON object within the entire body budget.
// The second Decode enforces EOF, including any whitespace after the object.
func decodeNote(w http.ResponseWriter, r *http.Request) (string, error) {
	r.Body = http.MaxBytesReader(w, r.Body, 8192)
	decoder := json.NewDecoder(r.Body)
	var input struct {
		Text string `json:"text"`
	}
	if err := decoder.Decode(&input); err != nil {
		return "", err
	}
	if input.Text == "" {
		return "", errors.New("text is required")
	}
	var extra any
	if err := decoder.Decode(&extra); !errors.Is(err, io.EOF) {
		if err == nil {
			err = errors.New("one JSON object is required")
		}
		return "", err
	}
	return input.Text, nil
}

func main() {
	release := os.Getenv("APP_RELEASE")
	if release != "v1" && release != "v2" && release != "v3" {
		log.Fatal("APP_RELEASE must be v1, v2, or v3")
	}
	db, err := sql.Open("pgx", os.Getenv("DATABASE_URL"))
	if err != nil {
		log.Fatal("database configuration rejected")
	}
	defer db.Close()
	db.SetMaxOpenConns(4)
	db.SetMaxIdleConns(2)
	db.SetConnMaxLifetime(5 * time.Minute)
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	err = db.PingContext(ctx)
	cancel()
	if err != nil {
		log.Fatal("database unavailable")
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), time.Second)
		defer cancel()
		if err := db.PingContext(ctx); err != nil {
			http.Error(w, "database unavailable", 503)
			return
		}
		w.Header().Set("X-Handbook-Instance", os.Getenv("APP_INSTANCE"))
		fmt.Fprintln(w, release)
	})
	mux.HandleFunc("POST /notes", func(w http.ResponseWriter, r *http.Request) {
		text, err := decodeNote(w, r)
		if err != nil {
			http.Error(w, "one JSON object with non-empty text, at most 8192 bytes, is required", 400)
			return
		}
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		var id int64
		query := "INSERT INTO app.notes(body) VALUES($1) RETURNING id"
		if release == "v2" {
			query = "INSERT INTO app.notes(body,title) VALUES($1,$1) RETURNING id"
		}
		if release == "v3" {
			query = "INSERT INTO app.notes(title) VALUES($1) RETURNING id"
		}
		if err := db.QueryRowContext(ctx, query, text).Scan(&id); err != nil {
			http.Error(w, "write failed; do not retry blindly", 503)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(201)
		json.NewEncoder(w).Encode(map[string]any{"id": id, "release": release})
	})
	mux.HandleFunc("GET /notes", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 3*time.Second)
		defer cancel()
		query := "SELECT id,body FROM app.notes ORDER BY id LIMIT 100"
		if release == "v2" {
			query = "SELECT id,COALESCE(title,body) FROM app.notes ORDER BY id LIMIT 100"
		}
		if release == "v3" {
			query = "SELECT id,title FROM app.notes ORDER BY id LIMIT 100"
		}
		rows, err := db.QueryContext(ctx, query)
		if err != nil {
			http.Error(w, "read failed", 503)
			return
		}
		defer rows.Close()
		type note struct {
			ID   int64  `json:"id"`
			Text string `json:"text"`
		}
		output := []note{}
		for rows.Next() {
			var n note
			if err := rows.Scan(&n.ID, &n.Text); err != nil {
				http.Error(w, "decode failed", 503)
				return
			}
			output = append(output, n)
		}
		if rows.Err() != nil {
			http.Error(w, "read interrupted", 503)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(output)
	})
	server := &http.Server{Addr: "127.0.0.1:18080", Handler: mux, ReadHeaderTimeout: 3 * time.Second, ReadTimeout: 5 * time.Second, WriteTimeout: 5 * time.Second, IdleTimeout: 30 * time.Second}
	stopped := make(chan os.Signal, 1)
	signal.Notify(stopped, syscall.SIGINT, syscall.SIGTERM)
	drained := make(chan error, 1)
	go func() {
		<-stopped
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		drained <- server.Shutdown(ctx)
	}()
	log.Printf("notes %s listening on 127.0.0.1:18080", release)
	if err := server.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatal("HTTP listener failed")
	}
	// ListenAndServe returns when listeners close; active handlers may still run.
	if err := <-drained; err != nil {
		log.Print("graceful shutdown deadline exceeded; in-flight results require inspection")
		server.Close()
	}
}
