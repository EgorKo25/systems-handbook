package bad
func Add[T ~int | ~int64](a,b T) T { return a+b }; var X = Add("a","b")
