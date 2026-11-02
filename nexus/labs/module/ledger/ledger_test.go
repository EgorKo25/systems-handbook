package ledger

import "testing"

func TestMessage(t *testing.T) {
	if got := Message("reader"); got != "ledger:v1 hello reader" {
		t.Fatalf("Message: %q", got)
	}
}
