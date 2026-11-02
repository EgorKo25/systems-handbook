package main

import (
	"encoding/binary"
	"example.org/compilerlab/lab"
	"fmt"
	"os"
	"runtime"
)

var Zero [4096]byte
var Data = [4]byte{42, 0, 0, 0}
var Version = "dev"

func main() {
	if len(os.Args) > 1 && os.Args[1] == "maps" {
		b, e := os.ReadFile("/proc/self/maps")
		if e != nil {
			panic(e)
		}
		fmt.Print(string(b))
		a, e := os.ReadFile("/proc/self/auxv")
		if e != nil {
			panic(e)
		}
		for len(a) >= 16 {
			k := binary.LittleEndian.Uint64(a)
			v := binary.LittleEndian.Uint64(a[8:])
			if k == 0 {
				break
			}
			if k == 3 || k == 4 || k == 5 || k == 6 || k == 7 || k == 9 {
				fmt.Printf("AUX %d %#x\n", k, v)
			}
			a = a[16:]
		}
		return
	}
	if len(os.Args) > 1 && os.Args[1] == "deep" {
		v := 42
		var a, b runtime.MemStats
		runtime.ReadMemStats(&a)
		r := lab.Deep(512, &v)
		runtime.ReadMemStats(&b)
		fmt.Printf("result=%d ptr=%d stackBefore=%d stackAfter=%d\n", r, *(&v), a.StackInuse, b.StackInuse)
		return
	}
	x, y := lab.Swap(2, 9)
	c := lab.Counter(7)
	v := 42
	fmt.Println(lab.Use(42), lab.Borrow(9), lab.Select([]int{2, 4, 6}, 0, false), lab.Mix(7), lab.Ten(1, 2, 3, 4, 5, 6, 7, 8, 9, 10), lab.Across(&v), lab.AddAsm(2, 3), x, y, c(), c(), lab.Mem(&v), Zero[4095], Data, Version)
	lab.Save(9)
	lab.Publish(lab.Global)
}
