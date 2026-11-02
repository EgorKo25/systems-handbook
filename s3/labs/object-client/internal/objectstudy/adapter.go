package objectstudy

import (
	"context"
	"crypto/sha256"
	"crypto/tls"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"io"
	"net"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/aws/aws-sdk-go-v2/aws"
	"github.com/aws/aws-sdk-go-v2/aws/retry"
	"github.com/aws/aws-sdk-go-v2/service/s3"
	"github.com/aws/aws-sdk-go-v2/service/s3/types"
	"github.com/aws/smithy-go/logging"
)

const MaxSinglePut int64 = 64 << 20

var errLimit = errors.New("read limit exceeded")
var errLength = errors.New("response length mismatch")
var errIntegrity = errors.New("full object checksum mismatch")

type API interface {
	PutObject(
		context.Context,
		*s3.PutObjectInput,
		...func(*s3.Options),
	) (*s3.PutObjectOutput, error)
	GetObject(
		context.Context,
		*s3.GetObjectInput,
		...func(*s3.Options),
	) (*s3.GetObjectOutput, error)
	HeadObject(
		context.Context,
		*s3.HeadObjectInput,
		...func(*s3.Options),
	) (*s3.HeadObjectOutput, error)
}

type profileFailure struct{}

func (*profileFailure) Error() string {
	return "selected profile unavailable"
}

type fileProvider struct {
	path, profile string
}

func (p fileProvider) Retrieve(ctx context.Context) (
	aws.Credentials, error,
) {
	if err := ctx.Err(); err != nil {
		return aws.Credentials{}, err
	}
	profile, err := LoadProfile(p.path, p.profile, time.Now())
	if err != nil {
		return aws.Credentials{}, &profileFailure{}
	}
	return aws.Credentials{
		AccessKeyID:     profile.AccessKeyID,
		SecretAccessKey: profile.SecretAccessKey,
		SessionToken:    profile.SessionToken,
		Source:          "object-study profile",
		CanExpire:       profile.Temporary,
		Expires:         profile.ExpiresAt,
	}, nil
}

type Adapter struct {
	api       API
	trace     *callTrace
	closeIdle func()
}

func NewAdapter(
	ctx context.Context,
	target Target,
	timeout time.Duration,
) (*Adapter, error) {
	if timeout <= 0 || timeout > 15*time.Minute ||
		validateTarget(target) != nil {
		return nil, configError()
	}
	roots, err := LoadRoots(target.CAFile)
	if err != nil {
		return nil, err
	}
	provider := aws.NewCredentialsCache(fileProvider{
		target.CredentialsFile, target.Profile,
	})
	if _, err := provider.Retrieve(ctx); err != nil {
		return nil, err
	}

	transport := &http.Transport{
		Proxy: nil,
		DialContext: (&net.Dialer{
			Timeout:   5 * time.Second,
			KeepAlive: 30 * time.Second,
		}).DialContext,
		TLSClientConfig: &tls.Config{
			RootCAs:    roots,
			MinVersion: tls.VersionTLS12,
		},
		TLSHandshakeTimeout:   5 * time.Second,
		ResponseHeaderTimeout: timeout,
		ExpectContinueTimeout: time.Second,
		MaxIdleConns:          16,
		MaxIdleConnsPerHost:   4,
		MaxConnsPerHost:       4,
		IdleConnTimeout:       30 * time.Second,
		DisableCompression:    true,
		ForceAttemptHTTP2:     true,
	}
	client := &http.Client{
		Transport: transport,
		Timeout:   timeout,
		CheckRedirect: func(
			*http.Request, []*http.Request,
		) error {
			return http.ErrUseLastResponse
		},
	}
	trace := &callTrace{}
	options := s3.Options{
		Region:       target.Region,
		Credentials:  provider,
		HTTPClient:   &tracedClient{client, trace},
		UsePathStyle: target.Addressing == "path",
		Retryer: retry.NewStandard(func(o *retry.StandardOptions) {
			o.MaxAttempts = 3
		}),
		Logger:                     logging.Nop{},
		RequestChecksumCalculation: aws.RequestChecksumCalculationWhenSupported,
		ResponseChecksumValidation: aws.ResponseChecksumValidationWhenSupported,
	}
	if target.Endpoint != "" {
		options.BaseEndpoint = aws.String(target.Endpoint)
	}
	return &Adapter{
		s3.New(options), trace, transport.CloseIdleConnections,
	}, nil
}

func (a *Adapter) Close() {
	a.closeIdle()
}

type contextReader struct {
	ctx    context.Context
	reader io.Reader
}

func (r contextReader) Read(p []byte) (int, error) {
	if err := r.ctx.Err(); err != nil {
		return 0, err
	}
	return r.reader.Read(p)
}

type trackedSource struct {
	ctx                context.Context
	file               *os.File
	trace              *callTrace
	expected, position int64
	mu                 sync.Mutex
}

func (s *trackedSource) Read(p []byte) (int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if err := s.ctx.Err(); err != nil {
		return 0, err
	}
	n, err := s.file.Read(p)
	s.position += int64(n)
	if err != nil && err != io.EOF ||
		err == io.EOF && s.position < s.expected {
		s.trace.sourceFailed()
	}
	return n, err
}

func (s *trackedSource) Seek(off int64, whence int) (int64, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if err := s.ctx.Err(); err != nil {
		return 0, err
	}
	n, err := s.file.Seek(off, whence)
	if err != nil {
		s.trace.sourceFailed()
	} else {
		s.position = n
	}
	return n, err
}

