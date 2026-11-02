package main

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestDecodeNoteBody(t *testing.T) {
	cases := []struct {
		name string
		body string
		want string
		ok   bool
	}{
		{"valid", `{"text":"hello"}`, "hello", true},
		{"whitespace", "  {\"text\":\"hello\"} \n\t", "hello", true},
		{"second-object", `{"text":"hello"}{"text":"other"}`, "", false},
		{"second-scalar", `{"text":"hello"} 42`, "", false},
		{"garbage", `{"text":"hello"} trailing`, "", false},
		{"empty-text", `{"text":""}`, "", false},
		{"null", `null`, "", false},
		{"exact-budget", `{"text":"` + strings.Repeat("x", 8181) + `"}`, strings.Repeat("x", 8181), true},
		{"object-overflow", `{"text":"` + strings.Repeat("x", 8192) + `"}`, "", false},
		{"whitespace-overflow", `{"text":"hello"}` + strings.Repeat(" ", 8192), "", false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			request := httptest.NewRequest(http.MethodPost, "/notes", strings.NewReader(tc.body))
			recorder := httptest.NewRecorder()
			text, err := decodeNote(recorder, request)
			if (err == nil) != tc.ok || text != tc.want {
				t.Fatalf("text length=%d, error=%v, want length=%d success=%v", len(text), err, len(tc.want), tc.ok)
			}
		})
	}
}
