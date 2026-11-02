package objectstudy

import (
	"context"
	"errors"
	"io"
	"os"
	"path/filepath"
)

type TransferResult struct {
	Bytes     int64
	SHA256Hex string
}

type OutputResult struct {
	TransferResult
	Published      bool
	CleanupPending bool
}

// Linux v1 requires hardlinks and directory fsync support.
// transfer succeeds only after EOF and requested integrity checks.
func WriteNewOutput(
	ctx context.Context,
	destination string,
	transfer func(io.Writer) (TransferResult, error),
) (out OutputResult, err error) {
	absolute, err := filepath.Abs(destination)
	if err != nil {
		return out, errors.New("invalid output path")
	}
	if _, statErr := os.Lstat(absolute); statErr == nil {
		return out, errors.New("output already exists")
	} else if !os.IsNotExist(statErr) {
		return out, errors.New("cannot inspect output")
	}
	directory := filepath.Dir(absolute)
	file, err := os.CreateTemp(directory, ".object-study-*.part")
	if err != nil {
		return out, errors.New("cannot create temporary output")
	}
	temporary := file.Name()
	closed := false
	defer func() {
		if !closed {
			if closeErr := file.Close(); closeErr != nil && err == nil {
				err = errors.New("temporary output close failed")
			}
		}
		if removeErr := os.Remove(temporary); removeErr != nil &&
			!os.IsNotExist(removeErr) {
			out.CleanupPending = true
			if err == nil {
				err = errors.New("temporary output cleanup failed")
			}
		}
	}()
	transferred, copyErr := transfer(file)
	out.TransferResult = transferred
	if copyErr != nil {
		return out, copyErr
	}
	if ctx.Err() != nil {
		return out, ctx.Err()
	}
	if syncErr := file.Sync(); syncErr != nil {
		return out, errors.New("temporary output sync failed")
	}
	closeErr := file.Close()
	closed = true
	if closeErr != nil {
		return out, errors.New("temporary output close failed")
	}
	if ctx.Err() != nil {
		return out, ctx.Err()
	}
	// Lstat above is only an early check. Link performs no-clobber publication.
	if linkErr := os.Link(temporary, absolute); linkErr != nil {
		return out, errors.New(
			"output publication failed; existing output preserved",
		)
	}
	out.Published = true
	parent, openErr := os.Open(directory)
	if openErr != nil {
		return out, errors.New(
			"complete output present; directory sync unavailable",
		)
	}
	syncErr := parent.Sync()
	parentCloseErr := parent.Close()
	if syncErr != nil || parentCloseErr != nil {
		return out, errors.New(
			"complete output present; directory sync failed",
		)
	}
	return out, nil
}
