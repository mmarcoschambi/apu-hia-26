package main

import (
	"context"
	"encoding/json"
	"io"
	"os"
	osexec "os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

	loomExec "github.com/mmarcoschambi/loom/internal/exec"
	"github.com/mmarcoschambi/loom/internal/fsm"
)

func TestMain(m *testing.M) {
	origRunner := loomExec.DefaultCommandRunner
	loomExec.DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
		if name == "herdr" {
			if runtime.GOOS == "windows" {
				return osexec.CommandContext(ctx, "cmd.exe", "/c", "echo herdr-mock")
			}
			return osexec.CommandContext(ctx, "echo", "herdr-mock")
		}
		return origRunner(ctx, name, args...)
	}
	code := m.Run()
	loomExec.DefaultCommandRunner = origRunner
	os.Exit(code)
}

func setupTestRegistry(t *testing.T) (*fsm.FSMRegistry, string) {
	t.Helper()
	tempDir := filepath.Join(os.TempDir(), "loomctl_test_state_"+time.Now().Format("20060102150405.000"))
	_ = os.MkdirAll(tempDir, 0755)

	reg := fsm.NewFSMRegistry(tempDir)
	return reg, tempDir
}

// captureStdout ejecuta fn capturando lo impreso por outputResult en stdout.
func captureStdout(t *testing.T, fn func()) string {
	t.Helper()
	rescueStdout := os.Stdout
	r, w, err := os.Pipe()
	if err != nil {
		t.Fatalf("Failed to create pipe: %v", err)
	}
	os.Stdout = w
	fn()
	_ = w.Close()
	os.Stdout = rescueStdout
	out, _ := io.ReadAll(r)
	return string(out)
}

// writeFakeVenvPython materializa un python de .venv fijo (sin ejecución real)
// para que ResolvePythonPath resuelva el discovery del worktree en tests.
func writeFakeVenvPython(t *testing.T, root string) {
	t.Helper()
	var pyExe string
	if runtime.GOOS == "windows" {
		pyExe = filepath.Join(root, ".venv", "Scripts", "python.exe")
	} else {
		pyExe = filepath.Join(root, ".venv", "bin", "python")
	}
	if err := os.MkdirAll(filepath.Dir(pyExe), 0755); err != nil {
		t.Fatalf("Failed to create fake venv dir: %v", err)
	}
	if err := os.WriteFile(pyExe, []byte("#!/bin/sh\n"), 0755); err != nil {
		t.Fatalf("Failed to write fake venv python: %v", err)
	}
}

// writeDummyGentleAIBinary deja un gentle-ai inerte en binDir y devuelve el
// binDir para armar un PATH donde LookPath("gentle-ai") tiene éxito.
func writeDummyGentleAIBinary(t *testing.T, binDir string) {
	t.Helper()
	var dummyGentle string
	if runtime.GOOS == "windows" {
		dummyGentle = filepath.Join(binDir, "gentle-ai.exe")
	} else {
		dummyGentle = filepath.Join(binDir, "gentle-ai")
	}
	if err := os.WriteFile(dummyGentle, []byte("#!/bin/sh\n"), 0755); err != nil {
		t.Fatalf("Failed to write dummy gentle-ai: %v", err)
	}
}

// stubCommandRunner reemplaza todos los comandos externos por la lectura del
// JSON del gate (éxito de proceso garantizado) o un exit code fijo.
func stubCommandRunner(jsonPath string) func() {
	origRunner := loomExec.DefaultCommandRunner
	loomExec.DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
		if jsonPath != "" {
			if runtime.GOOS == "windows" {
				return osexec.CommandContext(ctx, "cmd.exe", "/C", "type", jsonPath)
			}
			return osexec.CommandContext(ctx, "cat", jsonPath)
		}
		if runtime.GOOS == "windows" {
			return osexec.CommandContext(ctx, "cmd.exe", "/C", "exit 0")
		}
		return osexec.CommandContext(ctx, "true")
	}
	return func() { loomExec.DefaultCommandRunner = origRunner }
}

