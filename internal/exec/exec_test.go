package exec

import (
	"context"
	"errors"
	"os"
	osexec "os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

func TestRunHerdrStartHeadless_EnvLeakage(t *testing.T) {
	// GIVEN parent environment has GITHUB_TOKEN set
	os.Setenv("GITHUB_TOKEN", "secret_token_123")
	defer os.Unsetenv("GITHUB_TOKEN")

	allowlist := []string{"HOME", "PATH", "TEMP"}
	env := BuildEnv(allowlist)

	for _, e := range env {
		if strings.HasPrefix(strings.ToUpper(e), "GITHUB_TOKEN=") {
			t.Fatalf("GITHUB_TOKEN leaked into isolated environment: %s", e)
		}
	}
}

func TestWriteTasksMD_PathTraversal(t *testing.T) {
	// 1.2 RED TEST for Path Traversal
	homeDir, _ := os.UserHomeDir()
	validCwd := filepath.Join(homeDir, ".loom", "worktrees", "wt-123")
	invalidCwd := filepath.Join(homeDir, ".loom", "worktrees", "..", "..", "etc")

	// Create valid cwd so os.WriteFile doesn't fail due to missing dir
	if err := os.MkdirAll(validCwd, 0755); err != nil {
		t.Fatalf("Failed to create valid cwd: %v", err)
	}
	defer os.RemoveAll(validCwd)

	ctxValid := ExecContext{Ctx: context.Background(), Cwd: validCwd}
	ctxInvalid := ExecContext{Ctx: context.Background(), Cwd: invalidCwd}
	payload := IssuePayload{}

	err := WriteTasksMD(ctxInvalid, payload)
	if err == nil {
		t.Fatalf("Expected WriteTasksMD to reject invalid cwd %s", invalidCwd)
	}

	err = WriteTasksMD(ctxValid, payload)
	if err != nil {
		t.Fatalf("Expected valid path to succeed, got error: %v", err)
	}
}

func TestRunOrcaCreate_PathTraversal(t *testing.T) {
	// 1.2 RED TEST for Path Traversal
	homeDir, _ := os.UserHomeDir()
	invalidCwd := filepath.Join(homeDir, ".loom", "worktrees", "..", "..", "etc")

	ctxInvalid := ExecContext{Ctx: context.Background(), Cwd: invalidCwd}

	err := RunOrcaCreate(ctxInvalid, "issue-id")
	if err == nil {
		t.Fatalf("Expected RunOrcaCreate to reject invalid cwd %s", invalidCwd)
	}
}

func TestRunOrcaRemove_PhysicalDeletion(t *testing.T) {
	testDir := filepath.Join(os.TempDir(), "test_orca_remove_dir")
	if err := os.MkdirAll(testDir, 0755); err != nil {
		t.Fatalf("Failed to create test dir: %v", err)
	}
	testFile := filepath.Join(testDir, "test.txt")
	if err := os.WriteFile(testFile, []byte("data"), 0644); err != nil {
		t.Fatalf("Failed to write test file: %v", err)
	}

	ctxValid := ExecContext{Cwd: testDir}
	err := RunOrcaRemove(ctxValid)
	if err != nil {
		t.Fatalf("Expected RunOrcaRemove to succeed, got %v", err)
	}

	if _, err := os.Stat(testDir); !os.IsNotExist(err) {
		t.Fatalf("Expected %s to be deleted physically, but it still exists", testDir)
	}

	// Test path traversal rejection
	homeDir, _ := os.UserHomeDir()
	invalidCwd := filepath.Join(homeDir, ".loom", "worktrees", "..", "..", "etc")
	ctxInvalid := ExecContext{Cwd: invalidCwd}
	err = RunOrcaRemove(ctxInvalid)
	if err == nil {
		t.Fatalf("Expected RunOrcaRemove to reject path traversal %s", invalidCwd)
	}
}

func TestReadRecentLogs(t *testing.T) {
	tempDir := t.TempDir()
	logFile := filepath.Join(tempDir, "execution.log")
	lines := "line 1\nline 2\nline 3\nline 4\nline 5\n"
	if err := os.WriteFile(logFile, []byte(lines), 0644); err != nil {
		t.Fatalf("Failed to write log file: %v", err)
	}

	recent := ReadRecentLogs(tempDir, 2)
	expected := "line 4\nline 5"
	if recent != expected {
		t.Fatalf("Expected %q, got %q", expected, recent)
	}

	// Test non-existent dir
	empty := ReadRecentLogs("/non/existent/path", 5)
	if empty != "" {
		t.Fatalf("Expected empty string for non-existent path, got %q", empty)
	}
}

func TestRunHerdrStartHeadless_PropagatesErrors(t *testing.T) {
	tempDir := t.TempDir()
	origRunner := DefaultCommandRunner
	defer func() { DefaultCommandRunner = origRunner }()

	// Mock a failing command (e.g. exit status 1)
	DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
		if runtime.GOOS == "windows" {
			return osexec.CommandContext(ctx, "cmd.exe", "/C", "exit 1")
		}
		return osexec.CommandContext(ctx, "sh", "-c", "exit 1")
	}

	ctx := ExecContext{
		Ctx: context.Background(),
		Cwd: tempDir,
	}

	err := RunHerdrStartHeadless(ctx, "test-task")
	if err == nil {
		t.Fatal("Expected RunHerdrStartHeadless to strictly propagate process failure, but got nil (error swallowed)")
	}
	if !strings.Contains(err.Error(), "agent execution failed") {
		t.Fatalf("Expected error to contain 'agent execution failed', got: %v", err)
	}
}

