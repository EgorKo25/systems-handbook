package main

var Sink *int

func Local(n int) int {
	p := new(int)
	*p = n
	return *p
}

//go:noinline
func Keep(n int) *int {
	p := new(int)
	*p = n
	return p
}
func main() {
	println(Local(7))
	Sink = Keep(9)
}
