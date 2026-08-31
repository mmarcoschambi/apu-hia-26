//go:build !windows

package exec

import (
	"fmt"
	"syscall"
)

func KillProcessTree(pid int) error {
	if pid <= 0 {
		return fmt.Errorf("invalid pid %d", pid)
	}
	// Kill the process group with negative PID
	return syscall.Kill(-pid, syscall.SIGKILL)
}
