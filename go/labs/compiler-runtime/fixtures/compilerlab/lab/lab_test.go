package lab

import (
	"fmt"
	"runtime"
	"testing"
)

var Result int
var PointerResult []*int
var ValueResult []int

func TestValues(t *testing.T) {
	if Use(42) != 42 || Borrow(9) != 9 || Mix(7) != 22 || Ten(1, 2, 3, 4, 5, 6, 7, 8, 9, 10) != 55 || AddAsm(2, 3) != 5 {
		t.Fatal("arithmetic")
	}
	c := Counter(7)
	if c() != 8 || c() != 9 {
		t.Fatal("closure")
	}
	a, b := Swap(2, 9)
	if a != 9 || b != 2 {
		t.Fatal("swap")
	}
	for _, n := range []int{0, 1, 16, 1024, 65536} {
		xs := make([]int, n)
		for i := range xs {
			xs[i] = i%17 - 8
		}
		r := n % 17
		want := r*(r-1)/2 - 8*r
		if SumIndex(xs) != want || SumRange(xs) != want {
			t.Fatal(n, want)
		}
	}
	if Select([]int{2, 4}, 0, false) != 4 || Select([]int{2}, 0, false) != -1 || Select(nil, -1, true) != -1 {
		t.Fatal("bounds")
	}
	defer func() {
		if recover() == nil {
			t.Fatal("missing panic")
		}
	}()
	Unchecked([]int{1}, -1)
}
func TestAllocs(t *testing.T) {
	t.Log("use", testing.AllocsPerRun(100, func() { Result = Use(42) }), "borrow", testing.AllocsPerRun(100, func() { Result = Borrow(42) }), "pointers", testing.AllocsPerRun(100, func() { PointerResult = PointerBatch() }), "values", testing.AllocsPerRun(100, func() { ValueResult = ValueBatch() }))
}
func BenchmarkUse(b *testing.B) {
	for b.Loop() {
		Result = Use(42)
	}
}
func BenchmarkPointer(b *testing.B) {
	for b.Loop() {
		PointerResult = PointerBatch()
	}
}
func BenchmarkValue(b *testing.B) {
	for b.Loop() {
		ValueResult = ValueBatch()
	}
}
func BenchmarkSum(b *testing.B) {
	for _, n := range []int{0, 1, 16, 1024, 65536} {
		xs := make([]int, n)
		for i := range xs {
			xs[i] = i%17 - 8
		}
		b.Run(fmt.Sprintf("index/%d", n), func(b *testing.B) {
			for b.Loop() {
				Result = SumIndex(xs)
			}
		})
		b.Run(fmt.Sprintf("range/%d", n), func(b *testing.B) {
			for b.Loop() {
				Result = SumRange(xs)
			}
		})
		runtime.KeepAlive(xs)
	}
}