func prehash(
	ctx context.Context,
	file *os.File,
	size int64,
) (TransferResult, error) {
	var result TransferResult
	if size < 0 || size > MaxSinglePut {
		return result, errLimit
	}
	if _, err := file.Seek(0, io.SeekStart); err != nil {
		return result, err
	}
	hash := sha256.New()
	n, err := io.CopyBuffer(
		hash,
		io.LimitReader(contextReader{ctx, file}, size+1),
		make([]byte, 64<<10),
	)
	result.Bytes = n
	if err != nil {
		return result, err
	}
	if n != size {
		return result, errors.New("source size changed")
	}
	if _, err := file.Seek(0, io.SeekStart); err != nil {
		return result, err
	}
	result.SHA256Hex = hex.EncodeToString(hash.Sum(nil))
	return result, nil
}

func (a *Adapter) Put(
	ctx context.Context,
	target Target,
	in Invocation,
	file *os.File,
	prepared TransferResult,
	operationID string,
) error {
	digest, err := hex.DecodeString(prepared.SHA256Hex)
	if err != nil || len(digest) != 32 {
		return errIntegrity
	}
	input := &s3.PutObjectInput{
		Bucket: aws.String(target.Bucket),
		Key:    aws.String(in.Key),
		Body: &trackedSource{
			ctx: ctx, file: file, trace: a.trace,
			expected: prepared.Bytes,
		},
		ContentLength:     aws.Int64(prepared.Bytes),
		ContentType:       aws.String("application/octet-stream"),
		ChecksumAlgorithm: types.ChecksumAlgorithmSha256,
		ChecksumSHA256: aws.String(
			base64.StdEncoding.EncodeToString(digest),
		),
		Metadata: map[string]string{
			"operation-id": operationID,
		},
	}
	if in.CreateOnly {
		input.IfNoneMatch = aws.String("*")
	} else {
		input.IfMatch = in.IfMatch
	}
	out, err := a.api.PutObject(ctx, input)
	if err == nil && out == nil {
		return errors.New("missing PUT result")
	}
	return err
}

func copyFull(
	ctx context.Context,
	body io.ReadCloser,
	dst io.Writer,
	max int64,
	length *int64,
) (result TransferResult, err error) {
	if body == nil {
		return result, errors.New("missing GET body")
	}
	defer func() {
		closeErr := body.Close()
		if err == nil && closeErr != nil {
			err = closeErr
		}
		if err != nil {
			result.SHA256Hex = ""
		}
	}()
	if max < 0 || length != nil &&
		(*length < 0 || *length > max) {
		return result, errLimit
	}
	hash := sha256.New()
	result.Bytes, err = io.CopyBuffer(
		io.MultiWriter(dst, hash),
		io.LimitReader(contextReader{ctx, body}, max),
		make([]byte, 64<<10),
	)
	if err != nil {
		return result, err
	}
	var probe [1]byte
	n, probeErr := io.ReadFull(
		contextReader{ctx, body}, probe[:],
	)
	if n > 0 {
		return result, errLimit
	}
	if probeErr != io.EOF {
		return result, probeErr
	}
	if length != nil && result.Bytes != *length {
		return result, errLength
	}
	result.SHA256Hex = hex.EncodeToString(hash.Sum(nil))
	return result, nil
}

func (a *Adapter) Get(
	ctx context.Context,
	target Target,
	in Invocation,
	dst io.Writer,
) (TransferResult, error, string) {
	out, err := a.api.GetObject(ctx, &s3.GetObjectInput{
		Bucket:       aws.String(target.Bucket),
		Key:          aws.String(in.Key),
		VersionId:    in.VersionID,
		ChecksumMode: types.ChecksumModeEnabled,
	})
	if err != nil {
		return TransferResult{}, err, "request"
	}
	if out == nil {
		return TransferResult{},
			errors.New("missing GET result"), "body"
	}
	_, _, received := a.trace.snapshot()
	if received.status == nil ||
		*received.status != http.StatusOK ||
		out.ContentRange != nil && *out.ContentRange != "" {
		if out.Body != nil {
			out.Body.Close()
		}
		return TransferResult{},
			errors.New("unexpected partial GET response"), "body"
	}
	result, err := copyFull(
		ctx, out.Body, dst, in.MaxBytes, out.ContentLength,
	)
	if err != nil {
		return result, err, "body"
	}
	_, _, info := a.trace.snapshot()
	for _, sum := range info.checksums {
		if sum.Algorithm == "SHA256" &&
			sum.Scope == "full-object" {
			decoded, decodeErr := base64.StdEncoding.DecodeString(sum.Value)
			if decodeErr != nil ||
				hex.EncodeToString(decoded) != result.SHA256Hex {
				result.SHA256Hex = ""
				return result, errIntegrity, "body"
			}
		}
	}
	return result, nil, "body"
}

func (a *Adapter) Head(
	ctx context.Context,
	target Target,
	in Invocation,
) error {
	out, err := a.api.HeadObject(ctx, &s3.HeadObjectInput{
		Bucket:       aws.String(target.Bucket),
		Key:          aws.String(in.Key),
		VersionId:    in.VersionID,
		ChecksumMode: types.ChecksumModeEnabled,
	})
	if err == nil && out == nil {
		return errors.New("missing HEAD result")
	}
	return err
}
