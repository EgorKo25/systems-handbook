package main
type Count int
type Alias = int
//go:noinline
func Add[T ~int | ~int64](a, b T) T { return a + b }
func main() {
 println(Add(2, 3))
 println(Add(Count(4), Count(5)))
 println(Add(int64(6), int64(7)))
}
