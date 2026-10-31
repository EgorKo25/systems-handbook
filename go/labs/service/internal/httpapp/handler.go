package httpapp

import (
	"encoding/json"
	"net/http"
	"strings"
)

type Reply struct {
	Message string `json:"message"`
	Version string `json:"version"`
}

func New(version string) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		_ = json.NewEncoder(w).Encode(Reply{"ok", version})
	})
	mux.HandleFunc("/greet", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			w.Header().Set("Allow", "GET")
			http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
			return
		}
		name := strings.TrimSpace(r.URL.Query().Get("name"))
		if name == "" {
			name = "reader"
		}
		if len(name) > 128 {
			http.Error(w, "name exceeds 128 UTF-8 bytes", http.StatusBadRequest)
			return
		}
		w.Header().Set("Content-Type", "application/json; charset=utf-8")
		_ = json.NewEncoder(w).Encode(Reply{"Hello, " + name + "!", version})
	})
	return mux
}
