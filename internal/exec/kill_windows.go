//go:build windows

package exec

import (
	"fmt"
	"os/exec"
)

func KillProcessTree(pid int) error {
	cmd := exec.Command("taskkill", "/F", "/T", "/PID", fmt.Sprintf("%d", pid))
	return cmd.Run()
}
