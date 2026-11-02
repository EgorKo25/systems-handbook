package main

import (
	"context"
	"os"
	"os/signal"
	"syscall"

	"example.com/systems-handbook/object-study/internal/objectstudy"
)

func run() int {
	ctx, stop := signal.NotifyContext(
		context.Background(),
		os.Interrupt,
		syscall.SIGTERM,
	)
	defer stop()
	return objectstudy.Main(
		ctx, os.Args[1:], os.Stdout, os.Stderr,
	)
}

func main() {
	os.Exit(run())
}
