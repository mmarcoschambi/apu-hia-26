package tui

import (
	"context"
	"fmt"
	"os"
	osexec "os/exec"
	"path/filepath"
	"reflect"
	"runtime"
	"strings"
	"testing"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/mmarcoschambi/loom/internal/exec"
	"github.com/mmarcoschambi/loom/internal/fsm"
)

// 4.1 RED TEST for 'x' distinction
func TestKeyXDistinction(t *testing.T) {
	reg := fsm.NewFSMRegistry(filepath.Join(os.TempDir(), "test_tui_x"))
	defer os.RemoveAll(reg.StateDir)

	m := NewLoomModel(reg, nil)

	// Test ORPHAN
	m.SelectedIssue = &fsm.IssueFSM{ID: "test-orphan", State: fsm.ORPHAN, WorktreePath: "/tmp/fake"}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}

	_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'x'}})
	if cmd == nil {
		t.Fatal("Expected command to be returned for ORPHAN 'x'")
	}
	msg := cmd()
	if reflect.TypeOf(msg).Name() != "hardRemoveMsg" {
		t.Fatalf("Expected hardRemoveMsg, got %T", msg)
	}

	// Test STALE
	m.SelectedIssue = &fsm.IssueFSM{ID: "test-stale", State: fsm.STALE}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}

	_, cmd = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'x'}})
	if cmd == nil {
		t.Fatal("Expected non-nil command for STALE 'x' to handle transition errors")
	}

	// Execute the returned command to trigger the actual transition in the test
	msg = cmd()
	if _, ok := msg.(transitionOkMsg); !ok {
		t.Fatalf("Expected transitionOkMsg, got %T", msg)
	}

	states := reg.GetStates()
	if states["test-stale"].State != fsm.CLEANING {
		t.Fatalf("Expected state CLEANING, got %s", states["test-stale"].State)
	}
}

func TestKeyD_PhysicalRemoval(t *testing.T) {
	tempStateDir := filepath.Join(os.TempDir(), "test_tui_d_state")
	reg := fsm.NewFSMRegistry(tempStateDir)
	defer os.RemoveAll(tempStateDir)

	worktreeDir := filepath.Join(os.TempDir(), "test_worktree_d_123")
	if err := os.MkdirAll(worktreeDir, 0755); err != nil {
		t.Fatalf("Failed to create worktree dir: %v", err)
	}
	dummyFile := filepath.Join(worktreeDir, "tasks.md")
	if err := os.WriteFile(dummyFile, []byte("test"), 0644); err != nil {
		t.Fatalf("Failed to write dummy file: %v", err)
	}

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "issue-d-123",
		State:        fsm.SEALING,
		WorktreePath: worktreeDir,
	}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}

	// Press 'd'
	_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'d'}})
	if cmd == nil {
		t.Fatal("Expected non-nil command for 'd' in SEALING state")
	}

	msg := cmd()
	if _, ok := msg.(transitionOkMsg); !ok {
		t.Fatalf("Expected transitionOkMsg, got %T", msg)
	}

	// 1. Assert FSM state is DONE
	states := reg.GetStates()
	if states["issue-d-123"].State != fsm.DONE {
		t.Fatalf("Expected state DONE, got %s", states["issue-d-123"].State)
	}

	// 2. Physical File Validation: Assert directory no longer exists on disk
	if _, err := os.Stat(worktreeDir); !os.IsNotExist(err) {
		t.Fatalf("Expected worktree directory %s to be physically deleted, but it still exists", worktreeDir)
	}
}

