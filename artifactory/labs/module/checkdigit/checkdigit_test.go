package checkdigit

import "testing"

func TestKnownBytes(t *testing.T) {
	if got := Of("AB"); got != 1 {
		t.Fatalf("ASCII 65+66 mod 10: got %d", got)
	}
	if got := Of(""); got != 0 {
		t.Fatalf("empty input: got %d", got)
	}
}
