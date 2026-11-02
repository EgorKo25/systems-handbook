package memory

import "testing"

var Pointers []*int
var Values []int

func PointerBatch(n int) []*int {
	r := make([]*int, n)
	for i := range r {
		v := i
		r[i] = &v
	}
	return r
}
func ValueBatch(n int) []int {
	r := make([]int, n)
	for i := range r {
		r[i] = i
	}
	return r
}
func BenchmarkPointers(b *testing.B) {
	for b.Loop() {
		Pointers = PointerBatch(128)
	}
}
func BenchmarkValues(b *testing.B) {
	for b.Loop() {
		Values = ValueBatch(128)
	}
}
func TestAllocs(t *testing.T) {
	p := testing.AllocsPerRun(20, func() { Pointers = PointerBatch(128) })
	v := testing.AllocsPerRun(20, func() { Values = ValueBatch(128) })
	t.Logf("pointers %.0f values %.0f", p, v)
	if p <= v {
		t.Fatal("expected more pointer objects")
	}
}