// Governance must fail closed: with gentle-ai absent from PATH, review
// reports ErrGentleAINotInstalled instead of a silent pass.
func TestRunGentleReviewMode_NotInstalled(t *testing.T) {
	t.Setenv("PATH", t.TempDir())

	_, err := RunGentleReviewMode(ExecContext{Ctx: context.Background(), Cwd: t.TempDir()})
	if !errors.Is(err, ErrGentleAINotInstalled) {
		t.Fatalf("Expected ErrGentleAINotInstalled, got %v", err)
	}
}

func systemBinPath() string {
	if runtime.GOOS == "windows" {
		sysRoot := os.Getenv("SystemRoot")
		if sysRoot == "" {
			sysRoot = `C:\Windows`
		}
		return filepath.Join(sysRoot, "System32")
	}
	return "/usr/bin:/bin"
}

func writeDummyBinary(t *testing.T, dir string, name string) string {
	t.Helper()
	var binPath string
	if runtime.GOOS == "windows" {
		binPath = filepath.Join(dir, name+".exe")
	} else {
		binPath = filepath.Join(dir, name)
	}
	if err := os.WriteFile(binPath, []byte("#!/bin/sh\nexit 0\n"), 0755); err != nil {
		t.Fatalf("Failed to write dummy binary %s: %v", name, err)
	}
	return binPath
}

func TestRunGentleReviewMode_ValidReceiptPasses(t *testing.T) {
	origRunner := DefaultCommandRunner
	defer func() { DefaultCommandRunner = origRunner }()

	binDir := t.TempDir()
	writeDummyBinary(t, binDir, "gentle-ai")
	t.Setenv("PATH", binDir+string(os.PathListSeparator)+systemBinPath())

	jsonPath := filepath.Join(t.TempDir(), "response.json")
	_ = os.WriteFile(jsonPath, []byte(`{"schema":"gentle-ai.review-gate-result/v1","result":"passed","allowed":true,"delivery":"managed"}`), 0644)

	DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
		if runtime.GOOS == "windows" {
			return osexec.CommandContext(ctx, "cmd.exe", "/C", "type", jsonPath)
		}
		return osexec.CommandContext(ctx, "cat", jsonPath)
	}

	gateRes, err := RunGentleReviewMode(ExecContext{Ctx: context.Background(), Cwd: t.TempDir()})
	if err != nil {
		t.Fatalf("Expected RunGentleReviewMode to pass on allowed: true, got %v", err)
	}
	if !gateRes.Allowed {
		t.Fatal("Expected gateRes.Allowed to be true")
	}
}

// Per the gentle-ai review-integration contract, a gate result with
// delivery: "disabled/unmanaged" is NOT a rejection — it is a pass-through
// to ordinary repository policy. loomctl must not treat it as an error,
// otherwise administrative operations (seal/clean) deadlock when the
// kill switch is off.
func TestRunGentleReviewMode_DisabledUnmanagedPassesThrough(t *testing.T) {
	origRunner := DefaultCommandRunner
	defer func() { DefaultCommandRunner = origRunner }()

	binDir := t.TempDir()
	writeDummyBinary(t, binDir, "gentle-ai")
	t.Setenv("PATH", binDir+string(os.PathListSeparator)+systemBinPath())

	jsonPath := filepath.Join(t.TempDir(), "response.json")
	_ = os.WriteFile(jsonPath, []byte(`{"schema":"gentle-ai.review-gate-result/v1","result":"invalidated","allowed":false,"action":"repository-policy","delivery":"disabled/unmanaged","reason":"receipt-driven development is disabled and no receipt governs this candidate, so delivery follows ordinary repository policy"}`), 0644)

	DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
		if runtime.GOOS == "windows" {
			return osexec.CommandContext(ctx, "cmd.exe", "/C", "type", jsonPath)
		}
		return osexec.CommandContext(ctx, "cat", jsonPath)
	}

	gateRes, err := RunGentleReviewMode(ExecContext{Ctx: context.Background(), Cwd: t.TempDir()})
	if err != nil {
		t.Fatalf("Expected RunGentleReviewMode to pass-through disabled/unmanaged, got error: %v", err)
	}
	if gateRes.Allowed {
		t.Fatal("Expected gateRes.Allowed to remain false (no fabricated approval)")
	}
	if gateRes.Delivery != "disabled/unmanaged" {
		t.Fatalf("Expected gateRes.Delivery to be disabled/unmanaged, got: %s", gateRes.Delivery)
	}
}

