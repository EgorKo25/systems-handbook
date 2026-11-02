package main

//go:noinline
func Answer(x int) int { return x + 1 }
func main()            { println(Answer(41)) }
