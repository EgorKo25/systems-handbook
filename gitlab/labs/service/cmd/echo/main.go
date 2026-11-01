package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"time"
)

var Version = "dev"

func handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /ready", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
		fmt.Fprintln(w, "ready")
	})
	mux.HandleFunc("GET /echo", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(struct {
			Value string `json:"value"`
		}{Value: r.URL.Query().Get("value")})
	})
	return mux
}

func main() {
	version := flag.Bool("version", false, "print the linked version and exit")
	listen := flag.String("listen", "127.0.0.1:18081", "HTTP listen address")
	flag.Parse()
	if *version {
		fmt.Println(Version)
		return
	}
	server := &http.Server{Addr: *listen, Handler: handler(), ReadHeaderTimeout: 5 * time.Second}
	log.Fatal(server.ListenAndServe())
}