func TestKeyV_ReviewAndSealing(t *testing.T) {
	origRunner := exec.DefaultCommandRunner
	defer func() { exec.DefaultCommandRunner = origRunner }()

	binDir := t.TempDir()
	var dummyGentle string
	if runtime.GOOS == "windows" {
		dummyGentle = filepath.Join(binDir, "gentle-ai.exe")
	} else {
		dummyGentle = filepath.Join(binDir, "gentle-ai")
	}
	_ = os.WriteFile(dummyGentle, []byte("#!/bin/sh\n"), 0755)
	t.Setenv("PATH", binDir+string(os.PathListSeparator)+os.Getenv("PATH"))

	jsonPath := filepath.Join(t.TempDir(), "response.json")
	_ = os.WriteFile(jsonPath, []byte(`{"schema":"gentle-ai.review-gate-result/v1","result":"passed","allowed":true,"delivery":"managed"}`), 0644)

	exec.DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
		if runtime.GOOS == "windows" {
			return osexec.CommandContext(ctx, "cmd.exe", "/C", "type", jsonPath)
		}
		return osexec.CommandContext(ctx, "cat", jsonPath)
	}

	tempStateDir := filepath.Join(os.TempDir(), "test_tui_v_state")
	reg := fsm.NewFSMRegistry(tempStateDir)
	defer os.RemoveAll(tempStateDir)

	worktreeDir := filepath.Join(os.TempDir(), "test_tui_v_wt")
	_ = os.MkdirAll(worktreeDir, 0755)
	defer os.RemoveAll(worktreeDir)

	// La evidencia pytest [JD-4] debe resolver un intérprete dentro del worktree;
	// el runner stubbeado sirve el JSON del gate para cualquier comando.
	writeFakeVenvPython(t, worktreeDir)

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "issue-v-64",
		State:        fsm.WORKING,
		WorktreePath: worktreeDir,
	}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}

	// Press 'v'
	_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'v'}})
	if cmd == nil {
		t.Fatal("Expected non-nil command for 'v' in WORKING state")
	}

	msg := cmd()
	if _, ok := msg.(transitionOkMsg); !ok {
		t.Fatalf("Expected transitionOkMsg, got %T", msg)
	}

	// Assert FSM state is SEALING
	states := reg.GetStates()
	if states["issue-v-64"].State != fsm.SEALING {
		t.Fatalf("Expected state SEALING, got %s", states["issue-v-64"].State)
	}
}

// writeFakeVenvPython materializa un python de .venv falso (sin ejecución real)
// para que ResolvePythonPath resuelva el discovery del worktree en tests.
func writeFakeVenvPython(t *testing.T, root string) string {
	t.Helper()
	var scriptsDir, pyExe string
	if runtime.GOOS == "windows" {
		scriptsDir = filepath.Join(root, ".venv", "Scripts")
		pyExe = filepath.Join(scriptsDir, "python.exe")
	} else {
		scriptsDir = filepath.Join(root, ".venv", "bin")
		pyExe = filepath.Join(scriptsDir, "python")
	}
	if err := os.MkdirAll(scriptsDir, 0755); err != nil {
		t.Fatalf("Failed to create fake venv dir: %v", err)
	}
	if err := os.WriteFile(pyExe, []byte("#!/bin/sh\n"), 0755); err != nil {
		t.Fatalf("Failed to write fake venv python: %v", err)
	}
	return pyExe
}

func TestKeyV_StrictModeGovernanceReject(t *testing.T) {
	// Scrub PATH so gentle-ai is deterministically missing
	t.Setenv("PATH", t.TempDir())
	// Aísla el discovery de Python del repo real (sin .venv en ninguna parte)
	t.Setenv("GITHUB_WORKSPACE", "")
	t.Setenv("TARGET_REPO_PATH", t.TempDir())
	t.Setenv("LOOM_STRICT_GOVERNANCE", "true")

	reg := fsm.NewFSMRegistry(t.TempDir())

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "issue-v-strict",
		State:        fsm.WORKING,
		WorktreePath: "/tmp/fake_v_strict",
	}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}

	// Press 'v' in strict mode
	_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'v'}})
	if cmd == nil {
		t.Fatal("Expected non-nil command for 'v' in WORKING state")
	}

	msg := cmd()
	if _, ok := msg.(hardRemoveMsg); !ok {
		t.Fatalf("Expected hardRemoveMsg on strict mode review failure, got %T", msg)
	}

	// Assert FSM state did NOT transition to SEALING
	states := reg.GetStates()
	if states["issue-v-strict"].State == fsm.SEALING {
		t.Fatalf("Expected issue to NOT be in SEALING under strict mode, got %s", states["issue-v-strict"].State)
	}
}

func TestKeyR_Revert(t *testing.T) {
	tempStateDir := filepath.Join(os.TempDir(), "test_tui_r_state")
	reg := fsm.NewFSMRegistry(tempStateDir)
	defer os.RemoveAll(tempStateDir)

	worktreeDir := filepath.Join(os.TempDir(), "test_worktree_r_64")
	if err := os.MkdirAll(worktreeDir, 0755); err != nil {
		t.Fatalf("Failed to create worktree dir: %v", err)
	}

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "issue-r-64",
		State:        fsm.WORKING,
		WorktreePath: worktreeDir,
	}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}

	// Press 'r' to revert
	_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'r'}})
	if cmd == nil {
		t.Fatal("Expected non-nil command for 'r'")
	}

	msg := cmd()
	if _, ok := msg.(transitionOkMsg); !ok {
		t.Fatalf("Expected transitionOkMsg, got %T", msg)
	}

	// 1. Assert FSM state is reset to PENDING
	states := reg.GetStates()
	if states["issue-r-64"].State != fsm.PENDING {
		t.Fatalf("Expected state PENDING, got %s", states["issue-r-64"].State)
	}

	// 2. Assert worktree directory is wiped
	if _, err := os.Stat(worktreeDir); !os.IsNotExist(err) {
		t.Fatalf("Expected worktree directory %s to be wiped, but still exists", worktreeDir)
	}
}

