package main

import "fmt"

var Version = "dev"

//go:noinline
func Keep(x int) int { return x*3 + 1 }

//go:noinline
func Dead(x int) int { return x + 99 }
func main()          { fmt.Println(Version, Keep(7)) }
