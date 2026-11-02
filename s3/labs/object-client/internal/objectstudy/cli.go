package objectstudy

import (
	"errors"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

type Invocation struct {
	ConfigFile string
	TargetID   string
	Timeout    time.Duration
	Command    string
	Source     string
	Output     string
	MaxBytes   int64
	VersionID  *string
	CreateOnly bool
	IfMatch    *string
	Key        string
}

func cliError() error {
	return errors.New("invalid command line; see object-study v1 grammar")
}

func ParseCLI(args []string) (Invocation, error) {
	in := Invocation{Timeout: 30 * time.Second}
	rootSeen := map[string]bool{}
	i := 0
	for i < len(args) && strings.HasPrefix(args[i], "--") {
		name := args[i]
		if name != "--config" && name != "--target" && name != "--timeout" {
			return in, cliError()
		}
		if rootSeen[name] || i+1 >= len(args) {
			return in, cliError()
		}
		rootSeen[name] = true
		value := args[i+1]
		switch name {
		case "--config":
			in.ConfigFile = value
		case "--target":
			in.TargetID = value
		case "--timeout":
			parsed, err := time.ParseDuration(value)
			if err != nil || parsed <= 0 || parsed > 15*time.Minute {
				return in, cliError()
			}
			in.Timeout = parsed
		}
		i += 2
	}
	if in.ConfigFile == "" || !validID(in.TargetID) || i >= len(args) {
		return in, cliError()
	}
	in.Command = args[i]
	i++
	if in.Command != "put" && in.Command != "get" && in.Command != "head" {
		return in, cliError()
	}
	seen := map[string]bool{}
	for i < len(args) && args[i] != "--" {
		name := args[i]
		if seen[name] {
			return in, cliError()
		}
		seen[name] = true
		if in.Command == "put" && name == "--create-only" {
			in.CreateOnly = true
			i++
			continue
		}
		allowed := (in.Command == "put" &&
			(name == "--source" || name == "--if-match")) ||
			(in.Command == "get" &&
				(name == "--output" || name == "--max-bytes" ||
					name == "--version-id")) ||
			(in.Command == "head" && name == "--version-id")
		if !allowed || i+1 >= len(args) {
			return in, cliError()
		}
		value := args[i+1]
		if value == "" {
			return in, cliError()
		}
		switch name {
		case "--source":
			in.Source = value
		case "--output":
			in.Output = value
		case "--if-match":
			copy := value
			in.IfMatch = &copy
		case "--version-id":
			copy := value
			in.VersionID = &copy
		case "--max-bytes":
			for _, c := range []byte(value) {
				if c < '0' || c > '9' {
					return in, cliError()
				}
			}
			parsed, err := strconv.ParseInt(value, 10, 64)
			if err != nil || parsed < 0 {
				return in, cliError()
			}
			in.MaxBytes = parsed
		}
		i += 2
	}
	if i >= len(args) || args[i] != "--" || len(args)-i != 2 {
		return in, cliError()
	}
	in.Key = args[i+1]
	if !utf8.ValidString(in.Key) || len(in.Key) == 0 ||
		len(in.Key) > 1024 || strings.ContainsRune(in.Key, 0) {
		return in, cliError()
	}
	if in.Command == "put" &&
		(in.Source == "" || in.CreateOnly == (in.IfMatch != nil)) {
		return in, cliError()
	}
	if in.Command == "get" &&
		(in.Output == "" || !seen["--max-bytes"]) {
		return in, cliError()
	}
	return in, nil
}

func validID(value string) bool {
	if len(value) == 0 || len(value) > 64 {
		return false
	}
	for i, c := range []byte(value) {
		alnum := c >= 'a' && c <= 'z' ||
			c >= 'A' && c <= 'Z' || c >= '0' && c <= '9'
		if !alnum && (i == 0 || c != '-' && c != '_') {
			return false
		}
	}
	return true
}
