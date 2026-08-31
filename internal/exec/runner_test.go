package exec

import (
	"context"
	"runtime"
	"testing"
	"time"
)

func TestDryRunRunner_RecordsPlanWithoutExecution(t *testing.T) {
	runner := &DryRunRunner{}

	cmd := Command{
		Name: "git",
		Args: []string{"worktree", "add", "-b", "issue-999", "/tmp/wt", "HEAD"},
		Dir:  "/tmp",
	}

	res, err := runner.Run(context.Background(), cmd)
	if err != nil {
		t.Fatalf("DryRunRunner returned unexpected error: %v", err)
	}

	if res.ExitCode != 0 {
		t.Fatalf("Expected exit code 0, got %d", res.ExitCode)
	}

	if len(runner.History) != 1 {
		t.Fatalf("Expected 1 command in history, got %d", len(runner.History))
	}

	if runner.History[0].Name != "git" {
		t.Fatalf("Expected command name 'git', got %s", runner.History[0].Name)
	}
}

func TestRealRunner_Execution(t *testing.T) {
	runner := &RealRunner{}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()

	var cmd Command
	if runtime.GOOS == "windows" {
		cmd = Command{
			Name: "cmd.exe",
			Args: []string{"/C", "echo", "hello_runner"},
		}
	} else {
		cmd = Command{
			Name: "echo",
			Args: []string{"hello_runner"},
		}
	}

	res, err := runner.Run(ctx, cmd)
	if err != nil {
		t.Fatalf("RealRunner failed: %v", err)
	}

	if res.ExitCode != 0 {
		t.Fatalf("Expected exit code 0, got %d", res.ExitCode)
	}
}