// Non-disabled rejections (e.g. delivery: "denied", "blocked") must still
// fail closed — only disabled/unmanaged gets the pass-through.
func TestRunGentleReviewMode_DeniedDeliveryStillFails(t *testing.T) {
	origRunner := DefaultCommandRunner
	defer func() { DefaultCommandRunner = origRunner }()

	binDir := t.TempDir()
	writeDummyBinary(t, binDir, "gentle-ai")
	t.Setenv("PATH", binDir+string(os.PathListSeparator)+systemBinPath())

	jsonPath := filepath.Join(t.TempDir(), "response.json")
	_ = os.WriteFile(jsonPath, []byte(`{"schema":"gentle-ai.review-gate-result/v1","result":"invalidated","allowed":false,"action":"retry","delivery":"denied","reason":"real review gate rejection"}`), 0644)

	DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
		if runtime.GOOS == "windows" {
			return osexec.CommandContext(ctx, "cmd.exe", "/C", "type", jsonPath)
		}
		return osexec.CommandContext(ctx, "cat", jsonPath)
	}

	_, err := RunGentleReviewMode(ExecContext{Ctx: context.Background(), Cwd: t.TempDir()})
	if err == nil {
		t.Fatal("Expected RunGentleReviewMode to fail when delivery is denied, got nil")
	}
}

// Every external command context must carry a deadline: explicit caller ctx
// (still capped), CommandTimeout override, and per-operation fallback.
func TestCommandCtx_AlwaysBounded(t *testing.T) {
	cases := []struct {
		name    string
		execCtx ExecContext
	}{
		{"nil ctx falls back to default timeout", ExecContext{}},
		{"caller ctx is kept and capped", ExecContext{Ctx: context.Background()}},
		{"command timeout overrides fallback", ExecContext{CommandTimeout: time.Minute}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			runCtx, cancel := commandCtx(tc.execCtx, quickCmdTimeout)
			defer cancel()
			if _, ok := runCtx.Deadline(); !ok {
				t.Fatal("Expected bounded context with deadline, got none")
			}
		})
	}
}

func TestResolveTargetRepoDir(t *testing.T) {
	t.Run("Env TARGET_REPO_PATH override", func(t *testing.T) {
		t.Setenv("TARGET_REPO_PATH", `C:\test\target\repo`)
		dir := ResolveTargetRepoDir()
		if !strings.Contains(dir, "test") {
			t.Fatalf("Expected target repo override, got %s", dir)
		}
	})

	t.Run("Fallback to CWD", func(t *testing.T) {
		t.Setenv("TARGET_REPO_PATH", "")
		t.Setenv("LOOM_TARGET_REPO_PATH", "")
		dir := ResolveTargetRepoDir()
		if dir == "" {
			t.Fatal("Expected non-empty default dir")
		}
	})
}

func TestWriteOpenSpecScaffold_Conditional(t *testing.T) {
	homeDir, _ := os.UserHomeDir()
	validCwd := filepath.Join(homeDir, ".loom", "worktrees", "wt-spec-test")
	if err := os.MkdirAll(validCwd, 0755); err != nil {
		t.Fatalf("Failed to create valid cwd: %v", err)
	}
	defer os.RemoveAll(validCwd)

	ctx := ExecContext{Ctx: context.Background(), Cwd: validCwd}

	t.Run("Simple bug only creates tasks.md", func(t *testing.T) {
		payload := IssuePayload{
			Title:  "fix(ui): Fix typo in footer",
			Body:   "Simple fix",
			Labels: []string{"bug"},
		}
		if err := WriteOpenSpecScaffold(ctx, "99", payload); err != nil {
			t.Fatalf("WriteOpenSpecScaffold failed: %v", err)
		}
		if _, err := os.Stat(filepath.Join(validCwd, "tasks.md")); err != nil {
			t.Fatalf("Expected root tasks.md to exist: %v", err)
		}
		if _, err := os.Stat(filepath.Join(validCwd, "openspec", "changes", "issue-99")); !os.IsNotExist(err) {
			t.Fatal("Expected openspec change dir NOT to exist for simple bug")
		}
	})

	t.Run("Complex feat creates full 4-file OpenSpec suite", func(t *testing.T) {
		payload := IssuePayload{
			Title:  "feat(playbook): Live reload for Markdown in Avalonia",
			Body:   "Detailed requirements",
			Labels: []string{"feat", "architecture"},
		}
		if err := WriteOpenSpecScaffold(ctx, "100", payload); err != nil {
			t.Fatalf("WriteOpenSpecScaffold failed: %v", err)
		}
		changeDir := filepath.Join(validCwd, "openspec", "changes", "issue-100")
		files := []string{
			filepath.Join(changeDir, "proposal.md"),
			filepath.Join(changeDir, "design.md"),
			filepath.Join(changeDir, "specs", "spec.md"),
			filepath.Join(changeDir, "tasks.md"),
		}
		for _, f := range files {
			if _, err := os.Stat(f); err != nil {
				t.Fatalf("Expected %s to exist, got: %v", f, err)
			}
		}
	})

	t.Run("Path traversal is rejected", func(t *testing.T) {
		invalidCwd := filepath.Join(homeDir, ".loom", "worktrees", "..", "..", "etc")
		invalidCtx := ExecContext{Ctx: context.Background(), Cwd: invalidCwd}
		err := WriteOpenSpecScaffold(invalidCtx, "101", IssuePayload{Title: "feat: bad"})
		if err == nil {
			t.Fatal("Expected path traversal rejection, got nil")
		}
	})
}

