// An original bounded, loopback-only service for the handbook.
package main

import (
	"context"
	"flag"
	"log"
	"net"
	"net/http"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/collectors"
	"github.com/prometheus/client_golang/prometheus/promhttp"
)

type service struct {
	registry *prometheus.Registry
	requests *prometheus.CounterVec
	duration *prometheus.HistogramVec
	inflight prometheus.Gauge
}

func newService() *service {
	s := &service{
		registry: prometheus.NewRegistry(),
		requests: prometheus.NewCounterVec(prometheus.CounterOpts{Name: "lab_requests_total", Help: "Completed work requests."}, []string{"route", "code"}),
		duration: prometheus.NewHistogramVec(prometheus.HistogramOpts{Name: "lab_request_duration_seconds", Help: "Completed work duration in seconds.", Buckets: []float64{.01, .05, .1, .3, 1}}, []string{"route"}),
		inflight: prometheus.NewGauge(prometheus.GaugeOpts{Name: "lab_inflight_requests", Help: "Work handlers currently executing."}),
	}
	s.registry.MustRegister(s.requests, s.duration, s.inflight, collectors.NewGoCollector(), collectors.NewProcessCollector(collectors.ProcessCollectorOpts{}))
	for _, code := range []string{"200", "500"} {
		s.requests.WithLabelValues("/work", code)
	}
	s.duration.WithLabelValues("/work")
	return s
}

func (s *service) work(w http.ResponseWriter, r *http.Request) {
	started := time.Now()
	s.inflight.Inc()
	defer s.inflight.Dec()
	code := http.StatusOK
	if r.URL.Query().Get("fail") == "1" {
		code = http.StatusInternalServerError
	}
	// The query controls a bounded experiment, never a metric label.
	ms, _ := strconv.Atoi(r.URL.Query().Get("delay_ms"))
	if ms < 0 {
		ms = 0
	}
	if ms > 200 {
		ms = 200
	}
	timer := time.NewTimer(time.Duration(ms) * time.Millisecond)
	defer timer.Stop()
	select {
	case <-timer.C:
	case <-r.Context().Done():
		// This sample app counts cancellation as unsuccessful work.
		code = http.StatusInternalServerError
	}
	s.requests.WithLabelValues("/work", strconv.Itoa(code)).Inc()
	s.duration.WithLabelValues("/work").Observe(time.Since(started).Seconds())
	w.WriteHeader(code)
	_, _ = w.Write([]byte("work complete\n"))
}

func (s *service) handler() http.Handler {
	mux := http.NewServeMux()
	mux.Handle("/metrics", promhttp.HandlerFor(s.registry, promhttp.HandlerOpts{}))
	mux.HandleFunc("/work", s.work)
	mux.HandleFunc("/ready", func(w http.ResponseWriter, _ *http.Request) { _, _ = w.Write([]byte("ready\n")) })
	return mux
}

func main() {
	port := flag.Int("port", 18080, "loopback TCP port, 1..65535")
	flag.Parse()
	if *port < 1 || *port > 65535 {
		log.Fatal("invalid port")
	}
	listener, err := net.Listen("tcp", net.JoinHostPort("127.0.0.1", strconv.Itoa(*port)))
	if err != nil {
		log.Fatal(err)
	}
	server := &http.Server{Handler: newService().handler(), ReadHeaderTimeout: 3 * time.Second}
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()
	shutdownDone := make(chan struct{})
	go func() {
		defer close(shutdownDone)
		<-ctx.Done()
		shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := server.Shutdown(shutdown); err != nil {
			log.Printf("HTTP shutdown: %v", err)
		}
	}()
	log.Printf("listening on %s", listener.Addr())
	if err := server.Serve(listener); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
	<-shutdownDone
}
