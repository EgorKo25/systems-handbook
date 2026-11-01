// Public go/* tooling, not the compiler's internal syntax/types2 trees.
package main

import (
	"fmt"
	"go/ast"
	"go/parser"
	"go/scanner"
	"go/token"
	"go/types"
	"os"
)

func main() {
	if len(os.Args) != 2 {
		fmt.Fprintln(os.Stderr, "usage: inspect SOURCE")
		os.Exit(2)
	}
	name := os.Args[1]
	src, e := os.ReadFile(name)
	if e != nil {
		panic(e)
	}
	fs := token.NewFileSet()
	tf := fs.AddFile(name, -1, len(src))
	var s scanner.Scanner
	s.Init(tf, src, func(p token.Position, m string) { fmt.Fprintln(os.Stderr, p, m) }, 0)
	for {
		p, t, l := s.Scan()
		if t == token.EOF {
			break
		}
		fmt.Printf("token %d:%d %-10s %q\n", fs.Position(p).Line, fs.Position(p).Column, t, l)
	}
	fs = token.NewFileSet()
	f, e := parser.ParseFile(fs, name, src, 0)
	if e != nil {
		panic(e)
	}
	info := types.Info{Types: map[ast.Expr]types.TypeAndValue{}, Defs: map[*ast.Ident]types.Object{}, Uses: map[*ast.Ident]types.Object{}}
	_, e = (&types.Config{}).Check("example.invalid/front/sample", fs, []*ast.File{f}, &info)
	if e != nil {
		panic(e)
	}
	ast.Inspect(f, func(n ast.Node) bool {
		switch v := n.(type) {
		case *ast.BinaryExpr:
			tv := info.Types[v]
			fmt.Printf("binary %s type=%s constant=%v\n", v.Op, tv.Type, tv.Value)
		case *ast.CallExpr:
			tv := info.Types[v]
			fmt.Printf("call type=%s constant=%v\n", tv.Type, tv.Value)
		case *ast.Ident:
			if v.Name == "Answer" || v.Name == "Twice" {
				o := info.Defs[v]
				kind := "def"
				if o == nil {
					o = info.Uses[v]
					kind = "use"
				}
				if o != nil {
					fmt.Printf("%s %s -> %s\n", kind, v.Name, o)
				}
			}
		}
		return true
	})
}