func TestBuildPromptForIssue(t *testing.T) {
	t.Run("Simple bug prompt", func(t *testing.T) {
		p := IssuePayload{Title: "fix: typo in header", Labels: []string{"bug"}}
		prompt := BuildPromptForIssue("42", p, "", 0)
		if !strings.Contains(prompt, "tasks.md") || strings.Contains(prompt, "openspec") {
			t.Fatalf("Expected simple prompt, got: %s", prompt)
		}
	})

	t.Run("Complex feat prompt invokes sdd-apply and OpenSpec", func(t *testing.T) {
		p := IssuePayload{Title: "feat(auth): Add OAuth2 flow", Labels: []string{"feat"}}
		prompt := BuildPromptForIssue("43", p, "", 0)
		if !strings.Contains(prompt, "openspec/changes/issue-43/") {
			t.Fatalf("Expected openspec path in prompt, got: %s", prompt)
		}
		if !strings.Contains(prompt, "sdd-apply") {
			t.Fatalf("Expected sdd-apply skill in prompt, got: %s", prompt)
		}
	})

	// IMPL-4: con review.log previo el prompt de FIX debe llevar el reintento
	// REAL del issue y el denial.code persistido (no un retryCount hardcodeado).
	t.Run("review.log plus persisted denial injects real retry count", func(t *testing.T) {
		wt := t.TempDir()
		if err := os.WriteFile(filepath.Join(wt, "review.log"), []byte("denied"), 0644); err != nil {
			t.Fatalf("Failed to write review.log: %v", err)
		}
		p := IssuePayload{Title: "fix: remediation loop"}
		denied := GentleGateResult{
			Allowed: false,
			Reason:  "receipt mismatch",
			Context: &GentleContext{Denial: &GentleDenial{Code: "candidate-or-paths-mismatch"}},
		}

		first := BuildPromptForIssue("74", p, wt, 1, denied)
		if !strings.Contains(first, "candidate-or-paths-mismatch") {
			t.Fatalf("Expected denial code in FIX prompt, got: %s", first)
		}
		if !strings.Contains(first, "1/2") || strings.Contains(first, "2/2") {
			t.Fatalf("Expected real retry count 1/2 on first fix, got: %s", first)
		}

		second := BuildPromptForIssue("74", p, wt, 2, denied)
		if !strings.Contains(second, "candidate-or-paths-mismatch") {
			t.Fatalf("Expected denial code in FIX prompt, got: %s", second)
		}
		if !strings.Contains(second, "2/2") {
			t.Fatalf("Expected real retry count 2/2 on second fix, got: %s", second)
		}
	})

	t.Run("review.log without persisted denial still uses real retry count", func(t *testing.T) {
		wt := t.TempDir()
		if err := os.WriteFile(filepath.Join(wt, "review.log"), []byte("denied"), 0644); err != nil {
			t.Fatalf("Failed to write review.log: %v", err)
		}
		p := IssuePayload{Title: "fix: no denial payload"}
		prompt := BuildPromptForIssue("75", p, wt, 2)
		if !strings.Contains(prompt, "2/2") || strings.Contains(prompt, "1/2") {
			t.Fatalf("Expected real retry count 2/2 without denial, got: %s", prompt)
		}
	})
}

func TestGateDenialRoundTrip(t *testing.T) {
	gr := GentleGateResult{
		Allowed: false,
		Result:  "scope-changed",
		Reason:  "receipt mismatch",
		Context: &GentleContext{Gate: "pre-pr", Denial: &GentleDenial{Stage: "receipt-binding", Code: "candidate-or-paths-mismatch"}},
	}

	code, result, reason := GateDenialInfo(gr)
	if code != "candidate-or-paths-mismatch" || result != "scope-changed" || reason != "receipt mismatch" {
		t.Fatalf("GateDenialInfo mismatch: code=%q result=%q reason=%q", code, result, reason)
	}

	// Nil-safe: sin contexto no debe panic y debe exponer result+reason.
	nilCtxCode, nilCtxResult, nilCtxReason := GateDenialInfo(GentleGateResult{Allowed: false, Result: "denied", Reason: "no receipts"})
	if nilCtxCode != "" || nilCtxResult != "denied" || nilCtxReason != "no receipts" {
		t.Fatalf("GateDenialInfo nil-context mismatch: code=%q result=%q reason=%q", nilCtxCode, nilCtxResult, nilCtxReason)
	}

	rebuilt := GateResultFromDenial(code, result, reason)
	if rebuilt.Allowed {
		t.Fatal("Expected rebuilt gate result to be denied")
	}
	if rebuilt.Context == nil || rebuilt.Context.Denial == nil || rebuilt.Context.Denial.Code != code {
		t.Fatalf("Expected rebuilt denial code %s, got %+v", code, rebuilt.Context)
	}
	if rebuilt.Result != result || rebuilt.Reason != reason {
		t.Fatalf("Rebuilt mismatch: %+v", rebuilt)
	}
}

func TestToWslPath(t *testing.T) {
	cases := []struct {
		winPath  string
		expected string
	}{
		{`C:\Users\test\.loom\worktrees\1`, "/mnt/c/Users/test/.loom/worktrees/1"},
		{`D:\projects\app`, "/mnt/d/projects/app"},
		{`/mnt/c/already/wsl`, "/mnt/c/already/wsl"},
	}

	for _, tc := range cases {
		result := ToWslPath(tc.winPath)
		if result != tc.expected {
			t.Fatalf("ToWslPath(%q) = %q; expected %q", tc.winPath, result, tc.expected)
		}
	}
}

