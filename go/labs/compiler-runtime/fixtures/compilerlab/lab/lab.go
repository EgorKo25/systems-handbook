package lab

func Ptr(v int) *int { return &v }

//go:noinline
func Use(v int) int { return *Ptr(v) }

//go:noinline
func Read(p *int) int { return *p }

//go:noinline
func Borrow(v int) int { return Read(&v) }

var Global *int

//go:noinline
func Save(v int) { Global = &v }

//go:noinline
func Select(xs []int, i int, left bool) int {
	j := i
	if !left {
		j = i + 1
	}
	if j < 0 || j >= len(xs) {
		return -1
	}
	return xs[j]
}

//go:noinline
func Unchecked(xs []int, i int) int { return xs[i] }

//go:noinline
func SumIndex(xs []int) int {
	s := 0
	for i := 0; i < len(xs); i++ {
		s += xs[i]
	}
	return s
}

//go:noinline
func SumRange(xs []int) int {
	s := 0
	for _, x := range xs {
		s += x
	}
	return s
}

//go:noinline
func Mix(x int) int { return x*3 + 1 }

//go:noinline
func Ten(a, b, c, d, e, f, g, h, i, j int) int { return a + b + c + d + e + f + g + h + i + j }

//go:noinline
func Across(p *int) int { n := Mix(2); return *p + n }

//go:noinline
func Deep(n int, p *int) int {
	var pad [64]int
	pad[n&63] = n
	if n == 0 {
		return *p
	}
	return Deep(n-1, p) + pad[n&63]
}

//go:noinline
func Mem(p *int) int           { *p = 1; a := *p; *p = 2; return a + *p }
func Counter(n int) func() int { return func() int { n++; return n } }
func Swap(a, b int) (int, int) { a, b = b, a; return a, b }

var Published *int

//go:noinline
func Publish(p *int) { Published = p }

//go:noinline
func PointerBatch() []*int {
	out := make([]*int, 128)
	for i := range out {
		p := new(int)
		*p = i
		out[i] = p
	}
	return out
}

//go:noinline
func ValueBatch() []int {
	out := make([]int, 128)
	for i := range out {
		out[i] = i
	}
	return out
}

type Pair struct{ A, B int }

const Scale = 3

func AddAsm(a, b int) int
