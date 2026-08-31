package poller

import (
	"context"
	"errors"
	"os/exec"
	"regexp"
	"strings"
	"time"
)

var (
	// Matches SCP-like: [user@]host:owner/repo[.git]
	// host can be github.com, github.com-personal, etc.
	scpRegex = regexp.MustCompile(`^(?:[a-zA-Z0-9._-]+@)?([a-zA-Z0-9._-]+):([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+?)(?:\.git)?/?$`)

	// Matches URI-like: (https://|ssh://|git://)[credentials@]host[:port]/owner/repo[.git]
	uriRegex = regexp.MustCompile(`^(?:[a-zA-Z0-9+.-]+://)(?:[^@/]+@)?(?:[a-zA-Z0-9._-]+(?::[0-9]+)?)/([a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+?)(?:\.git)?/?$`)
)

// ParseGitRemoteURL extracts canonical "owner/repo" from any valid HTTPS or SSH git remote string.
func ParseGitRemoteURL(rawURL string) (string, error) {
	trimmed := strings.TrimSpace(rawURL)
	if trimmed == "" {
		return "", errors.New("empty git remote url")
	}

	if m := scpRegex.FindStringSubmatch(trimmed); len(m) == 3 {
		slug := strings.TrimSuffix(m[2], ".git")
		slug = strings.Trim(slug, "/")
		if strings.Contains(slug, "/") {
			return slug, nil
		}
	}

	if m := uriRegex.FindStringSubmatch(trimmed); len(m) == 2 {
		slug := strings.TrimSuffix(m[1], ".git")
		slug = strings.Trim(slug, "/")
		if strings.Contains(slug, "/") {
			return slug, nil
		}
	}

	return "", errors.New("unable to parse canonical owner/repo from git remote url: " + rawURL)
}

// DetectCurrentRepo runs git config to detect origin remote in target directory.
func DetectCurrentRepo(dir string) (string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	cmd := exec.CommandContext(ctx, "git", "config", "--get", "remote.origin.url")
	if dir != "" {
		cmd.Dir = dir
	}
	out, err := cmd.Output()
	if err != nil {
		// Fallback to git remote get-url origin
		cmdFallback := exec.CommandContext(ctx, "git", "remote", "get-url", "origin")
		if dir != "" {
			cmdFallback.Dir = dir
		}
		outFallback, errFallback := cmdFallback.Output()
		if errFallback != nil {
			return "", err
		}
		out = outFallback
	}

	return ParseGitRemoteURL(string(out))
}