func TestBuildAgentCmd_Fx(t *testing.T) {
	ctx := ExecContext{Cwd: filepath.Join(t.TempDir(), "wt-42")}
	cmd := BuildAgentCmd(ctx, "implement feature", "fx")
	if cmd == nil {
		t.Fatal("Expected non-nil command for fx agent")
	}

	cmdStr := strings.Join(cmd.Args, " ")
	if runtime.GOOS == "windows" {
		if !strings.Contains(cmdStr, "wsl") && !strings.Contains(cmd.Path, "wsl") {
			t.Fatalf("Expected cmd to invoke wsl on Windows, got %s (args: %v)", cmd.Path, cmd.Args)
		}
	} else {
		if !strings.Contains(cmdStr, "fx") && !strings.Contains(cmd.Path, "fx") {
			t.Fatalf("Expected cmd to invoke fx on Linux, got %s (args: %v)", cmd.Path, cmd.Args)
		}
	}
}

// containsCall verifica si una invocación grabada coincide exactamente con la esperada.
func containsCall(calls [][]string, expected []string) bool {
	for _, c := range calls {
		if len(c) == len(expected) {
			match := true
			for i := range c {
				if c[i] != expected[i] {
					match = false
					break
				}
			}
			if match {
				return true
			}
		}
	}
	return false
}

// El TUI de fx no admite flags de prompt y Herdr no registra el kind fx:
// RunHerdrAgentStart debe inyectar el prompt a nivel de pane (wait-output,
// send-text, send-keys) y saltear `herdr agent start`.
func TestRunHerdrAgentStart_FxInjectsPromptViaPane(t *testing.T) {
	tempDir := t.TempDir()
	origRunner := DefaultCommandRunner
	defer func() { DefaultCommandRunner = origRunner }()

	var calls [][]string
	DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
		calls = append(calls, append([]string{name}, args...))
		if runtime.GOOS == "windows" {
			return osexec.CommandContext(ctx, "cmd.exe", "/C", "exit 0")
		}
		return osexec.CommandContext(ctx, "true")
	}

	ctx := ExecContext{Ctx: context.Background(), Cwd: tempDir}
	err := RunHerdrAgentStart(ctx, "plan-73", "fx", "wN:p3M", "prompt de plan")
	if err != nil {
		t.Fatalf("Expected RunHerdrAgentStart to succeed for fx, got %v", err)
	}

	normPath := filepath.Clean(tempDir)
	expectedCalls := [][]string{
		{"herdr", "pane", "run", "wN:p3M", "wsl", "-d", "Ubuntu", "--cd", normPath, "bash", "-lc", "fx"},
		{"herdr", "pane", "wait-output", "--match", fxReadyMarker, "wN:p3M"},
		{"herdr", "pane", "send-text", "wN:p3M", "prompt de plan"},
		{"herdr", "pane", "send-keys", "wN:p3M", "Enter"},
	}
	for _, exp := range expectedCalls {
		if !containsCall(calls, exp) {
			t.Fatalf("Missing expected herdr call %v; recorded: %v", exp, calls)
		}
	}

	for _, c := range calls {
		if len(c) > 2 && c[1] == "agent" && c[2] == "start" {
			t.Fatalf("herdr agent start must be skipped for fx (unsupported kind); recorded: %v", c)
		}
	}
}

// Si el TUI de fx nunca muestra el banner de readiness, el comportamiento
// actual (post-issue-#6) es soft-fail: el wait timeout se loguea como
// warning y se prosigue con send-text. Esto protege contra la fragilidad
// del marker hardcodeado: si fx cambia su banner, el prompt sigue
// llegando. La inyección exitosa es la prioridad.
func TestRunHerdrAgentStart_FxWaitFailureSoftFails(t *testing.T) {
	tempDir := t.TempDir()
	origRunner := DefaultCommandRunner
	defer func() { DefaultCommandRunner = origRunner }()

	var calls [][]string
	DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
		calls = append(calls, append([]string{name}, args...))
		// Forzar timeout en wait-output para simular banner que no aparece.
		if len(args) > 1 && args[0] == "pane" && args[1] == "wait-output" {
			if runtime.GOOS == "windows" {
				return osexec.CommandContext(ctx, "cmd.exe", "/C", "exit 1")
			}
			return osexec.CommandContext(ctx, "false")
		}
		if runtime.GOOS == "windows" {
			return osexec.CommandContext(ctx, "cmd.exe", "/C", "exit 0")
		}
		return osexec.CommandContext(ctx, "true")
	}

	ctx := ExecContext{Ctx: context.Background(), Cwd: tempDir}
	err := RunHerdrAgentStart(ctx, "plan-73", "fx", "wN:p3M", "prompt de plan")
	// Soft-fail: la funcion debe retornar nil aunque wait-output haya fallado.
	if err != nil {
		t.Fatalf("Expected soft-fail (nil error) for fx wait timeout, got %v", err)
	}

	// Pero send-text y send-keys SI deben haber sido ejecutados (el prompt
	// llega aunque el banner no apareciera).
	if !containsCall(calls, []string{"herdr", "pane", "send-text", "wN:p3M", "prompt de plan"}) {
		t.Fatalf("send-text was not called after wait timeout; recorded: %v", calls)
	}
	if !containsCall(calls, []string{"herdr", "pane", "send-keys", "wN:p3M", "Enter"}) {
		t.Fatalf("send-keys was not called after wait timeout; recorded: %v", calls)
	}
}

