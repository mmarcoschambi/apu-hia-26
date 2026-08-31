//go:build windows

package exec

import (
	"context"
	"errors"
	osExec "os/exec"
	"testing"
	"time"
)

func TestKillProcessTree(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping slow Windows taskkill test in short mode")
	}
	// 1.3 RED TEST for KillProcessTree
	err := KillProcessTree(999999) // Non-existent PID
	if err == nil {
		t.Fatal("Expected error when killing non-existent PID")
	}
}

func TestRunHerdrStartHeadless_Timeout(t *testing.T) {
	if testing.Short() {
		t.Skip("skipping slow Windows taskkill timeout test in short mode")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	execCtx := ExecContext{
		Ctx: ctx,
		Cwd: ".",
	}

	// Test real OS execution with a long sleep command
	oldRunner := DefaultCommandRunner
	defer func() { DefaultCommandRunner = oldRunner }()

	DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osExec.Cmd {
		return osExec.CommandContext(ctx, "powershell.exe", "-Command", "Start-Sleep -Seconds 5")
	}

	err := RunHerdrStartHeadless(execCtx, "slow_task")
	if err == nil {
		t.Fatal("Expected timeout error, got nil")
	}
	if !errors.Is(err, context.DeadlineExceeded) && err != context.DeadlineExceeded {
		t.Fatalf("Expected DeadlineExceeded, got %v", err)
	}
}
