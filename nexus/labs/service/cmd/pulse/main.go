package main

import (
	"flag"
	"fmt"
	"log"
	"net"
	"net/http"

	"example.invalid/Acme/ledger"
)

var version = "development"

func main() {
	show := flag.Bool("version", false, "print build version")
	addr := flag.String("listen", "127.0.0.1:18090", "HTTP listen address")
	flag.Parse()
	if *show {
		fmt.Println(version)
		return
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) { fmt.Fprintln(w, "ok") })
	mux.HandleFunc("GET /version", func(w http.ResponseWriter, r *http.Request) { fmt.Fprintln(w, version) })
	mux.HandleFunc("GET /hello", func(w http.ResponseWriter, r *http.Request) { fmt.Fprintln(w, ledger.Message("reader")) })
	listener, err := net.Listen("tcp", *addr)
	if err != nil { log.Fatal(err) }
	fmt.Println("LISTEN " + listener.Addr().String())
	if err := http.Serve(listener, mux); err != nil { log.Fatal(err) }
}