func TestRunCodeGraphInit_EmptyCwd(t *testing.T) {
	err := RunCodeGraphInit(ExecContext{})
	if err != nil {
		t.Fatalf("Expected nil error for empty Cwd, got %v", err)
	}
}

func TestRunCodeGraphInit_ExecutesInit(t *testing.T) {
	origRunner := DefaultCommandRunner
	defer func() { DefaultCommandRunner = origRunner }()

	binDir := t.TempDir()
	writeDummyBinary(t, binDir, "gentle-ai")
	t.Setenv("PATH", binDir+string(os.PathListSeparator)+systemBinPath())

	var executedCmd string
	var executedArgs []string
	DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
		executedCmd = name
		executedArgs = args
		if runtime.GOOS == "windows" {
			return osexec.CommandContext(ctx, "cmd.exe", "/C", "exit 0")
		}
		return osexec.CommandContext(ctx, "true")
	}

	testPath := filepath.Join(t.TempDir(), "wt-test")
	if err := os.MkdirAll(testPath, 0755); err != nil {
		t.Fatalf("Failed to create test directory: %v", err)
	}
	err := RunCodeGraphInit(ExecContext{Cwd: testPath})
	if err != nil {
		t.Fatalf("Expected RunCodeGraphInit to succeed, got: %v", err)
	}

	if executedCmd != "gentle-ai" && executedCmd != "codegraph" {
		t.Fatalf("Expected command gentle-ai or codegraph, got: %s", executedCmd)
	}
	argsStr := strings.Join(executedArgs, " ")
	if !strings.Contains(argsStr, "init") {
		t.Fatalf("Expected 'init' in args, got: %v", executedArgs)
	}
}

func TestDeriveReviewSeverity(t *testing.T) {
	cases := []struct {
		name     string
		gate     GentleGateResult
		expected string
	}{
		{"Allowed true is CLEAN", GentleGateResult{Allowed: true}, "CLEAN"},
		{"Allowed false is BLOCKER", GentleGateResult{Allowed: false, Result: "scope-changed"}, "BLOCKER"},
		{"Allowed false with denial code is BLOCKER", GentleGateResult{
			Allowed: false,
			Context: &GentleContext{
				Gate:   "pre-pr",
				Denial: &GentleDenial{Stage: "receipt-binding", Code: "candidate-or-paths-mismatch"},
			},
		}, "BLOCKER"},
		{"Allowed false without context is BLOCKER (nil-safe)", GentleGateResult{Allowed: false}, "BLOCKER"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			res := DeriveReviewSeverity(tc.gate)
			if res != tc.expected {
				t.Fatalf("Expected severity %s, got %s", tc.expected, res)
			}
		})
	}
}

func TestBuildPlanPrompt(t *testing.T) {
	p := IssuePayload{Title: "feat: new trading signal"}
	prompt := BuildPlanPrompt("74", p)
	if !strings.Contains(prompt, "PLAN") || !strings.Contains(prompt, "Given/When/Then") || !strings.Contains(prompt, "STOP") {
		t.Fatalf("Expected BuildPlanPrompt to contain PLAN, Given/When/Then, and STOP, got: %s", prompt)
	}
}

func TestBuildFixPrompt(t *testing.T) {
	p := IssuePayload{Title: "fix: schema drift"}
	gateWithDenial := GentleGateResult{
		Allowed: false,
		Reason:  "receipt mismatch",
		Context: &GentleContext{
			Denial: &GentleDenial{Code: "candidate-or-paths-mismatch"},
		},
	}
	prompt := BuildFixPrompt("74", p, `C:\Users\test\.loom\worktrees\74`, 1, gateWithDenial)
	if !strings.Contains(prompt, "FIX") || !strings.Contains(prompt, "candidate-or-paths-mismatch") || !strings.Contains(prompt, "1/2") {
		t.Fatalf("Expected BuildFixPrompt to contain FIX, denial code, and retry count 1/2, got: %s", prompt)
	}

	// Fallback without denial code
	gateFallback := GentleGateResult{
		Allowed: false,
		Result:  "scope-changed",
		Reason:  "files differing",
	}
	promptFallback := BuildFixPrompt("74", p, `C:\Users\test\.loom\worktrees\74`, 2, gateFallback)
	if !strings.Contains(promptFallback, "scope-changed") || !strings.Contains(promptFallback, "2/2") {
		t.Fatalf("Expected fallback to contain scope-changed and 2/2, got: %s", promptFallback)
	}
}