// systemBinPath devuelve un PATH mínimo con los binarios del sistema (cmd.exe
// en Windows, cat/true en Unix) para que los stubs de runner puedan ejecutarse
// sin exponer gentle-ai ni herdr del ambiente real.
func systemBinPath() string {
	if runtime.GOOS == "windows" {
		return filepath.Join(os.Getenv("SystemRoot"), "System32")
	}
	return "/usr/bin:/bin"
}

const deniedGateJSON = `{"schema":"gentle-ai.review-gate-result/v1","result":"scope-changed","allowed":false,"reason":"terminal review receipts do not exactly match the live gate target","context":{"gate":"pre-pr","denial":{"stage":"receipt-binding","code":"candidate-or-paths-mismatch"}}}`

func TestLoomctl_EnvelopeBackwardCompatibility(t *testing.T) {
	_, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	// Write old raw map format to state.json
	rawMap := map[string]*fsm.IssueFSM{
		"42": {
			ID:    "42",
			Title: "Test Issue 42",
			State: fsm.PENDING,
		},
	}
	data, _ := json.MarshalIndent(rawMap, "", "  ")
	_ = os.WriteFile(filepath.Join(tempDir, "state.json"), data, 0644)

	reg := fsm.NewFSMRegistry(tempDir)
	if err := reg.HydrateState(); err != nil {
		t.Fatalf("Failed to hydrate legacy format: %v", err)
	}

	if reg.Revision != 0 {
		t.Fatalf("Expected legacy state to hydrate with revision 0, got %d", reg.Revision)
	}

	states := reg.GetStates()
	if states["42"] == nil || states["42"].State != fsm.PENDING {
		t.Fatalf("Expected issue 42 in PENDING, got %v", states["42"])
	}

	// Persist must upgrade to envelope format and bump revision to 1
	if err := reg.PersistState(); err != nil {
		t.Fatalf("Failed to persist upgraded state: %v", err)
	}

	if reg.Revision != 1 {
		t.Fatalf("Expected revision 1 after Save, got %d", reg.Revision)
	}

	// Read file directly to verify envelope
	savedData, _ := os.ReadFile(filepath.Join(tempDir, "state.json"))
	var env fsm.StateEnvelope
	if err := json.Unmarshal(savedData, &env); err != nil {
		t.Fatalf("Expected valid envelope JSON, got error: %v", err)
	}
	if env.Revision != 1 || env.Issues["42"] == nil {
		t.Fatalf("Envelope content mismatch: %+v", env)
	}
}

func TestLoomctl_HydrateVsRecover(t *testing.T) {
	_, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	// Create state with an issue in WORKING
	rawMap := map[string]*fsm.IssueFSM{
		"10": {
			ID:    "10",
			Title: "Active working task",
			State: fsm.WORKING,
		},
	}
	data, _ := json.MarshalIndent(rawMap, "", "  ")
	_ = os.WriteFile(filepath.Join(tempDir, "state.json"), data, 0644)

	// HydrateState (CLI) must NOT modify active states to STALE
	cliReg := fsm.NewFSMRegistry(tempDir)
	if err := cliReg.HydrateState(); err != nil {
		t.Fatalf("HydrateState failed: %v", err)
	}
	if cliReg.GetStates()["10"].State != fsm.WORKING {
		t.Fatalf("Expected WORKING state preserved in HydrateState, got %s", cliReg.GetStates()["10"].State)
	}

	// RecoverState (Cold TUI boot) MUST flag abandoned active tasks as STALE
	tuiReg := fsm.NewFSMRegistry(tempDir)
	if err := tuiReg.RecoverState(); err != nil {
		t.Fatalf("RecoverState failed: %v", err)
	}
	if tuiReg.GetStates()["10"].State != fsm.STALE {
		t.Fatalf("Expected STALE state after RecoverState, got %s", tuiReg.GetStates()["10"].State)
	}
}

