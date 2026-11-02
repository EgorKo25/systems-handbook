package main

//go:noinline
func Ten(a, b, c, d, e, f, g, h, i, j int) int {
	return a + b + c + d + e + f + g + h + i + j
}
func main() { println(Ten(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)) }