func TestRunGitStageAll(t *testing.T) {
	origRunner := DefaultCommandRunner
	defer func() { DefaultCommandRunner = origRunner }()

	var executedArgs []string
	DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
		executedArgs = args
		if runtime.GOOS == "windows" {
			return osexec.CommandContext(ctx, "cmd.exe", "/C", "exit 0")
		}
		return osexec.CommandContext(ctx, "true")
	}

	err := RunGitStageAll(ExecContext{Cwd: t.TempDir()})
	if err != nil {
		t.Fatalf("Expected RunGitStageAll to succeed, got %v", err)
	}

	argsJoined := strings.Join(executedArgs, " ")
	if !strings.Contains(argsJoined, "add -A -- :!review.log") {
		t.Fatalf("Expected args to contain 'add -A -- :!review.log', got %v", executedArgs)
	}
}

// venvPythonPath devuelve la ruta del intérprete de un .venv según GOOS.
func venvPythonPath(root string) string {
	if runtime.GOOS == "windows" {
		return filepath.Join(root, ".venv", "Scripts", "python.exe")
	}
	return filepath.Join(root, ".venv", "bin", "python")
}

// writeFakeVenv materializa un python de .venv falso (solo para os.Stat/LookPath).
func writeFakeVenv(t *testing.T, root string) string {
	t.Helper()
	pyExe := venvPythonPath(root)
	if err := os.MkdirAll(filepath.Dir(pyExe), 0755); err != nil {
		t.Fatalf("Failed to create fake venv dir: %v", err)
	}
	if err := os.WriteFile(pyExe, []byte("#!/bin/sh\n"), 0755); err != nil {
		t.Fatalf("Failed to write fake venv python: %v", err)
	}
	return pyExe
}

func TestResolvePythonPath(t *testing.T) {
	// El discovery del repo raíz no debe depender del ambiente del host.
	isolateRoot := func(t *testing.T, repoRoot string) {
		t.Helper()
		t.Setenv("GITHUB_WORKSPACE", "")
		t.Setenv("TARGET_REPO_PATH", repoRoot)
	}

	t.Run("worktree venv wins", func(t *testing.T) {
		tempDir := t.TempDir()
		pyExe := writeFakeVenv(t, tempDir)
		isolateRoot(t, t.TempDir())
		t.Setenv("PATH", t.TempDir())

		found, err := ResolvePythonPath(tempDir)
		if err != nil {
			t.Fatalf("Expected ResolvePythonPath to find worktree venv, got error: %v", err)
		}
		if filepath.Clean(found) != filepath.Clean(pyExe) {
			t.Fatalf("Expected python path %s, got %s", pyExe, found)
		}
	})

	t.Run("repo root venv fallback", func(t *testing.T) {
		repoRoot := t.TempDir()
		rootPyExe := writeFakeVenv(t, repoRoot)
		worktree := t.TempDir() // sin .venv propio
		isolateRoot(t, repoRoot)
		t.Setenv("PATH", t.TempDir())

		found, err := ResolvePythonPath(worktree)
		if err != nil {
			t.Fatalf("Expected ResolvePythonPath to find repo root venv, got error: %v", err)
		}
		if filepath.Clean(found) != filepath.Clean(rootPyExe) {
			t.Fatalf("Expected python path %s, got %s", rootPyExe, found)
		}
	})

	t.Run("PATH fallback when no venv exists", func(t *testing.T) {
		binDir := t.TempDir()
		var pyName string
		if runtime.GOOS == "windows" {
			pyName = "python3.exe"
		} else {
			pyName = "python3"
		}
		pyBin := filepath.Join(binDir, pyName)
		if err := os.WriteFile(pyBin, []byte("#!/bin/sh\n"), 0755); err != nil {
			t.Fatalf("Failed to write fake PATH python: %v", err)
		}
		isolateRoot(t, t.TempDir())
		t.Setenv("PATH", binDir)

		found, err := ResolvePythonPath(t.TempDir())
		if err != nil {
			t.Fatalf("Expected ResolvePythonPath to find python on PATH, got error: %v", err)
		}
		if filepath.Clean(found) != filepath.Clean(pyBin) {
			t.Fatalf("Expected python path %s, got %s", pyBin, found)
		}
	})

	t.Run("missing interpreter fails closed with sentinel", func(t *testing.T) {
		isolateRoot(t, t.TempDir())
		t.Setenv("PATH", t.TempDir())

		found, err := ResolvePythonPath(t.TempDir())
		if !errors.Is(err, ErrPythonEnvMissing) {
			t.Fatalf("Expected ErrPythonEnvMissing, got %v", err)
		}
		if found != "" {
			t.Fatalf("Expected empty path on missing env, got %s", found)
		}
	})
}