// 4.11 RED TEST: 's' must be rejected (toast, no exec) when 3 agents are in flight
func TestKeyS_ConcurrencyLimit(t *testing.T) {
	reg := fsm.NewFSMRegistry(filepath.Join(os.TempDir(), "test_tui_s_sema"))
	defer os.RemoveAll(reg.StateDir)

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{ID: "issue-s-4", State: fsm.PENDING}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}

	// Simulate three agents already in flight
	for i := 1; i <= fsm.MaxConcurrentAgents; i++ {
		if !reg.TryAcquire(fmt.Sprintf("issue-s-%d", i)) {
			t.Fatalf("Failed to occupy slot %d in test setup", i)
		}
	}

	updatedModel, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'s'}})
	if cmd != nil {
		t.Fatal("Expected nil command: 's' must not launch anything when the limit is reached")
	}
	loomModel, ok := updatedModel.(*LoomModel)
	if !ok {
		t.Fatalf("Expected *LoomModel, got %T", updatedModel)
	}
	if loomModel.IsBusy {
		t.Fatal("Expected IsBusy=false when the concurrency limit rejects 's'")
	}
	if !strings.Contains(loomModel.ToastMsg, "Límite alcanzado") {
		t.Fatalf("Expected limit toast, got %q", loomModel.ToastMsg)
	}
	if states := reg.GetStates(); states["issue-s-4"].State != fsm.PENDING {
		t.Fatalf("Expected issue to stay PENDING, got %s", states["issue-s-4"].State)
	}
}

// 4.12 'd' must give the semaphore slot back once teardown starts
func TestKeyD_ReleasesSemaphoreSlot(t *testing.T) {
	tempStateDir := filepath.Join(os.TempDir(), "test_tui_d_sema")
	reg := fsm.NewFSMRegistry(tempStateDir)
	defer os.RemoveAll(tempStateDir)

	worktreeDir := filepath.Join(os.TempDir(), "test_worktree_d_sema")
	if err := os.MkdirAll(worktreeDir, 0755); err != nil {
		t.Fatalf("Failed to create worktree dir: %v", err)
	}
	defer os.RemoveAll(worktreeDir)

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "issue-d-sema",
		State:        fsm.SEALING,
		WorktreePath: worktreeDir,
	}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}
	if !reg.TryAcquire("issue-d-sema") {
		t.Fatal("Failed to occupy slot in test setup")
	}

	_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'d'}})
	if cmd == nil {
		t.Fatal("Expected non-nil command for 'd' in SEALING state")
	}
	if _, ok := cmd().(transitionOkMsg); !ok {
		t.Fatal("Expected transitionOkMsg from 'd'")
	}

	if reg.ActiveAgents() != 0 {
		t.Fatalf("Expected slot released after [d], got ActiveAgents()=%d", reg.ActiveAgents())
	}
}

// 4.13 'r' must give the semaphore slot back after a successful reset
func TestKeyR_ReleasesSemaphoreSlot(t *testing.T) {
	tempStateDir := filepath.Join(os.TempDir(), "test_tui_r_sema")
	reg := fsm.NewFSMRegistry(tempStateDir)
	defer os.RemoveAll(tempStateDir)

	worktreeDir := filepath.Join(os.TempDir(), "test_worktree_r_sema")
	if err := os.MkdirAll(worktreeDir, 0755); err != nil {
		t.Fatalf("Failed to create worktree dir: %v", err)
	}
	defer os.RemoveAll(worktreeDir)

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "issue-r-sema",
		State:        fsm.WORKING,
		WorktreePath: worktreeDir,
	}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}
	if !reg.TryAcquire("issue-r-sema") {
		t.Fatal("Failed to occupy slot in test setup")
	}

	_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'r'}})
	if cmd == nil {
		t.Fatal("Expected non-nil command for 'r'")
	}
	if _, ok := cmd().(transitionOkMsg); !ok {
		t.Fatal("Expected transitionOkMsg from 'r'")
	}

	if reg.ActiveAgents() != 0 {
		t.Fatalf("Expected slot released after [r], got ActiveAgents()=%d", reg.ActiveAgents())
	}
}

