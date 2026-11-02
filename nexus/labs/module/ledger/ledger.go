// Package ledger is the source artifact consumed through a module proxy.
package ledger

import "fmt"

// Message is deliberately deterministic so the published source has a clear contract.
func Message(name string) string { return fmt.Sprintf("ledger:v1 hello %s", name) }
