package main
import "example.invalid/front/lib"
var X = initialize()
func initialize() int { println("main-var"); return lib.Value }
func init() { println("main-init") }
func main() { println("main", X) }
