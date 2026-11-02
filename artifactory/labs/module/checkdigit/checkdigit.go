// Package checkdigit supplies an explicitly non-cryptographic teaching checksum.
package checkdigit

func Of(s string) int {
	total := 0
	for _, b := range []byte(s) {
		total += int(b)
	}
	return total % 10
}
