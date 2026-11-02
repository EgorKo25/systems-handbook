package main

import "testing"

func TestAdd(t *testing.T) {
	t.Run("positive", func(t *testing.T) {
		if got := Add(2, 3); got != 5 {
			t.Fatalf("got %d", got)
		}
	})
}

func BenchmarkAdd(b *testing.B) {
	for b.Loop() {
		_ = Add(2, 3)
	}
}

func FuzzAdd(f *testing.F) {
	f.Add(1, 2)
	f.Fuzz(func(t *testing.T, a, b int) {
		if Add(a, b) != Add(b, a) {
			t.Fatal("not commutative")
		}
	})
}
