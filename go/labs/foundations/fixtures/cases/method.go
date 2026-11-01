package bad
type Count int
func (c *Count) Inc(){}
func Use[T interface{Inc()}](v T){v.Inc()}; func F(){var c Count;Use(c)}
