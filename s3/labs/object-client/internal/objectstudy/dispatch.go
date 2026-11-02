package objectstudy

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net"
)

type checkedWriter struct {
	writer io.Writer
	failed bool
}

func (w *checkedWriter) Write(p []byte) (int, error) {
	n, err := w.writer.Write(p)
	if n < len(p) && err == nil {
		err = io.ErrShortWrite
	}
	if err != nil {
		w.failed = true
	}
	return n, err
}

func outcomeAndCode(
	ctx context.Context,
	r *Receipt,
	trace *callTrace,
	err error,
	stage string,
	writerFailed bool,
) int {
	applyTrace(r, trace)
	calls, sourceFailed, _ := trace.snapshot()
	explicit := serviceFields(r, err)
	r.Outcome = "rejected"
	if calls > 0 {
		// Do counts cannot prove all underlying network transmissions.
		// A failed PUT after possible dispatch remains unknown,
		// including a final 412 after an earlier lost response.
		if r.Operation != nil && *r.Operation == "put" || !explicit {
			r.Outcome = "unknown"
		}
	}
	if sourceFailed || writerFailed {
		return 5
	}
	if ctx.Err() != nil ||
		errors.Is(err, context.Canceled) ||
		errors.Is(err, context.DeadlineExceeded) {
		return 4
	}
	if explicit {
		return 3
	}
	var profileErr *profileFailure
	if calls == 0 && errors.As(err, &profileErr) {
		return 2
	}
	if stage == "local" {
		return 5
	}
	var networkErr net.Error
	if errors.As(err, &networkErr) {
		return 4
	}
	if stage == "body" {
		return 5
	}
	return 4
}

func dispatch(
	ctx context.Context,
	in Invocation,
	target Target,
	a *Adapter,
	r *Receipt,
) int {
	switch in.Command {
	case "put":
		file, info, err := openRegularForRead(in.Source)
		if err != nil {
			return outcomeAndCode(
				ctx, r, a.trace, err, "local", false,
			)
		}
		prepared, hashErr := prehash(ctx, file, info.Size())
		r.LocalBytes = prepared.Bytes
		if hashErr != nil {
			file.Close()
			return outcomeAndCode(
				ctx, r, a.trace, hashErr, "local", false,
			)
		}
		r.LocalSHA256Hex = stringPtr(prepared.SHA256Hex)
		var random [16]byte
		if _, err := rand.Read(random[:]); err != nil {
			file.Close()
			return outcomeAndCode(
				ctx, r, a.trace, err, "local", false,
			)
		}
		operationID := hex.EncodeToString(random[:])
		r.OperationID = &operationID

		callErr := a.Put(
			ctx, target, in, file, prepared, operationID,
		)
		closeErr := file.Close()
		if callErr != nil {
			return outcomeAndCode(
				ctx, r, a.trace, callErr, "request", false,
			)
		}
		applyTrace(r, a.trace)
		r.Outcome = "confirmed"
		if closeErr != nil {
			return 5
		}
		return 0

	case "head":
		if err := a.Head(ctx, target, in); err != nil {
			return outcomeAndCode(
				ctx, r, a.trace, err, "request", false,
			)
		}
		applyTrace(r, a.trace)
		r.Outcome = "confirmed"
		return 0

	case "get":
		stage := "local"
		writerFailed := false
		var transferred TransferResult
		_, err := WriteNewOutput(
			ctx, in.Output,
			func(dst io.Writer) (TransferResult, error) {
				writer := &checkedWriter{writer: dst}
				var copyErr error
				transferred, copyErr, stage = a.Get(
					ctx, target, in, writer,
				)
				writerFailed = writer.failed
				return transferred, copyErr
			},
		)
		r.LocalBytes = transferred.Bytes
		if transferred.SHA256Hex != "" {
			r.LocalSHA256Hex = stringPtr(transferred.SHA256Hex)
		}
		if err != nil {
			return outcomeAndCode(
				ctx, r, a.trace, err, stage, writerFailed,
			)
		}
		applyTrace(r, a.trace)
		r.Outcome = "confirmed"
		return 0
	}
	return 2
}

func Main(
	parent context.Context,
	args []string,
	stdout, stderr io.Writer,
) int {
	receipt := Receipt{
		SchemaVersion: 1,
		Outcome:       "rejected",
	}
	code := 2
	in, err := ParseCLI(args)
	if err == nil {
		receipt.Target = stringPtr(in.TargetID)
		receipt.Operation = stringPtr(in.Command)
		ctx, cancel := context.WithTimeout(parent, in.Timeout)
		defer cancel()

		target, targetErr := LoadTarget(in.ConfigFile, in.TargetID)
		if targetErr == nil {
			adapter, adapterErr := NewAdapter(
				ctx, target, in.Timeout,
			)
			if adapterErr == nil {
				defer adapter.Close()
				code = dispatch(
					ctx, in, target, adapter, &receipt,
				)
			} else if ctx.Err() != nil {
				code = 4
			}
		} else if ctx.Err() != nil {
			code = 4
		}
	}
	if emitReceipt(stdout, receipt) != nil {
		fmt.Fprintln(
			stderr,
			"receipt output failed; inspect prior operation state before retry",
		)
		return 5
	}
	if code != 0 {
		fmt.Fprintln(
			stderr,
			"object-study operation did not complete successfully; inspect sanitized receipt",
		)
	}
	return code
}