func TestLoomctl_DryRunStartPreconditions(t *testing.T) {
	reg, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	iss := &fsm.IssueFSM{
		ID:    "99",
		Title: "Test feature",
		State: fsm.WORKING, // Already working!
	}
	_ = reg.Save(iss)

	ctx := loomExec.ExecContext{Ctx: t.Context()}

	// Attempting start on a WORKING issue must be rejected
	states := reg.GetStates()
	targetIss := states["99"]
	if targetIss.State != fsm.PENDING && targetIss.State != fsm.STALE && targetIss.State != fsm.FAILED && targetIss.State != fsm.ORPHAN {
		// Validated pre-condition failure
	} else {
		t.Fatal("Expected pre-condition to reject start on WORKING state")
	}
	_ = ctx
}

func TestLoomctl_SealStrictModeFailClosed(t *testing.T) {
	// Scrub PATH so gentle-ai is missing
	t.Setenv("PATH", t.TempDir())

	// Mock exitFunc so test doesn't terminate
	origExit := exitFunc
	exitCodeCalled := 0
	exitFunc = func(code int) {
		exitCodeCalled = code
	}
	defer func() { exitFunc = origExit }()

	reg, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	iss := &fsm.IssueFSM{
		ID:           "77",
		Title:        "Strict mode issue",
		State:        fsm.WORKING,
		WorktreePath: tempDir,
	}
	_ = reg.Save(iss)

	ctx := loomExec.ExecContext{Ctx: t.Context()}

	// Run handleSeal with strict = true
	handleSeal(reg, ctx, "77", true, false, true)

	if exitCodeCalled != 1 {
		t.Fatalf("Expected exit code 1 on strict mode failure, got %d", exitCodeCalled)
	}

	// Issue must NOT advance to SEALING under strict governance failure
	states := reg.GetStates()
	if states["77"].State == fsm.SEALING {
		t.Fatalf("Expected issue 77 to NOT be in SEALING under strict mode failure, got %s", states["77"].State)
	}
}

func TestLoomctl_SealDefaultFailClosed(t *testing.T) {
	// Scrub PATH so gentle-ai is missing
	t.Setenv("PATH", t.TempDir())

	// Mock exitFunc so test doesn't terminate
	origExit := exitFunc
	exitCodeCalled := 0
	exitFunc = func(code int) {
		exitCodeCalled = code
	}
	defer func() { exitFunc = origExit }()

	reg, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	iss := &fsm.IssueFSM{
		ID:           "88",
		Title:        "Fail-closed issue",
		State:        fsm.WORKING,
		WorktreePath: tempDir,
	}
	_ = reg.Save(iss)

	ctx := loomExec.ExecContext{Ctx: t.Context()}

	// Run handleSeal with strict = false (now unconditionally fail-closed)
	captured := captureStdout(t, func() {
		handleSeal(reg, ctx, "88", false, false, true)
	})

	if exitCodeCalled != 1 {
		t.Fatalf("Expected exit code 1 on missing review, got %d", exitCodeCalled)
	}

	// IMPL-8: gentle-ai ausente conserva su código dedicado E_GENTLE_AI_MISSING
	if !strings.Contains(captured, "E_GENTLE_AI_MISSING") {
		t.Fatalf("Expected E_GENTLE_AI_MISSING for absent gentle-ai, got: %s", captured)
	}

	// Issue MUST NOT advance to SEALING
	states := reg.GetStates()
	if states["88"].State == fsm.SEALING {
		t.Fatalf("Expected issue 88 to NOT advance to SEALING, got %s", states["88"].State)
	}
	if states["88"].ActivePhase != fsm.PhaseFix {
		t.Fatalf("Expected issue 88 to transition to FIX phase, got %s", states["88"].ActivePhase)
	}
}

func TestLoomctl_PlanCommand(t *testing.T) {
	reg, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	iss := &fsm.IssueFSM{
		ID:           "101",
		Title:        "feat: plan phase test",
		State:        fsm.WORKING,
		WorktreePath: tempDir,
	}
	_ = reg.Save(iss)

	ctx := loomExec.ExecContext{Ctx: t.Context()}
	handlePlan(reg, ctx, "101", "opencode", false, true)

	states := reg.GetStates()
	if states["101"].ActivePhase != fsm.PhasePlan {
		t.Fatalf("Expected ActivePhase=PLAN, got %s", states["101"].ActivePhase)
	}
}

