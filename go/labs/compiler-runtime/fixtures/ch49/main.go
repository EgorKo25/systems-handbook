package main

//go:noinline
func Sum(xs []int) int {
	n := 0
	for i := 0; i < len(xs); i++ {
		n += xs[i]
	}
	return n
}

//go:noinline
func At(xs []int, i int) int { return xs[i] }
func main() {
	println(Sum([]int{1, 2, 3}))
	println(At([]int{9}, 0))
}