func TestKeyY_ClipboardCopy(t *testing.T) {
	tempStateDir := filepath.Join(os.TempDir(), "test_tui_y_state")
	reg := fsm.NewFSMRegistry(tempStateDir)
	defer os.RemoveAll(tempStateDir)

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{
		ID:    "64",
		Title: "Test Issue",
		State: fsm.WORKING,
		Body:  "Test Body",
	}
	m.Issues = []*fsm.IssueFSM{m.SelectedIssue}

	// Press 'y'
	updatedModel, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'y'}})
	if cmd != nil {
		t.Fatal("Expected nil command for instant clipboard copy")
	}
	loomModel, ok := updatedModel.(*LoomModel)
	if !ok {
		t.Fatalf("Expected *LoomModel, got %T", updatedModel)
	}
	if loomModel.ToastMsg != "📋 Copied complete Issue #64 report to clipboard!" {
		t.Fatalf("Expected toast msg for issue 64, got %q", loomModel.ToastMsg)
	}

	// Press 'Y'
	updatedModel, _ = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'Y'}})
	loomModel, _ = updatedModel.(*LoomModel)
	if loomModel.ToastMsg != "📋 Copied Backlog list to clipboard!" {
		t.Fatalf("Expected toast msg for backlog, got %q", loomModel.ToastMsg)
	}
}

func TestKeyA_ToggleAgent(t *testing.T) {
	reg := fsm.NewFSMRegistry(filepath.Join(os.TempDir(), "test_tui_a_state"))
	defer os.RemoveAll(reg.StateDir)

	m := NewLoomModel(reg, nil)
	m.SelectedAgent = "agy"

	// Press 'a' -> should toggle to opencode
	updatedModel, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'a'}})
	if cmd != nil {
		t.Fatal("Expected nil command for instant agent switch")
	}
	loomModel, ok := updatedModel.(*LoomModel)
	if !ok {
		t.Fatalf("Expected *LoomModel, got %T", updatedModel)
	}
	if loomModel.SelectedAgent != "opencode" {
		t.Fatalf("Expected SelectedAgent to be opencode, got %s", loomModel.SelectedAgent)
	}

	// Press 'a' again -> should toggle to zcode
	updatedModel, _ = loomModel.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'a'}})
	loomModel, _ = updatedModel.(*LoomModel)
	if loomModel.SelectedAgent != "zcode" {
		t.Fatalf("Expected SelectedAgent to be zcode, got %s", loomModel.SelectedAgent)
	}

	// Press 'a' again -> should toggle to fx
	updatedModel, _ = loomModel.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'a'}})
	loomModel, _ = updatedModel.(*LoomModel)
	if loomModel.SelectedAgent != "fx" {
		t.Fatalf("Expected SelectedAgent to be fx, got %s", loomModel.SelectedAgent)
	}

	// Press 'a' again -> should toggle back to agy
	updatedModel, _ = loomModel.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'a'}})
	loomModel, _ = updatedModel.(*LoomModel)
	if loomModel.SelectedAgent != "agy" {
		t.Fatalf("Expected SelectedAgent to be agy, got %s", loomModel.SelectedAgent)
	}
}

// Governance fail-closed: 'v' with gentle-ai absent must fail-closed,
// transitioning to PhaseFix in WORKING and never advancing to SEALING.
func TestKeyV_FailClosedWhenGentleAIMissing(t *testing.T) {
	t.Setenv("PATH", t.TempDir())
	// Aísla el discovery de Python del repo real (sin .venv en ninguna parte)
	t.Setenv("GITHUB_WORKSPACE", "")
	t.Setenv("TARGET_REPO_PATH", t.TempDir())

	tempStateDir := filepath.Join(os.TempDir(), "test_tui_v_nogentle")
	reg := fsm.NewFSMRegistry(tempStateDir)
	defer os.RemoveAll(tempStateDir)

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "issue-v-ng",
		State:        fsm.WORKING,
		WorktreePath: t.TempDir(),
	}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}

	_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'v'}})
	if cmd == nil {
		t.Fatal("Expected non-nil command for 'v' in WORKING state")
	}
	msg := cmd()
	if _, ok := msg.(hardRemoveMsg); !ok {
		t.Fatalf("Expected hardRemoveMsg on failed gate, got %T", msg)
	}

	states := reg.GetStates()
	issue, exists := states["issue-v-ng"]
	if !exists {
		t.Fatal("Expected issue to exist after 'v'")
	}
	if issue.State != fsm.WORKING {
		t.Fatalf("Expected state to remain WORKING, got %s", issue.State)
	}
	if issue.ActivePhase != fsm.PhaseFix {
		t.Fatalf("Expected ActivePhase to be FIX, got %s", issue.ActivePhase)
	}
}

