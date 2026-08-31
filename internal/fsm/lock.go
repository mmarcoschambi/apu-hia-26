package fsm

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

var ErrLockTimeout = errors.New("timeout acquiring state lock: E_STATE_CONFLICT")

// IsProcessAlive checks if a process with the given PID is currently running (cross-platform)
func IsProcessAlive(pid int) bool {
	return isProcessAliveOS(pid)
}

func readLockHolderPID(lockPath string) string {
	data, err := os.ReadFile(lockPath)
	if err != nil {
		return "unknown"
	}
	lines := strings.Split(string(data), "\n")
	for _, l := range lines {
		if strings.HasPrefix(l, "pid=") {
			return strings.TrimPrefix(l, "pid=")
		}
	}
	return "unknown"
}

// AcquireFileLock attempts to acquire exclusive file lock with timeout and PID metadata
func AcquireFileLock(stateDir string, timeout time.Duration) (unlock func(), err error) {
	if stateDir == "" {
		return func() {}, nil
	}
	if timeout <= 0 {
		timeout = 10 * time.Second
	}

	if err := os.MkdirAll(stateDir, 0755); err != nil {
		return nil, fmt.Errorf("failed to create state dir: %w", err)
	}

	lockPath := filepath.Join(stateDir, ".lock")
	deadline := time.Now().Add(timeout)

	for {
		// Try to atomically create the lock file with O_EXCL
		f, err := os.OpenFile(lockPath, os.O_CREATE|os.O_EXCL|os.O_RDWR, 0600)
		if err == nil {
			// Successfully acquired lock; write PID and timestamp
			payload := fmt.Sprintf("pid=%d\nstarted=%s\n", os.Getpid(), time.Now().UTC().Format(time.RFC3339))
			_, _ = f.WriteString(payload)
			_ = f.Close()
			return func() {
				_ = os.Remove(lockPath)
			}, nil
		}

		// Inspect lock for stale condition (> 45s old)
		if info, statErr := os.Stat(lockPath); statErr == nil {
			if time.Since(info.ModTime()) > 45*time.Second {
				holder := readLockHolderPID(lockPath)
				pidNum, _ := strconv.Atoi(holder)
				if pidNum <= 0 || !IsProcessAlive(pidNum) || time.Since(info.ModTime()) > 2*time.Minute {
					_ = os.Remove(lockPath)
					continue
				}
			}
		}

		if time.Now().After(deadline) {
			holderPID := readLockHolderPID(lockPath)
			return nil, fmt.Errorf("E_STATE_CONFLICT: state locked by PID %s (timeout after %v)", holderPID, timeout)
		}

		time.Sleep(50 * time.Millisecond)
	}
}
