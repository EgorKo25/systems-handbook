package pgolab

import "testing"

func TestBoth(t *testing.T) {
	for _, e := range []Eval{Hot{}, Cold{}} {
		for _, x := range []uint64{0, 1, 42, ^uint64(0)} {
			if Apply(e, x) != e.Eval(x) {
				t.Fatal(x)
			}
		}
	}
}
func BenchmarkSkew(b *testing.B) {
	es := []Eval{Hot{}, Cold{}}
	i := 0
	for b.Loop() {
		j := 0
		if i%100 == 0 {
			j = 1
		}
		Value = Apply(es[j], uint64(i))
		i++
	}
}
func BenchmarkBalanced(b *testing.B) {
	es := []Eval{Hot{}, Cold{}}
	i := 0
	for b.Loop() {
		Value = Apply(es[i&1], uint64(i))
		i++
	}
}
