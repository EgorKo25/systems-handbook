package main

//go:noinline
func Keep(x int) int { return x + 1 }

//go:noinline
func Dead() int { return 123456 }
func main()     { println(Keep(7)) }
