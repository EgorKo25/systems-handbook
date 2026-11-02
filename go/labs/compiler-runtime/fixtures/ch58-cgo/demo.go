package demo

/*
static int twice(int x) { return x * 2; }
*/
import "C"

func Twice(x int) int { return int(C.twice(C.int(x))) }
