package objectstudy

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"sync"
	"unicode/utf8"
)

type Checksum struct {
	Algorithm string `json:"algorithm"`
	Encoding  string `json:"encoding"`
	Scope     string `json:"scope"`
	Value     string `json:"value"`
}

type Receipt struct {
	SchemaVersion  int        `json:"schema_version"`
	Target         *string    `json:"target"`
	Operation      *string    `json:"operation"`
	OperationID    *string    `json:"operation_id"`
	Outcome        string     `json:"outcome"`
	HTTPStatus     *int       `json:"http_status"`
	ServiceCode    *string    `json:"service_code"`
	RequestID      *string    `json:"request_id"`
	ETag           *string    `json:"etag"`
	VersionID      *string    `json:"version_id"`
	Checksums      []Checksum `json:"checksums"`
	LocalBytes     int64      `json:"local_bytes"`
	LocalSHA256Hex *string    `json:"local_sha256_hex"`
	Attempts       *int       `json:"attempts"`
}

func stringPtr(v string) *string {
	return &v
}

func safeField(v string) *string {
	if v == "" || len(v) > 4096 || !utf8.ValidString(v) {
		return nil
	}
	for _, r := range v {
		if r < 32 || r == 127 {
			return nil
		}
	}
	return stringPtr(v)
}

type responseInfo struct {
	status                                  *int
	requestID, etag, versionID, operationID *string
	checksums                               []Checksum
}

func responseFields(resp *http.Response) responseInfo {
	if resp == nil {
		return responseInfo{}
	}
	status := resp.StatusCode
	h := resp.Header
	info := responseInfo{
		status:      &status,
		requestID:   safeField(h.Get("X-Amz-Request-Id")),
		etag:        safeField(h.Get("ETag")),
		versionID:   safeField(h.Get("X-Amz-Version-Id")),
		operationID: safeField(h.Get("X-Amz-Meta-Operation-Id")),
		checksums:   []Checksum{},
	}
	scope, encoding := "unknown", "s3-checksum-text"
	switch h.Get("X-Amz-Checksum-Type") {
	case "FULL_OBJECT":
		scope, encoding = "full-object", "base64"
	case "COMPOSITE":
		scope, encoding = "composite", "base64-with-part-count"
	}
	for _, pair := range [][2]string{
		{"CRC32", "crc32"},
		{"CRC32C", "crc32c"},
		{"CRC64NVME", "crc64nvme"},
		{"MD5", "md5"},
		{"SHA1", "sha1"},
		{"SHA256", "sha256"},
		{"SHA512", "sha512"},
		{"XXHASH64", "xxhash64"},
		{"XXHASH3", "xxhash3"},
		{"XXHASH128", "xxhash128"},
	} {
		if value := safeField(
			h.Get("X-Amz-Checksum-" + pair[1]),
		); value != nil {
			info.checksums = append(info.checksums, Checksum{
				pair[0], encoding, scope, *value,
			})
		}
	}
	return info
}

type callTrace struct {
	mu       sync.Mutex
	calls    int
	sourceIO bool
	info     responseInfo
}

func (t *callTrace) sourceFailed() {
	t.mu.Lock()
	t.sourceIO = true
	t.mu.Unlock()
}

func (t *callTrace) snapshot() (int, bool, responseInfo) {
	t.mu.Lock()
	defer t.mu.Unlock()
	info := t.info
	info.checksums = append([]Checksum(nil), info.checksums...)
	return t.calls, t.sourceIO, info
}

type tracedClient struct {
	client *http.Client
	trace  *callTrace
}

func (c *tracedClient) Do(req *http.Request) (*http.Response, error) {
	c.trace.mu.Lock()
	c.trace.calls++
	c.trace.info = responseInfo{}
	c.trace.mu.Unlock()

	resp, err := c.client.Do(req)

	c.trace.mu.Lock()
	c.trace.info = responseFields(resp)
	c.trace.mu.Unlock()
	return resp, err
}

func applyTrace(r *Receipt, t *callTrace) {
	calls, _, info := t.snapshot()
	r.Attempts = &calls
	r.HTTPStatus, r.RequestID = info.status, info.requestID
	r.ETag, r.VersionID = info.etag, info.versionID
	r.Checksums = info.checksums
	if r.Operation != nil && *r.Operation != "put" {
		r.OperationID = info.operationID
	}
}

func serviceFields(r *Receipt, err error) bool {
	var status interface{ HTTPStatusCode() int }
	if errors.As(err, &status) {
		value := status.HTTPStatusCode()
		r.HTTPStatus = &value
	}
	var coded interface{ ErrorCode() string }
	if errors.As(err, &coded) {
		r.ServiceCode = safeField(coded.ErrorCode())
	}
	return r.ServiceCode != nil ||
		r.HTTPStatus != nil && *r.HTTPStatus >= 300
}

func emitReceipt(dst io.Writer, r Receipt) error {
	data, err := json.Marshal(r)
	if err != nil {
		return err
	}
	data = append(data, '\n')
	for len(data) > 0 {
		n, err := dst.Write(data)
		if n < 0 || n > len(data) {
			return io.ErrShortWrite
		}
		data = data[n:]
		if err != nil {
			return err
		}
		if n == 0 {
			return io.ErrShortWrite
		}
	}
	return nil
}
