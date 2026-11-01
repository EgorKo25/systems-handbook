package lib
var Value = initialize()
func initialize() int { println("lib-var"); return 7 }
func init() { println("lib-init") }