func TestTUI_BusyStateBlocksActionsAndRendersUI(t *testing.T) {
	reg := fsm.NewFSMRegistry(filepath.Join(os.TempDir(), "test_tui_busy_state"))
	defer os.RemoveAll(reg.StateDir)

	m := NewLoomModel(reg, nil)
	m.IsBusy = true
	m.BusyIssueID = "76"
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "76",
		State:        fsm.WORKING,
		WorktreePath: "/tmp/fake_76",
	}
	_ = reg.Save(m.SelectedIssue)

	// 1. Press 'v' -> should be blocked with toast message
	updated, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'v'}})
	if cmd != nil {
		t.Fatal("Expected nil command when pressing 'v' while busy")
	}
	model := updated.(*LoomModel)
	if !strings.Contains(model.ToastMsg, "Cannot validate while agent is actively working") {
		t.Fatalf("Expected busy toast for 'v', got: %q", model.ToastMsg)
	}

	// 2. Press 'd' -> should be blocked with toast message
	updated, cmd = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'d'}})
	if cmd != nil {
		t.Fatal("Expected nil command when pressing 'd' while busy")
	}
	model = updated.(*LoomModel)
	if !strings.Contains(model.ToastMsg, "Cannot clean while agent is actively working") {
		t.Fatalf("Expected busy toast for 'd', got: %q", model.ToastMsg)
	}

	// 3. Press 's' -> should be blocked with toast message
	updated, cmd = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'s'}})
	if cmd != nil {
		t.Fatal("Expected nil command when pressing 's' while busy")
	}
	model = updated.(*LoomModel)
	if !strings.Contains(model.ToastMsg, "Agent is busy") {
		t.Fatalf("Expected busy toast for 's', got: %q", model.ToastMsg)
	}

	// 4. Press 'r' -> should be blocked with toast message
	updated, cmd = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'r'}})
	if cmd != nil {
		t.Fatal("Expected nil command when pressing 'r' while busy")
	}
	model = updated.(*LoomModel)
	if !strings.Contains(model.ToastMsg, "Cannot reset while agent is actively working") {
		t.Fatalf("Expected busy toast for 'r', got: %q", model.ToastMsg)
	}

	// 5. Test UI Rendering in busy mode
	m.Width = 120
	m.Height = 30
	renderedView := m.View()

	if !strings.Contains(renderedView, "AGENT WORKING ON ISSUE #76") {
		t.Fatal("Expected header to show busy status in View()")
	}
	if !strings.Contains(renderedView, "actively writing") {
		t.Fatal("Expected right panel to show active agent warning in View()")
	}
}

// isolateStartEnv hace determinístico el flujo [s] de start: sin git/orca/
// herdr/gentle-ai en PATH y con repo raíz vacío, RunOrcaCreate solo hace mkdir.
func isolateStartEnv(t *testing.T) {
	t.Helper()
	t.Setenv("PATH", t.TempDir())
	t.Setenv("GITHUB_WORKSPACE", "")
	t.Setenv("TARGET_REPO_PATH", t.TempDir())
}

