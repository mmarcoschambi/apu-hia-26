//go:build !windows

package exec

import (
	"testing"
)

func TestKillProcessTree_Unix(t *testing.T) {
	err := KillProcessTree(-1)
	if err == nil {
		t.Fatal("Expected error for invalid PID")
	}
}
