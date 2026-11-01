package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestReady(t *testing.T) {
	recorder := httptest.NewRecorder()
	handler().ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/ready", nil))
	if recorder.Code != http.StatusOK || recorder.Body.String() != "ready\n" {
		t.Fatalf("ready = %d %q", recorder.Code, recorder.Body.String())
	}
}

func TestEcho(t *testing.T) {
	for _, tc := range []struct{ name, query, want string }{
		{"ascii", "hello", "hello"},
		{"escaped", "%D1%81%D0%B5%D1%82%D1%8C%20%26%20Go", "сеть & Go"},
		{"empty", "", ""},
	} {
		t.Run(tc.name, func(t *testing.T) {
			recorder := httptest.NewRecorder()
			handler().ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/echo?value="+tc.query, nil))
			var body struct{ Value string `json:"value"` }
			if err := json.Unmarshal(recorder.Body.Bytes(), &body); err != nil {
				t.Fatal(err)
			}
			if body.Value != tc.want {
				t.Fatalf("value = %q, want %q", body.Value, tc.want)
			}
		})
	}
}

func TestWrongMethod(t *testing.T) {
	recorder := httptest.NewRecorder()
	handler().ServeHTTP(recorder, httptest.NewRequest(http.MethodPost, "/ready", nil))
	if recorder.Code != http.StatusMethodNotAllowed {
		t.Fatalf("code = %d", recorder.Code)
	}
}