// IMPL-1: el flujo [s] de start debe cruzar DELEGATING -> WORKING; sin esa
// arista el issue queda varado en DELEGATING ocupando un slot de concurrencia
// y todo lo gated-en-WORKING ([v], FIX, [p]) es inalcanzable.
func TestKeyS_StartFlowReachesWorking(t *testing.T) {
	isolateStartEnv(t)

	reg := fsm.NewFSMRegistry(t.TempDir())
	issueID := "issue-s-start-1"

	homeDir, err := os.UserHomeDir()
	if err != nil {
		t.Fatalf("Failed to resolve home dir: %v", err)
	}
	worktreePath := filepath.Join(homeDir, ".loom", "worktrees", issueID)
	defer os.RemoveAll(worktreePath)

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{ID: issueID, Title: "start flow reaches working", State: fsm.PENDING}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}

	updated, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'s'}})
	if cmd != nil {
		t.Fatal("Expected nil command: 's' start flow is synchronous")
	}
	model, ok := updated.(*LoomModel)
	if !ok {
		t.Fatalf("Expected *LoomModel, got %T", updated)
	}
	if model.IsBusy {
		t.Fatal("Expected IsBusy=false after start flow completes")
	}

	issue, exists := reg.GetStates()[issueID]
	if !exists {
		t.Fatal("Expected issue to exist after 's'")
	}
	if issue.State != fsm.WORKING {
		t.Fatalf("Expected issue to reach WORKING after start flow, got %s", issue.State)
	}
	if issue.ActivePhase != fsm.PhasePlan {
		t.Fatalf("Expected ActivePhase=PLAN after start flow, got %s", issue.ActivePhase)
	}
}

// IMPL-2: sin Herdr corriendo el start flow no lanza nada; el toast de éxito
// ("Agent attached...") está prohibido en ese camino.
func TestKeyS_StartNoHerdr_ShowsErrorNotSuccess(t *testing.T) {
	isolateStartEnv(t)

	reg := fsm.NewFSMRegistry(t.TempDir())
	issueID := "issue-s-start-2"

	homeDir, _ := os.UserHomeDir()
	defer os.RemoveAll(filepath.Join(homeDir, ".loom", "worktrees", issueID))

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{ID: issueID, Title: "no herdr start", State: fsm.PENDING}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}

	updated, _ := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'s'}})
	model := updated.(*LoomModel)

	if strings.Contains(model.ToastMsg, "attached") {
		t.Fatalf("Success toast shown when nothing was dispatched: %q", model.ToastMsg)
	}
	if !strings.Contains(model.ToastMsg, "Herdr") {
		t.Fatalf("Expected visible Herdr-missing error toast, got %q", model.ToastMsg)
	}
}

// IMPL-2: el re-dispatch de fases en WORKING sin Herdr tampoco debe mostrar el
// toast de éxito ("Dispatched...") cuando no se despachó ninguna sesión.
func TestKeyS_WorkingDispatchNoHerdr_ShowsErrorNotSuccess(t *testing.T) {
	isolateStartEnv(t)

	reg := fsm.NewFSMRegistry(t.TempDir())

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "issue-s-w-1",
		State:        fsm.WORKING,
		ActivePhase:  fsm.PhaseApply,
		WorktreePath: t.TempDir(),
	}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}

	updated, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'s'}})
	if cmd != nil {
		t.Fatal("Expected nil command for synchronous phase dispatch")
	}
	model := updated.(*LoomModel)

	if model.IsBusy {
		t.Fatal("Expected IsBusy=false after dispatch attempt")
	}
	if strings.Contains(model.ToastMsg, "Dispatched") {
		t.Fatalf("Success toast shown when nothing was dispatched: %q", model.ToastMsg)
	}
	if !strings.Contains(model.ToastMsg, "Herdr") {
		t.Fatalf("Expected visible Herdr-missing error toast, got %q", model.ToastMsg)
	}
}

// IMPL-3: la evidencia pytest se corre ANTES del gate y falla cerrado cuando
// ResolvePythonPath no encuentra intérprete (ErrPythonEnvMissing).
func TestKeyV_PytestEvidenceFailsClosed(t *testing.T) {
	t.Setenv("PATH", t.TempDir())
	t.Setenv("GITHUB_WORKSPACE", "")
	t.Setenv("TARGET_REPO_PATH", t.TempDir())

	reg := fsm.NewFSMRegistry(t.TempDir())

	worktreeDir := t.TempDir() // sin .venv y sin python en PATH

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "issue-v-py",
		State:        fsm.WORKING,
		WorktreePath: worktreeDir,
	}
	if err := reg.Save(m.SelectedIssue); err != nil {
		t.Fatalf("Failed to save selected issue: %v", err)
	}

	_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'v'}})
	if cmd == nil {
		t.Fatal("Expected non-nil command for 'v' in WORKING state")
	}
	msg := cmd()
	hardMsg, ok := msg.(hardRemoveMsg)
	if !ok {
		t.Fatalf("Expected hardRemoveMsg on missing python env, got %T", msg)
	}
	if !strings.Contains(hardMsg.err.Error(), "python environment missing") {
		t.Fatalf("Expected ErrPythonEnvMissing remediation message, got %v", hardMsg.err)
	}

	issue := reg.GetStates()["issue-v-py"]
	if issue.State != fsm.WORKING {
		t.Fatalf("Expected issue to rest in WORKING, got %s", issue.State)
	}
	if issue.ActivePhase != fsm.PhaseFix {
		t.Fatalf("Expected ActivePhase=FIX after evidence failure, got %s", issue.ActivePhase)
	}
}

