package main

import "testing"

func BenchmarkWork(b *testing.B) {
	for b.Loop() {
		Sink = Work(Sink)
	}
}
