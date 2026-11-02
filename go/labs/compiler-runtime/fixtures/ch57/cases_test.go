package cases

import "testing"

var Sink int

func SumIndex(xs []int) int {
	n := 0
	for i := 0; i < len(xs); i++ {
		n += xs[i]
	}
	return n
}
func SumRange(xs []int) int {
	n := 0
	for _, x := range xs {
		n += x
	}
	return n
}
func BenchmarkIndex(b *testing.B) {
	xs := make([]int, 1024)
	for i := range xs {
		xs[i] = i
	}
	for b.Loop() {
		Sink = SumIndex(xs)
	}
}
func BenchmarkRange(b *testing.B) {
	xs := make([]int, 1024)
	for i := range xs {
		xs[i] = i
	}
	for b.Loop() {
		Sink = SumRange(xs)
	}
}
func TestAgreement(t *testing.T) {
	xs := []int{1, -2, 3, 4}
	if SumIndex(xs) != 6 || SumRange(xs) != 6 {
		t.Fatal("wrong sum")
	}
}
