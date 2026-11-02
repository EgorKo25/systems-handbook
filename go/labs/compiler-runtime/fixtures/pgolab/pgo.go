package pgolab

type Eval interface{ Eval(uint64) uint64 }
type Hot struct{}
type Cold struct{}

func (Hot) Eval(x uint64) uint64 {
	for i := 0; i < 40; i++ {
		x = x*1664525 + 1013904223
	}
	return x
}
func (Cold) Eval(x uint64) uint64 { return x ^ 0x12345678 }

//go:noinline
func Apply(e Eval, x uint64) uint64 { return e.Eval(x) }

var Value uint64