// IMPL-7 / JD-1: Key 'p' must only create PR when issue is SEALING && !Unmanaged.
func TestKeyP_GuardRequiresSealingAndManaged(t *testing.T) {
	reg := fsm.NewFSMRegistry(t.TempDir())
	m := NewLoomModel(reg, nil)

	// 1. Rejected in WORKING
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "p-working",
		State:        fsm.WORKING,
		WorktreePath: t.TempDir(),
	}
	_ = reg.Save(m.SelectedIssue)

	_, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'p'}})
	if cmd != nil {
		t.Fatal("Expected nil command when pressing 'p' in WORKING state")
	}

	// 2. Rejected in SEALING if Unmanaged == true
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "p-unmanaged",
		State:        fsm.SEALING,
		Unmanaged:    true,
		WorktreePath: t.TempDir(),
	}
	_ = reg.Save(m.SelectedIssue)

	_, cmd = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'p'}})
	if cmd != nil {
		t.Fatal("Expected nil command when pressing 'p' in SEALING unmanaged state")
	}

	// 3. Accepted in SEALING if Unmanaged == false
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "p-managed",
		State:        fsm.SEALING,
		Unmanaged:    false,
		WorktreePath: t.TempDir(),
	}
	_ = reg.Save(m.SelectedIssue)

	_, cmd = m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'p'}})
	if cmd == nil {
		t.Fatal("Expected non-nil command when pressing 'p' in SEALING managed state")
	}
}

func TestTUI_AccordionFolding(t *testing.T) {
	tempStateDir := t.TempDir()
	reg := fsm.NewFSMRegistry(tempStateDir)

	_, _ = reg.AddTrackedRepo("mmarcoschambi/loom")
	_, _ = reg.AddTrackedRepo("mmarcoschambi/swing-momentum-v1")

	iss1 := &fsm.IssueFSM{
		ID:    "14",
		Repo:  "mmarcoschambi/loom",
		Title: "feat(poller): multi-repo",
		State: fsm.WORKING,
	}
	iss2 := &fsm.IssueFSM{
		ID:    "68",
		Repo:  "mmarcoschambi/swing-momentum-v1",
		Title: "fix(backtest): metrics",
		State: fsm.PENDING,
	}
	_ = reg.Save(iss1)
	_ = reg.Save(iss2)

	m := NewLoomModel(reg, nil)
	m.Width = 120

	// Verify both issues present in list
	if len(m.Issues) != 2 {
		t.Fatalf("Expected 2 issues, got %d", len(m.Issues))
	}

	viewOutput := m.View()
	if !strings.Contains(viewOutput, "mmarcoschambi/loom") || !strings.Contains(viewOutput, "mmarcoschambi/swing-momentum-v1") {
		t.Fatalf("Expected both repos in view, got: %s", viewOutput)
	}
	if !strings.Contains(viewOutput, "[▼]") {
		t.Fatalf("Expected expanded chevron [▼] in view, got: %s", viewOutput)
	}

	// Currently on iss1 (loom#14). Press left arrow to collapse loom
	m.Update(tea.KeyMsg{Type: tea.KeyLeft})

	if !m.CollapsedRepos["mmarcoschambi/loom"] {
		t.Fatal("Expected mmarcoschambi/loom to be collapsed")
	}

	collapsedView := m.View()
	if !strings.Contains(collapsedView, "[▶]") {
		t.Fatalf("Expected collapsed chevron [▶] in view, got: %s", collapsedView)
	}
	if !strings.Contains(collapsedView, "hidden") {
		t.Fatalf("Expected 'hidden' indicator in view, got: %s", collapsedView)
	}

	// Selection should have shifted to the remaining visible issue (iss2)
	if m.SelectedIssue == nil || m.SelectedIssue.ID != "68" {
		t.Fatalf("Expected selected issue to be 68, got: %v", m.SelectedIssue)
	}

	// Press right arrow to expand all / selected
	m.Update(tea.KeyMsg{Type: tea.KeyRight})

	// If user was on swing, expand all collapsed repos when pressing right or expand currently selected
	// Let's expand loom
	m.CollapsedRepos["mmarcoschambi/loom"] = false
	expandedView := m.View()
	if !strings.Contains(expandedView, "[▼] mmarcoschambi/loom") {
		t.Fatalf("Expected expanded header [▼] mmarcoschambi/loom, got: %s", expandedView)
	}
}

