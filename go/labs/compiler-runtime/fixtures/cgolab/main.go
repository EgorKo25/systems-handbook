package main

/*
#include <stdint.h>
#include <stdlib.h>
static int twice(int x) {return x*2;}
static long sum_ints(int *p,int n) {long s=0;for(int i=0;i<n;i++)s+=p[i];return s;}
static long sum_bytes(unsigned char *p,int n) {long s=0;for(int i=0;i<n;i++)s+=p[i];return s;}
static void touch(void *p) {(void)p;}
extern int callGo(uintptr_t h,int x);
*/
import "C"
import (
	"fmt"
	"os"
	"runtime"
	"runtime/cgo"
	"unsafe"
)

type Box struct{ P *int }

//export GoValue
func GoValue(h C.uintptr_t, x C.int) C.int {
	f := cgo.Handle(h).Value().(func(int) int)
	return C.int(f(int(x)))
}
func main() {
	if len(os.Args) > 1 && os.Args[1] == "badpointer" {
		n := 7
		b := Box{&n}
		C.touch(unsafe.Pointer(&b))
		runtime.KeepAlive(b)
		return
	}
	bs := []byte{1, 2, 3}
	bytesSum := C.sum_bytes((*C.uchar)(unsafe.Pointer(&bs[0])), C.int(len(bs)))
	runtime.KeepAlive(bs)
	xs := []C.int{1, 2, 3}
	sum := C.sum_ints(&xs[0], C.int(len(xs)))
	runtime.KeepAlive(xs)
	s := C.CString("Go")
	C.free(unsafe.Pointer(s))
	h := cgo.NewHandle(func(x int) int { return x + 1 })
	result := C.callGo(C.uintptr_t(h), 41)
	h.Delete()
	fmt.Printf("bytes=%d\n", bytesSum)
	fmt.Printf("twice=%d sum=%d callback=%d C.int=%d Go.int=%d\n", C.twice(21), sum, result, unsafe.Sizeof(C.int(0)), unsafe.Sizeof(int(0)))
}
