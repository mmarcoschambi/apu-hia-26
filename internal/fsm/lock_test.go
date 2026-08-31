package fsm

import (
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestAcquireFileLock_SuccessAndRelease(t *testing.T) {
	tempDir := filepath.Join(os.TempDir(), "loom_test_lock_ok")
	defer os.RemoveAll(tempDir)

	unlock, err := AcquireFileLock(tempDir, 2*time.Second)
	if err != nil {
		t.Fatalf("Expected lock acquisition to succeed, got: %v", err)
	}

	lockPath := filepath.Join(tempDir, ".lock")
	if _, err := os.Stat(lockPath); os.IsNotExist(err) {
		t.Fatal("Expected .lock file to exist while held")
	}

	unlock()

	if _, err := os.Stat(lockPath); !os.IsNotExist(err) {
		t.Fatal("Expected .lock file to be removed after unlock")
	}
}

func TestAcquireFileLock_ContentionTimeout(t *testing.T) {
	tempDir := filepath.Join(os.TempDir(), "loom_test_lock_conflict")
	defer os.RemoveAll(tempDir)

	unlock1, err := AcquireFileLock(tempDir, 2*time.Second)
	if err != nil {
		t.Fatalf("Failed to acquire first lock: %v", err)
	}
	defer unlock1()

	// Second attempt with short timeout must fail with ErrLockTimeout
	_, err2 := AcquireFileLock(tempDir, 150*time.Millisecond)
	if err2 == nil {
		t.Fatal("Expected second lock attempt to fail due to contention timeout")
	}
}
