package httpapp

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestHandler(t *testing.T) {
	cases := []struct {
		name, method, path string
		status             int
		message            string
	}{
		{"health", "GET", "/healthz", 200, "ok"},
		{"default", "GET", "/greet", 200, "Hello, reader!"},
		{"name", "GET", "/greet?name=Go", 200, "Hello, Go!"},
		{"spaces", "GET", "/greet?name=%20%20", 200, "Hello, reader!"},
		{"unicode", "GET", "/greet?name=%D0%9C%D0%B8%D1%80", 200, "Hello, Мир!"},
		{"method", "POST", "/greet", 405, ""},
		{"health-method", "DELETE", "/healthz", 405, ""},
		{"missing", "GET", "/absent", 404, ""},
		{"long", "GET", "/greet?name=" + strings.Repeat("x", 129), 400, ""},
	}
	handler := New("test-version")
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			w := httptest.NewRecorder()
			handler.ServeHTTP(w, httptest.NewRequest(tc.method, tc.path, nil))
			if w.Code != tc.status {
				t.Fatalf("status %d, want %d", w.Code, tc.status)
			}
			if tc.status == http.StatusMethodNotAllowed && w.Header().Get("Allow") != "GET" {
				t.Fatal("missing Allow header")
			}
			if tc.message != "" {
				var reply Reply
				if err := json.Unmarshal(w.Body.Bytes(), &reply); err != nil {
					t.Fatal(err)
				}
				if reply.Message != tc.message || reply.Version != "test-version" {
					t.Fatalf("reply %+v", reply)
				}
				if w.Header().Get("Content-Type") != "application/json; charset=utf-8" {
					t.Fatal("content type")
				}
			}
		})
	}
}
