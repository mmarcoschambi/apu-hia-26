package exec

import (
	"bytes"
	"context"
	"os/exec"
	"sync"
)

// PlanItem defines a structured action planned during dry-run simulation
type PlanItem struct {
	Action string `json:"action"`
	Target string `json:"target"`
	Detail string `json:"detail,omitempty"`
}

// Command holds execution parameters
type Command struct {
	Name string
	Args []string
	Dir  string
	Env  []string
}

// Result holds command execution output
type Result struct {
	Stdout   string
	Stderr   string
	ExitCode int
}

// Runner defines the interface for command execution
type Runner interface {
	Run(ctx context.Context, cmd Command) (Result, error)
	IsDryRun() bool
	GetPlan() []PlanItem
}

// RealRunner executes real OS commands
type RealRunner struct{}

func (r *RealRunner) IsDryRun() bool {
	return false
}

func (r *RealRunner) GetPlan() []PlanItem {
	return nil
}

func (r *RealRunner) Run(ctx context.Context, cmd Command) (Result, error) {
	c := exec.CommandContext(ctx, cmd.Name, cmd.Args...)
	c.Dir = cmd.Dir
	if len(cmd.Env) > 0 {
		c.Env = cmd.Env
	}
	var stdoutBuf, stderrBuf bytes.Buffer
	c.Stdout = &stdoutBuf
	c.Stderr = &stderrBuf

	err := c.Run()
	exitCode := 0
	if err != nil {
		if exitErr, ok := err.(*exec.ExitError); ok {
			exitCode = exitErr.ExitCode()
		} else {
			exitCode = 1
		}
	}

	return Result{
		Stdout:   stdoutBuf.String(),
		Stderr:   stderrBuf.String(),
		ExitCode: exitCode,
	}, err
}

// DryRunRunner logs planned commands and structured plan items without executing OS changes
type DryRunRunner struct {
	mu      sync.Mutex
	History []Command
	Plan    []PlanItem
}

func (d *DryRunRunner) IsDryRun() bool {
	return true
}

func (d *DryRunRunner) GetPlan() []PlanItem {
	d.mu.Lock()
	defer d.mu.Unlock()
	return append([]PlanItem(nil), d.Plan...)
}

func (d *DryRunRunner) RecordPlan(item PlanItem) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.Plan = append(d.Plan, item)
}

func (d *DryRunRunner) Run(ctx context.Context, cmd Command) (Result, error) {
	d.mu.Lock()
	defer d.mu.Unlock()
	d.History = append(d.History, cmd)
	d.Plan = append(d.Plan, PlanItem{
		Action: cmd.Name,
		Target: cmd.Dir,
		Detail: cmd.Name + " " + bytes.NewBufferString("").String(),
	})
	return Result{
		Stdout:   "[dry-run] simulated execution of " + cmd.Name,
		ExitCode: 0,
	}, nil
}