// Issue #31: Persistent validation indicator and sticky sealed banner tests
func TestKeyV_SetsBusyStateAndRendersProgress(t *testing.T) {
	reg := fsm.NewFSMRegistry(t.TempDir())
	worktreeDir := t.TempDir()

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "31",
		Title:        "feat(tui): persistent validation",
		State:        fsm.WORKING,
		WorktreePath: worktreeDir,
	}
	_ = reg.Save(m.SelectedIssue)

	// Press 'v' to initiate validation
	updatedModel, cmd := m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'v'}})
	if cmd == nil {
		t.Fatal("Expected non-nil command when pressing 'v' on WORKING issue")
	}
	loomModel, ok := updatedModel.(*LoomModel)
	if !ok {
		t.Fatalf("Expected *LoomModel, got %T", updatedModel)
	}

	// 1. Assert IsBusy and BusyIssueID are set
	if !loomModel.IsBusy {
		t.Fatal("Expected IsBusy=true upon pressing 'v'")
	}
	if loomModel.BusyIssueID != "31" {
		t.Fatalf("Expected BusyIssueID='31', got %q", loomModel.BusyIssueID)
	}

	// 2. Assert View renders persistent busy validation telemetry
	m.Width = 120
	m.Height = 30
	viewOutput := loomModel.View()
	if !strings.Contains(viewOutput, "VALIDATING & SEALING") && !strings.Contains(viewOutput, "WORKING ON ISSUE #31") {
		t.Fatalf("Expected persistent validation indicator in header/view, got: %s", viewOutput)
	}

	// 3. Navigation keys (e.g. 'j') must NOT wipe the persistent busy state
	updatedModel, _ = loomModel.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'j'}})
	loomModel = updatedModel.(*LoomModel)
	if !loomModel.IsBusy || loomModel.BusyIssueID != "31" {
		t.Fatalf("Expected IsBusy to persist across keystrokes, got IsBusy=%v, BusyIssueID=%q", loomModel.IsBusy, loomModel.BusyIssueID)
	}
}

func TestKeyV_SealedStateRendersStickyBanner(t *testing.T) {
	reg := fsm.NewFSMRegistry(t.TempDir())
	worktreeDir := t.TempDir()

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{
		ID:           "31",
		Title:        "feat(tui): persistent validation",
		State:        fsm.SEALING,
		WorktreePath: worktreeDir,
	}
	_ = reg.Save(m.SelectedIssue)

	m.Width = 120
	m.Height = 30
	viewOutput := m.View()

	// Assert sticky SEALED banner and guidance in inspector
	if !strings.Contains(viewOutput, "SEALED") {
		t.Fatalf("Expected sticky SEALED banner in inspector, got: %s", viewOutput)
	}
	if !strings.Contains(viewOutput, "[p]") || !strings.Contains(viewOutput, "[d]") {
		t.Fatalf("Expected [p] PR and [d] Done guidance in inspector, got: %s", viewOutput)
	}

	// Pressing a navigation key should NOT clear the inspector sealed banner
	m.Update(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'k'}})
	viewAfterKey := m.View()
	if !strings.Contains(viewAfterKey, "SEALED") {
		t.Fatalf("Expected sticky SEALED banner to persist after keystroke, got: %s", viewAfterKey)
	}
}

func TestKeyV_FailureRendersPinnedAlert(t *testing.T) {
	reg := fsm.NewFSMRegistry(t.TempDir())
	worktreeDir := t.TempDir()

	m := NewLoomModel(reg, nil)
	m.SelectedIssue = &fsm.IssueFSM{
		ID:             "31",
		Title:          "feat(tui): persistent validation",
		State:          fsm.WORKING,
		ActivePhase:    fsm.PhaseFix,
		ReviewSeverity: "BLOCKER",
		WorktreePath:   worktreeDir,
	}
	_ = reg.Save(m.SelectedIssue)

	m.Width = 120
	m.Height = 30
	viewOutput := m.View()

	// Assert pinned failure / blocker alert renders in inspector
	if !strings.Contains(viewOutput, "BLOCKER") {
		t.Fatalf("Expected pinned BLOCKER severity badge in inspector, got: %s", viewOutput)
	}
}