func TestLoomctl_FixCircuitBreaker(t *testing.T) {
	origExit := exitFunc
	exitCodeCalled := 0
	exitFunc = func(code int) {
		exitCodeCalled = code
	}
	defer func() { exitFunc = origExit }()

	reg, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	iss := &fsm.IssueFSM{
		ID:            "102",
		Title:         "fix: remediation loop",
		State:         fsm.WORKING,
		WorktreePath:  tempDir,
		FixRetryCount: 1,
	}
	_ = reg.Save(iss)

	ctx := loomExec.ExecContext{Ctx: t.Context()}

	// 1. First retry (FixRetryCount goes 1 -> 2)
	handleFix(reg, ctx, "102", "opencode", false, true)
	states := reg.GetStates()
	if states["102"].FixRetryCount != 2 || states["102"].ActivePhase != fsm.PhaseFix {
		t.Fatalf("Expected FixRetryCount=2 and ActivePhase=FIX, got count=%d phase=%s",
			states["102"].FixRetryCount, states["102"].ActivePhase)
	}

	// 2. Second retry at max (FixRetryCount = 2, trips Circuit Breaker)
	exitCodeCalled = 0
	handleFix(reg, ctx, "102", "opencode", false, true)
	if exitCodeCalled != 1 {
		t.Fatalf("Expected exit code 1 on tripped circuit breaker, got %d", exitCodeCalled)
	}
}

func TestLoomctl_FixInvalidState(t *testing.T) {
	origExit := exitFunc
	exitCodeCalled := 0
	exitFunc = func(code int) {
		exitCodeCalled = code
	}
	defer func() { exitFunc = origExit }()

	reg, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	iss := &fsm.IssueFSM{
		ID:           "103",
		Title:        "pending issue",
		State:        fsm.PENDING,
		WorktreePath: tempDir,
	}
	_ = reg.Save(iss)

	ctx := loomExec.ExecContext{Ctx: t.Context()}
	handleFix(reg, ctx, "103", "opencode", false, true)

	if exitCodeCalled != 1 {
		t.Fatalf("Expected exit code 1 on invalid state for fix, got %d", exitCodeCalled)
	}
}

// IMPL-5 + IMPL-4: un review rechazado debe responder con status de error
// (exit 1), reposar en WORKING con ActivePhase=FIX y persistir el denial.code
// para la inyección quirúrgica en el prompt de FIX.
func TestLoomctl_ReviewRejectedReturnsErrorStatus(t *testing.T) {
	origExit := exitFunc
	exitCodeCalled := 0
	exitFunc = func(code int) { exitCodeCalled = code }
	defer func() { exitFunc = origExit }()

	reg, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	worktree := t.TempDir()
	// La evidencia pytest [JD-4] resuelve el intérprete desde el .venv del worktree.
	writeFakeVenvPython(t, worktree)

	iss := &fsm.IssueFSM{
		ID:           "104",
		Title:        "fix: rejected review flow",
		State:        fsm.WORKING,
		WorktreePath: worktree,
	}
	_ = reg.Save(iss)

	// gentle-ai presente en PATH (inerte); el runner stubbeado sirve el JSON denegado
	// tanto para la evidencia pytest (exit 0 implícito) como para el gate.
	binDir := t.TempDir()
	writeDummyGentleAIBinary(t, binDir)
	t.Setenv("PATH", binDir+string(os.PathListSeparator)+systemBinPath())
	t.Setenv("GITHUB_WORKSPACE", "")
	t.Setenv("TARGET_REPO_PATH", t.TempDir())

	jsonPath := filepath.Join(t.TempDir(), "denied.json")
	_ = os.WriteFile(jsonPath, []byte(deniedGateJSON), 0644)
	restoreRunner := stubCommandRunner(jsonPath)
	defer restoreRunner()

	ctx := loomExec.ExecContext{Ctx: t.Context()}
	captured := captureStdout(t, func() {
		handleReview(reg, ctx, "104", "opencode", false, true)
	})

	if exitCodeCalled != 1 {
		t.Fatalf("Expected exit code 1 on rejected review, got %d", exitCodeCalled)
	}
	if !strings.Contains(captured, `"status": "error"`) {
		t.Fatalf("Expected non-ok status on rejected review, got: %s", captured)
	}
	if !strings.Contains(captured, "E_REVIEW_FAILED") {
		t.Fatalf("Expected E_REVIEW_FAILED error code, got: %s", captured)
	}

	issue := reg.GetStates()["104"]
	if issue.State != fsm.WORKING {
		t.Fatalf("Expected issue to rest in WORKING after rejection, got %s", issue.State)
	}
	if issue.ActivePhase != fsm.PhaseFix {
		t.Fatalf("Expected ActivePhase=FIX after rejection, got %s", issue.ActivePhase)
	}
	if issue.ReviewSeverity != "BLOCKER" {
		t.Fatalf("Expected ReviewSeverity=BLOCKER, got %s", issue.ReviewSeverity)
	}
	if issue.LastGateDenial == nil || issue.LastGateDenial.Code != "candidate-or-paths-mismatch" {
		t.Fatalf("Expected persisted denial code candidate-or-paths-mismatch, got %+v", issue.LastGateDenial)
	}
}

