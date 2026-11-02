package main

import (
	"encoding/json"
	"os"
	"runtime"
	"runtime/metrics"
	"time"
)

var Hold [][]byte
var Sink []byte

func snap() map[string]any {
	names := []string{"/gc/heap/live:bytes", "/gc/heap/goal:bytes", "/gc/cycles/total:gc-cycles", "/cpu/classes/gc/mark/assist:cpu-seconds", "/memory/classes/total:bytes", "/memory/classes/heap/released:bytes"}
	s := make([]metrics.Sample, len(names))
	for i, n := range names {
		s[i].Name = n
	}
	metrics.Read(s)
	m := map[string]any{}
	for _, x := range s {
		if x.Value.Kind() == metrics.KindUint64 {
			m[x.Name] = x.Value.Uint64()
		} else if x.Value.Kind() == metrics.KindFloat64 {
			m[x.Name] = x.Value.Float64()
		}
	}
	return m
}
func main() {
	for i := 0; i < 128; i++ {
		b := make([]byte, 64<<10)
		for j := 0; j < len(b); j += 4096 {
			b[j] = byte(i)
		}
		Hold = append(Hold, b)
	}
	runtime.GC()
	before := snap()
	start := time.Now()
	for i := 0; i < 4096; i++ {
		Sink = make([]byte, 16<<10)
		Sink[0] = byte(i)
	}
	elapsed := time.Since(start)
	after := snap()
	json.NewEncoder(os.Stdout).Encode(map[string]any{"live_payload_bytes": 8 << 20, "churn_requested_bytes": 64 << 20, "elapsed_ns": elapsed.Nanoseconds(), "before": before, "after": after})
	runtime.KeepAlive(Hold)
}
