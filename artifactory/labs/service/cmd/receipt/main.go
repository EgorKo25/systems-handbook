package main

import (
	"encoding/json"
	"fmt"
	"os"

	"example.invalid/BuildLab/checkdigit"
)

// Set only at the release build, then inspect the same published bytes.
var version = "dev"

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: receipt ORDER")
		os.Exit(2)
	}
	if err := json.NewEncoder(os.Stdout).Encode(struct {
		Order   string `json:"order"`
		Digit   int    `json:"digit"`
		Version string `json:"version"`
	}{os.Args[1], checkdigit.Of(os.Args[1]), version}); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