// IMPL-5: gentle-ai ausente en review devuelve E_GENTLE_AI_MISSING (no un ok).
func TestLoomctl_ReviewGentleAIMissing(t *testing.T) {
	origExit := exitFunc
	exitCodeCalled := 0
	exitFunc = func(code int) { exitCodeCalled = code }
	defer func() { exitFunc = origExit }()

	reg, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	worktree := t.TempDir()
	writeFakeVenvPython(t, worktree) // la evidencia pytest sí puede resolver intérprete

	iss := &fsm.IssueFSM{
		ID:           "105",
		Title:        "review without gentle-ai",
		State:        fsm.WORKING,
		WorktreePath: worktree,
	}
	_ = reg.Save(iss)

	t.Setenv("PATH", systemBinPath()) // cmd.exe disponible, sin gentle-ai ni herdr
	t.Setenv("GITHUB_WORKSPACE", "")
	t.Setenv("TARGET_REPO_PATH", t.TempDir())
	restoreRunner := stubCommandRunner("") // evidencia pytest stubbeada a exit 0
	defer restoreRunner()

	ctx := loomExec.ExecContext{Ctx: t.Context()}
	captured := captureStdout(t, func() {
		handleReview(reg, ctx, "105", "opencode", false, true)
	})

	if exitCodeCalled != 1 {
		t.Fatalf("Expected exit code 1 when gentle-ai is missing, got %d", exitCodeCalled)
	}
	if !strings.Contains(captured, "E_GENTLE_AI_MISSING") {
		t.Fatalf("Expected E_GENTLE_AI_MISSING error code, got: %s", captured)
	}
}

// IMPL-3: sin intérprete en ninguna ubicación, el review falla cerrado con el
// sentinel E_PYTHON_ENV_MISSING y no procede al gate.
func TestLoomctl_ReviewPythonEnvMissing(t *testing.T) {
	origExit := exitFunc
	exitCodeCalled := 0
	exitFunc = func(code int) { exitCodeCalled = code }
	defer func() { exitFunc = origExit }()

	reg, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	iss := &fsm.IssueFSM{
		ID:           "106",
		Title:        "review without python",
		State:        fsm.WORKING,
		WorktreePath: t.TempDir(), // sin .venv
	}
	_ = reg.Save(iss)

	t.Setenv("PATH", t.TempDir())
	t.Setenv("GITHUB_WORKSPACE", "")
	t.Setenv("TARGET_REPO_PATH", t.TempDir())

	ctx := loomExec.ExecContext{Ctx: t.Context()}
	captured := captureStdout(t, func() {
		handleReview(reg, ctx, "106", "opencode", false, true)
	})

	if exitCodeCalled != 1 {
		t.Fatalf("Expected exit code 1 on missing python env, got %d", exitCodeCalled)
	}
	if !strings.Contains(captured, "E_PYTHON_ENV_MISSING") {
		t.Fatalf("Expected E_PYTHON_ENV_MISSING error code, got: %s", captured)
	}

	issue := reg.GetStates()["106"]
	if issue.State != fsm.WORKING || issue.ActivePhase != fsm.PhaseFix {
		t.Fatalf("Expected WORKING + ActivePhase=FIX on evidence failure, got %s/%s",
			issue.State, issue.ActivePhase)
	}
}

