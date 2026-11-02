package httpapp

import (
	"net/http/httptest"
	"testing"
)

var BodyBytes int

func BenchmarkGreet(b *testing.B) {
	h := New("bench")
	r := httptest.NewRequest("GET", "/greet?name=Go", nil)
	for b.Loop() {
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		BodyBytes = w.Body.Len()
	}
}