func TestRunPytestEvidence(t *testing.T) {
	t.Run("missing interpreter fails closed with sentinel", func(t *testing.T) {
		t.Setenv("GITHUB_WORKSPACE", "")
		t.Setenv("TARGET_REPO_PATH", t.TempDir())
		t.Setenv("PATH", t.TempDir())

		err := RunPytestEvidence(ExecContext{Cwd: t.TempDir()})
		if !errors.Is(err, ErrPythonEnvMissing) {
			t.Fatalf("Expected ErrPythonEnvMissing, got %v", err)
		}
	})

	t.Run("runs resolved interpreter with -m pytest", func(t *testing.T) {
		worktree := t.TempDir()
		pyExe := writeFakeVenv(t, worktree)

		origRunner := DefaultCommandRunner
		defer func() { DefaultCommandRunner = origRunner }()

		var executedName string
		var executedArgs []string
		DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
			executedName = name
			executedArgs = args
			if runtime.GOOS == "windows" {
				return osexec.CommandContext(ctx, "cmd.exe", "/C", "exit 0")
			}
			return osexec.CommandContext(ctx, "true")
		}

		if err := RunPytestEvidence(ExecContext{Cwd: worktree}); err != nil {
			t.Fatalf("Expected RunPytestEvidence to succeed with stubbed runner, got %v", err)
		}
		if filepath.Clean(executedName) != filepath.Clean(pyExe) {
			t.Fatalf("Expected resolved interpreter %s, got %s", pyExe, executedName)
		}
		argsJoined := strings.Join(executedArgs, " ")
		if !strings.Contains(argsJoined, "-m pytest") {
			t.Fatalf("Expected args to contain '-m pytest', got %v", executedArgs)
		}
	})

	t.Run("pytest failure propagates", func(t *testing.T) {
		worktree := t.TempDir()
		writeFakeVenv(t, worktree)

		origRunner := DefaultCommandRunner
		defer func() { DefaultCommandRunner = origRunner }()

		DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
			if runtime.GOOS == "windows" {
				return osexec.CommandContext(ctx, "cmd.exe", "/C", "exit 1")
			}
			return osexec.CommandContext(ctx, "false")
		}

		if err := RunPytestEvidence(ExecContext{Cwd: worktree}); err == nil {
			t.Fatal("Expected RunPytestEvidence to propagate pytest failure, got nil")
		}
	})
}

func TestDetectTestRunner(t *testing.T) {
	t.Run("detects Go project when go.mod exists", func(t *testing.T) {
		worktree := t.TempDir()
		if err := os.WriteFile(filepath.Join(worktree, "go.mod"), []byte("module example.com/test\n\ngo 1.21\n"), 0644); err != nil {
			t.Fatal(err)
		}
		runnerKind, binPath, args, err := DetectTestRunner(worktree)
		if err != nil {
			t.Fatalf("Expected Go runner to be detected, got err: %v", err)
		}
		if runnerKind != RunnerGoTest {
			t.Fatalf("Expected RunnerGoTest, got %v", runnerKind)
		}
		if binPath != "go" {
			t.Fatalf("Expected binary 'go', got %q", binPath)
		}
		if len(args) == 0 || args[0] != "test" {
			t.Fatalf("Expected 'test' arg, got %v", args)
		}
	})

	t.Run("detects Python project with venv", func(t *testing.T) {
		worktree := t.TempDir()
		pyExe := writeFakeVenv(t, worktree)
		runnerKind, binPath, args, err := DetectTestRunner(worktree)
		if err != nil {
			t.Fatalf("Expected Python runner to be detected, got err: %v", err)
		}
		if runnerKind != RunnerPytest {
			t.Fatalf("Expected RunnerPytest, got %v", runnerKind)
		}
		if filepath.Clean(binPath) != filepath.Clean(pyExe) {
			t.Fatalf("Expected python bin %s, got %s", pyExe, binPath)
		}
		argsJoined := strings.Join(args, " ")
		if !strings.Contains(argsJoined, "-m pytest") {
			t.Fatalf("Expected args containing '-m pytest', got %v", args)
		}
	})

	t.Run("fails closed when neither Go nor Python found", func(t *testing.T) {
		worktree := t.TempDir()
		t.Setenv("GITHUB_WORKSPACE", "")
		t.Setenv("TARGET_REPO_PATH", t.TempDir())
		t.Setenv("PATH", t.TempDir())
		_, _, _, err := DetectTestRunner(worktree)
		if err == nil {
			t.Fatal("Expected error when no test runner found, got nil")
		}
		if !errors.Is(err, ErrUnknownProjectRunner) && !errors.Is(err, ErrPythonEnvMissing) {
			t.Fatalf("Expected ErrUnknownProjectRunner or ErrPythonEnvMissing, got %v", err)
		}
	})
}

func TestRunTestEvidence(t *testing.T) {
	t.Run("executes go test in Go worktree", func(t *testing.T) {
		worktree := t.TempDir()
		if err := os.WriteFile(filepath.Join(worktree, "go.mod"), []byte("module example.com/test\n"), 0644); err != nil {
			t.Fatal(err)
		}

		origRunner := DefaultCommandRunner
		defer func() { DefaultCommandRunner = origRunner }()

		var executedName string
		DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
			executedName = name
			if runtime.GOOS == "windows" {
				return osexec.CommandContext(ctx, "cmd.exe", "/C", "echo ok")
			}
			return osexec.CommandContext(ctx, "echo", "ok")
		}

		report, err := RunTestEvidence(ExecContext{Cwd: worktree})
		if err != nil {
			t.Fatalf("Expected RunTestEvidence to succeed, got %v", err)
		}
		if report == nil || !report.Passed {
			t.Fatal("Expected report.Passed to be true")
		}
		if report.Runner != RunnerGoTest {
			t.Fatalf("Expected RunnerGoTest, got %v", report.Runner)
		}
		if executedName != "go" {
			t.Fatalf("Expected 'go' executed, got %q", executedName)
		}
	})
}

