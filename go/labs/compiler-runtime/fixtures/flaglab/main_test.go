package main

import (
	"os"
	"testing"
)

func TestVersion(t *testing.T) {
	want := os.Getenv("WANT_VERSION")
	if want != "" && Version != want {
		t.Fatalf("Version=%s want=%s", Version, want)
	}
}