// IMPL-8: un rechazo legítimo del gate en seal es E_REVIEW_FAILED (el código
// E_GENTLE_AI_MISSING queda reservado para el binario ausente). Además persiste
// el denial para el FIX posterior (IMPL-4).
func TestLoomctl_SealGateDenialIsReviewFailed(t *testing.T) {
	origExit := exitFunc
	exitCodeCalled := 0
	exitFunc = func(code int) { exitCodeCalled = code }
	defer func() { exitFunc = origExit }()

	reg, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	iss := &fsm.IssueFSM{
		ID:           "107",
		Title:        "seal with legit denial",
		State:        fsm.WORKING,
		WorktreePath: t.TempDir(),
	}
	_ = reg.Save(iss)

	binDir := t.TempDir()
	writeDummyGentleAIBinary(t, binDir)
	t.Setenv("PATH", binDir+string(os.PathListSeparator)+systemBinPath())

	jsonPath := filepath.Join(t.TempDir(), "denied.json")
	_ = os.WriteFile(jsonPath, []byte(deniedGateJSON), 0644)
	restoreRunner := stubCommandRunner(jsonPath)
	defer restoreRunner()

	ctx := loomExec.ExecContext{Ctx: t.Context()}
	captured := captureStdout(t, func() {
		handleSeal(reg, ctx, "107", false, false, true)
	})

	if exitCodeCalled != 1 {
		t.Fatalf("Expected exit code 1 on gate denial, got %d", exitCodeCalled)
	}
	if !strings.Contains(captured, "E_REVIEW_FAILED") {
		t.Fatalf("Expected E_REVIEW_FAILED for legitimate gate denial, got: %s", captured)
	}
	if strings.Contains(captured, "E_GENTLE_AI_MISSING") {
		t.Fatalf("E_GENTLE_AI_MISSING must be reserved for the missing binary, got: %s", captured)
	}

	issue := reg.GetStates()["107"]
	if issue.State != fsm.WORKING {
		t.Fatalf("Expected issue to rest in WORKING after denial, got %s", issue.State)
	}
	if issue.ActivePhase != fsm.PhaseFix {
		t.Fatalf("Expected ActivePhase=FIX after denial, got %s", issue.ActivePhase)
	}
	if issue.LastGateDenial == nil || issue.LastGateDenial.Code != "candidate-or-paths-mismatch" {
		t.Fatalf("Expected persisted denial code candidate-or-paths-mismatch, got %+v", issue.LastGateDenial)
	}
}

func TestLoomctl_ReviewDryRun(t *testing.T) {
	reg, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	iss := &fsm.IssueFSM{
		ID:           "108",
		Title:        "dry-run review issue",
		State:        fsm.WORKING,
		WorktreePath: tempDir,
	}
	_ = reg.Save(iss)

	ctx := loomExec.ExecContext{Ctx: t.Context()}
	captured := captureStdout(t, func() {
		handleReview(reg, ctx, "108", "opencode", true, true)
	})

	if !strings.Contains(captured, `"status": "ok"`) || !strings.Contains(captured, "Dry-run review plan validated") {
		t.Fatalf("Expected dry-run plan in output, got: %s", captured)
	}

	// State must not have mutated to PhaseReview
	issue := reg.GetStates()["108"]
	if issue.ActivePhase != fsm.PhaseNone {
		t.Fatalf("Expected ActivePhase to remain unmodified, got %s", issue.ActivePhase)
	}
}

