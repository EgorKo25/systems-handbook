package main

//go:noinline
func Mix(x int) int { return 3*x + 1 }

//go:noinline
func At(xs []int, i int) int { return xs[i] }
func main() {
	println(Mix(7))
	println(At([]int{9}, 0))
}
