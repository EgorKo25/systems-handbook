package main

import (
	"os"
	"path/filepath"
	"sync"
	"testing"
)

func TestCounterDurableAndSerialized(t *testing.T) {
	dir := t.TempDir()
	c, err := openCounter(dir)
	if err != nil {
		t.Fatal(err)
	}
	var wg sync.WaitGroup
	for i := 0; i < 12; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if _, err := c.increment(); err != nil {
				t.Error(err)
			}
		}()
	}
	wg.Wait()
	reopened, err := openCounter(dir)
	if err != nil {
		t.Fatal(err)
	}
	if reopened.current() != 12 {
		t.Fatalf("persisted=%d, want 12", reopened.current())
	}
}
func TestCounterRejectsCorruption(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "counter"), []byte("broken"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := openCounter(dir); err == nil {
		t.Fatal("must not silently reset corrupted state")
	}
}
func TestFailedWriteDoesNotAdvanceValue(t *testing.T) {
	dir := t.TempDir()
	c, err := openCounter(dir)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(dir); err != nil {
		t.Fatal(err)
	}
	if _, err := c.increment(); err == nil {
		t.Fatal("missing directory should fail")
	}
	if c.current() != 0 {
		t.Fatal("failed write advanced memory state")
	}
}