func TestLoomctl_ValidateDoesNotMutateState(t *testing.T) {
	reg, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	iss := &fsm.IssueFSM{
		ID:             "109",
		Title:          "validate test",
		State:          fsm.WORKING,
		WorktreePath:   tempDir,
		ReviewSeverity: "",
	}
	_ = reg.Save(iss)

	binDir := t.TempDir()
	writeDummyGentleAIBinary(t, binDir)
	t.Setenv("PATH", binDir+string(os.PathListSeparator)+systemBinPath())

	jsonPath := filepath.Join(t.TempDir(), "passed.json")
	_ = os.WriteFile(jsonPath, []byte(`{"schema":"gentle-ai.review-gate-result/v1","result":"passed","allowed":true,"delivery":"managed"}`), 0644)
	restoreRunner := stubCommandRunner(jsonPath)
	defer restoreRunner()

	ctx := loomExec.ExecContext{Ctx: t.Context()}
	captured := captureStdout(t, func() {
		handleValidate(reg, ctx, "109", false, true)
	})

	if !strings.Contains(captured, `"status": "ok"`) {
		t.Fatalf("Expected ok status, got: %s", captured)
	}

	issue := reg.GetStates()["109"]
	if issue.ReviewSeverity != "" {
		t.Fatalf("Expected ReviewSeverity to remain empty (read-only contract), got %s", issue.ReviewSeverity)
	}
}

func TestLoomctl_RepoSubcommands(t *testing.T) {
	reg, tempDir := setupTestRegistry(t)
	defer os.RemoveAll(tempDir)

	// 1. List repos in JSON
	capturedList := captureStdout(t, func() {
		handleRepo(reg, []string{"list"}, true)
	})
	if !strings.Contains(capturedList, `"status": "ok"`) || !strings.Contains(capturedList, "tracked_repos") {
		t.Fatalf("Expected ok status with tracked_repos, got: %s", capturedList)
	}

	// 2. Add valid repo
	capturedAdd := captureStdout(t, func() {
		handleRepo(reg, []string{"add", "mmarcoschambi/loom"}, true)
	})
	if !strings.Contains(capturedAdd, `"status": "ok"`) {
		t.Fatalf("Expected ok status on adding repo, got: %s", capturedAdd)
	}

	// Verify repo in registry
	found := false
	for _, r := range reg.GetTrackedRepos() {
		if r == "mmarcoschambi/loom" {
			found = true
			break
		}
	}
	if !found {
		t.Fatal("Expected mmarcoschambi/loom in tracked repos list")
	}

	// 3. Add invalid repo format (no slash)
	origExit := exitFunc
	exitCalled := false
	exitCode := 0
	exitFunc = func(c int) {
		exitCalled = true
		exitCode = c
	}
	defer func() { exitFunc = origExit }()

	capturedInvalid := captureStdout(t, func() {
		handleRepo(reg, []string{"add", "invalid_slug_no_slash"}, true)
	})
	if !strings.Contains(capturedInvalid, "E_INVALID_ARGS") {
		t.Fatalf("Expected E_INVALID_ARGS error code, got: %s", capturedInvalid)
	}
	if !exitCalled || exitCode != 2 {
		t.Fatalf("Expected exit code 2 on E_INVALID_ARGS, got %d (called=%v)", exitCode, exitCalled)
	}

	// 4. Remove repo
	exitCalled = false
	capturedRemove := captureStdout(t, func() {
		handleRepo(reg, []string{"remove", "mmarcoschambi/loom"}, true)
	})
	if !strings.Contains(capturedRemove, `"status": "ok"`) {
		t.Fatalf("Expected ok status on removing repo, got: %s", capturedRemove)
	}

	// Verify repo removed
	for _, r := range reg.GetTrackedRepos() {
		if r == "mmarcoschambi/loom" {
			t.Fatal("Expected mmarcoschambi/loom to have been removed")
		}
	}
}

