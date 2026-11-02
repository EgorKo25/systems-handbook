package main

import (
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
)

func TestWorkAndMetrics(t *testing.T) {
	s := newService()
	for _, path := range []string{"/work", "/work?fail=1&untrusted_id=123"} {
		r := httptest.NewRecorder()
		s.handler().ServeHTTP(r, httptest.NewRequest("GET", path, nil))
		want := 200
		if strings.Contains(path, "fail=1") { want = 500 }
		if r.Code != want { t.Fatalf("status = %d, want %d", r.Code, want) }
	}
	r := httptest.NewRecorder()
	s.handler().ServeHTTP(r, httptest.NewRequest("GET", "/metrics", nil))
	for _, want := range []string{`lab_requests_total{code="200",route="/work"} 1`, `lab_requests_total{code="500",route="/work"} 1`, "lab_inflight_requests 0", "lab_request_duration_seconds_count{route=\"/work\"} 2", "go_goroutines", "process_cpu_seconds_total"} {
		if !strings.Contains(r.Body.String(), want) { t.Errorf("missing metric %s", want) }
	}
	if strings.Contains(r.Body.String(), "untrusted_id") { t.Fatal("input became a metric label") }
}

func TestConcurrentScrapeAndWork(t *testing.T) {
	s := newService()
	h := s.handler()
	var wg sync.WaitGroup
	for i := 0; i < 12; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); for j := 0; j < 20; j++ { h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/work", nil)); h.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/metrics", nil)) } }()
	}
	wg.Wait()
}

func BenchmarkObserve(b *testing.B) {
	s := newService()
	h := s.duration.WithLabelValues("/work")
	b.ReportAllocs()
	for i := 0; i < b.N; i++ { h.Observe(.02) }
}

func BenchmarkObserveLookup(b *testing.B) {
	s := newService()
	b.ReportAllocs()
	for i := 0; i < b.N; i++ { s.duration.WithLabelValues("/work").Observe(.02) }
}
