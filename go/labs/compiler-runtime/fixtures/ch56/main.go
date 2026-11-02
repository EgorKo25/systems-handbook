package main

/*
static int twice(int x) { return 2*x; }
*/
import "C"

func main() { println(int(C.twice(21))) }
