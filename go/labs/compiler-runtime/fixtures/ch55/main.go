// main.go
package main

var Sink uint64

//go:noinline
func Work(x uint64) uint64 {
	for j := 0; j < 1000; j++ {
		x = x*1664525 + 1013904223
	}
	return x
}
func main() {
	for i := 0; i < 1000; i++ {
		Sink = Work(uint64(i))
	}
	println(Sink)
}
