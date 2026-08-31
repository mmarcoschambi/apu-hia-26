package exec

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

type ExecContext struct {
	Ctx            context.Context
	Cwd            string
	CommandTimeout time.Duration
	EnvAllowlist   []string // e.g. ["HOME", "PATH", "TEMP"] (denies GITHUB_TOKEN by default)
	CmdArgs        []string // Un-parsed arguments
}

type IssuePayload struct {
	Title  string
	Body   string
	URL    string
	Labels []string
}

type GentleDenial struct {
	Stage string `json:"stage"`
	Code  string `json:"code"`
}

type GentleContext struct {
	Gate   string        `json:"gate"`
	Denial *GentleDenial `json:"denial,omitempty"`
}

type GentleGateResult struct {
	Schema   string         `json:"schema,omitempty"`
	Result   string         `json:"result"`
	Allowed  bool           `json:"allowed"`
	Action   string         `json:"action,omitempty"`
	Reason   string         `json:"reason"`
	Delivery string         `json:"delivery,omitempty"`
	Context  *GentleContext `json:"context,omitempty"`
}

func DeriveReviewSeverity(gr GentleGateResult) string {
	if gr.Allowed {
		return "CLEAN"
	}
	return "BLOCKER" // Fail-closed
}

var ErrPythonEnvMissing = errors.New("python environment missing: create .venv in the repo root or worktree, or ensure python is on PATH")
var ErrUnknownProjectRunner = errors.New("no supported test runner discovered (expected go.mod or python environment)")

type TestRunnerKind string

const (
	RunnerGoTest  TestRunnerKind = "go_test"
	RunnerPytest  TestRunnerKind = "pytest"
	RunnerUnknown TestRunnerKind = "unknown"
)

type TestExecutionResult struct {
	Runner   TestRunnerKind
	Passed   bool
	Output   string
	Duration time.Duration
}

func ResolvePythonPath(worktreePath string) (string, error) {
	// 1. Worktree .venv
	if worktreePath != "" {
		var wtCandidate string
		if runtime.GOOS == "windows" {
			wtCandidate = filepath.Join(worktreePath, ".venv", "Scripts", "python.exe")
		} else {
			wtCandidate = filepath.Join(worktreePath, ".venv", "bin", "python")
		}
		if _, err := os.Stat(wtCandidate); err == nil {
			return wtCandidate, nil
		}
	}

	// 2. Repo root .venv
	repoRoot := os.Getenv("GITHUB_WORKSPACE")
	if repoRoot == "" {
		repoRoot = GetRepoRoot()
	}
	if repoRoot != "" {
		var rootCandidate string
		if runtime.GOOS == "windows" {
			rootCandidate = filepath.Join(repoRoot, ".venv", "Scripts", "python.exe")
		} else {
			rootCandidate = filepath.Join(repoRoot, ".venv", "bin", "python")
		}
		if _, err := os.Stat(rootCandidate); err == nil {
			return rootCandidate, nil
		}
	}

	// 3. PATH
	if pyPath, err := exec.LookPath("python3"); err == nil {
		return pyPath, nil
	}
	if pyPath, err := exec.LookPath("python"); err == nil {
		return pyPath, nil
	}

	return "", ErrPythonEnvMissing
}

func RunGitStageAll(ctx ExecContext) error {
	stageCtx, cancel := commandCtx(ctx, 30*time.Second)
	defer cancel()
	cmd := DefaultCommandRunner(stageCtx, "git", "add", "-A", "--", ":!review.log")
	cmd.Dir = ctx.Cwd
	cmd.Env = BuildEnv(ctx.EnvAllowlist)
	return cmd.Run()
}

// DetectTestRunner inspecciona el worktree para determinar el ejecutable
// de tests nativo (Go o Python). Retorna el tipo de runner, el binario,
// los argumentos y error en caso de no encontrar ningún entorno compatible.
func DetectTestRunner(cwd string) (TestRunnerKind, string, []string, error) {
	if cwd != "" {
		goModPath := filepath.Join(cwd, "go.mod")
		if _, err := os.Stat(goModPath); err == nil {
			return RunnerGoTest, "go", []string{"test", "./..."}, nil
		}
	}

	pyPath, err := ResolvePythonPath(cwd)
	if err == nil && pyPath != "" {
		return RunnerPytest, pyPath, []string{"-m", "pytest", "-q"}, nil
	}

	if err != nil {
		return RunnerUnknown, "", nil, errors.Join(ErrUnknownProjectRunner, err)
	}
	return RunnerUnknown, "", nil, ErrUnknownProjectRunner
}

// RunTestEvidence ejecuta la evidencia de tests según el tipo de proyecto
// descubierto en el worktree (go test ./... o pytest -q).
// Fail-closed: si falla la ejecución o no hay runner, se propaga el error.
func RunTestEvidence(ctx ExecContext) (*TestExecutionResult, error) {
	kind, binPath, args, err := DetectTestRunner(ctx.Cwd)
	if err != nil {
		return nil, err
	}

	start := time.Now()
	testCtx, cancel := commandCtx(ctx, pytestEvidenceTimeout)
	defer cancel()

	cmd := DefaultCommandRunner(testCtx, binPath, args...)
	cmd.Dir = ctx.Cwd
	cmd.Env = BuildEnv(ctx.EnvAllowlist)

	out, runErr := cmd.CombinedOutput()
	dur := time.Since(start)

	res := &TestExecutionResult{
		Runner:   kind,
		Passed:   runErr == nil,
		Output:   string(out),
		Duration: dur,
	}

	if runErr != nil {
		return res, fmt.Errorf("%s evidence failed: %w", kind, runErr)
	}
	return res, nil
}

// RunPytestEvidence ejecuta la evidencia ejecutable del ciclo de review
// delegando en el motor políglota RunTestEvidence [JD-4].
// Fail-closed: sin intérprete o con tests rojos NO se procede al gate ni al sello.
func RunPytestEvidence(ctx ExecContext) error {
	_, err := RunTestEvidence(ctx)
	return err
}

// GateDenialInfo extrae (code, result, reason) del resultado del gate para
// persistirlos en la FSM (IssueFSM.RecordGateDenial).
func GateDenialInfo(gr GentleGateResult) (code string, result string, reason string) {
	if gr.Context != nil && gr.Context.Denial != nil {
		code = gr.Context.Denial.Code
	}
	return code, gr.Result, gr.Reason
}

// GateResultFromDenial reconstruye un GentleGateResult desde el denial
// persistido en la FSM, para inyectarlo en BuildFixPrompt en el dispatch de FIX.
func GateResultFromDenial(code, result, reason string) GentleGateResult {
	gr := GentleGateResult{Allowed: false, Result: result, Reason: reason}
	if code != "" {
		gr.Context = &GentleContext{Denial: &GentleDenial{Code: code}}
	}
	return gr
}

func BuildPlanPrompt(issueID string, payload IssuePayload) string {
	return fmt.Sprintf("Estás en la fase PLAN del issue #%s. Redacta la especificación formal en openspec/changes/issue-%s/ (proposal.md, design.md, specs/spec.md, tasks.md) con una matriz de escenarios BDD cerrada (Given/When/Then) y casos límite explícitos. Si existe alguna ambigüedad de requerimientos o diseño, DETENTE (STOP) y consulta al usuario antes de generar el plan final.", issueID, issueID)
}

func BuildApplyPrompt(issueID string, payload IssuePayload, worktreePath string) string {
	if isComplexIssue(payload) {
		return fmt.Sprintf("Estás en la fase APPLY del issue #%s dentro del worktree aislado (%s). Lee openspec/changes/issue-%s/ (proposal.md, design.md, specs/spec.md, tasks.md) y ejecuta las tareas con la skill sdd-apply bajo TDD estricto (RED antes que GREEN). Todas las modificaciones deben realizarse exclusivamente en este worktree sin tocar el repositorio principal.", issueID, worktreePath, issueID)
	}
	return fmt.Sprintf("Estás en la fase APPLY del issue #%s dentro del worktree aislado (%s). Lee tasks.md y ejecuta las tareas de desarrollo con TDD estricto (RED antes que GREEN) sin tocar el repositorio principal.", issueID, worktreePath)
}

func BuildReviewPrompt(issueID string, worktreePath string) string {
	return fmt.Sprintf("Estás en la fase REVIEW del issue #%s en el worktree aislado (%s). Actúa como un auditor independiente de QA y Riesgo. Lee el git diff y evalúa las 4 Lentes de Riesgo (Risk, Resilience, Readability, Reliability). Valida la evidencia ejecutable y genera los recibos de auditoría con gentle-ai review capture-result.", issueID, worktreePath)
}

func BuildFixPrompt(issueID string, payload IssuePayload, worktreePath string, retryCount int, gateResult ...GentleGateResult) string {
	denialReason := "terminal review receipts do not match gate target"
	if len(gateResult) > 0 {
		gr := gateResult[0]
		if gr.Context != nil && gr.Context.Denial != nil && gr.Context.Denial.Code != "" {
			denialReason = fmt.Sprintf("código de rechazo [%s]: %s", gr.Context.Denial.Code, gr.Reason)
		} else if gr.Result != "" && gr.Reason != "" {
			denialReason = fmt.Sprintf("resultado [%s]: %s", gr.Result, gr.Reason)
		} else if gr.Reason != "" {
			denialReason = gr.Reason
		}
	}
	return fmt.Sprintf("Estás en la fase FIX (Remediación) del issue #%s en el worktree aislado (%s). Reintento de corrección: %d/2. El auditor rechazó la validación previa (%s). Lee review.log, tasks.md y openspec/changes/issue-%s/ (si existe) y aplica quirúrgicamente las correcciones necesarias bajo TDD estricto sin tocar el repositorio principal.", issueID, worktreePath, retryCount, denialReason, issueID)
}

func BuildDirectPrompt(issueID string, payload IssuePayload, worktreePath string) string {
	return fmt.Sprintf("Estás ejecutando el issue #%s en modo Fast-Path DIRECT dentro del worktree aislado (%s). Lee tasks.md, realiza las modificaciones solicitadas directamente bajo TDD y verifica que los tests pasen al 100%% sin tocar el repositorio principal.", issueID, worktreePath)
}

func WriteTasksMD(ctx ExecContext, payload IssuePayload) error {
	// Normalize the Cwd path to prevent path traversal
	normPath := filepath.Clean(ctx.Cwd)

	// Ensure it starts with the valid worktrees directory
	homeDir, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("failed to get user home dir: %w", err)
	}
	validPrefix := filepath.Join(homeDir, ".loom", "worktrees")

	// Use filepath.Rel for safe, case-insensitive, OS-aware path bounding
	rel, err := filepath.Rel(validPrefix, normPath)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return fmt.Errorf("path traversal attempt rejected: %s", normPath)
	}

	tasksPath := filepath.Join(normPath, "tasks.md")

	content := fmt.Sprintf("# Tasks: %s\n\n%s\n\nURL: %s\nLabels: %s",
		payload.Title, payload.Body, payload.URL, strings.Join(payload.Labels, ", "))

	return os.WriteFile(tasksPath, []byte(content), 0644)
}

func ResolveTargetRepoDir() string {
	if p := os.Getenv("TARGET_REPO_PATH"); p != "" {
		return filepath.Clean(p)
	}
	if p := os.Getenv("LOOM_TARGET_REPO_PATH"); p != "" {
		return filepath.Clean(p)
	}
	cwd, _ := os.Getwd()
	return cwd
}

func GetRepoRoot() string {
	return ResolveTargetRepoDir()
}

func isComplexIssue(payload IssuePayload) bool {
	for _, l := range payload.Labels {
		lower := strings.ToLower(l)
		if lower == "feat" || lower == "feature" || lower == "epic" || lower == "architecture" || lower == "sdd" || lower == "spec" {
			return true
		}
	}
	tLower := strings.ToLower(payload.Title)
	return strings.HasPrefix(tLower, "feat(") || strings.HasPrefix(tLower, "feat:") || strings.HasPrefix(tLower, "epic(")
}

// BuildPromptForIssue generates an informed directive for the agent based on issue
// complexity and remediation status. Si existe un review.log previo, emite el
// prompt de FIX con el reintento REAL del issue y el denial persistido del gate.
func BuildPromptForIssue(issueID string, payload IssuePayload, worktreePath string, retryCount int, gateResult ...GentleGateResult) string {
	wt := worktreePath
	if wt != "" {
		reviewLogPath := filepath.Join(wt, "review.log")
		if data, err := os.ReadFile(reviewLogPath); err == nil && len(bytes.TrimSpace(data)) > 0 {
			return BuildFixPrompt(issueID, payload, wt, retryCount, gateResult...)
		}
	}
	return BuildApplyPrompt(issueID, payload, wt)
}

// WriteOpenSpecScaffold writes root tasks.md and conditionally creates the 4-document OpenSpec suite
func WriteOpenSpecScaffold(ctx ExecContext, issueID string, payload IssuePayload) error {
	normPath := filepath.Clean(ctx.Cwd)

	homeDir, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("failed to get user home dir: %w", err)
	}
	validPrefix := filepath.Join(homeDir, ".loom", "worktrees")
	rel, err := filepath.Rel(validPrefix, normPath)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		tempRel, tempErr := filepath.Rel(os.TempDir(), normPath)
		if tempErr != nil || tempRel == ".." || strings.HasPrefix(tempRel, ".."+string(filepath.Separator)) {
			return fmt.Errorf("path traversal attempt rejected: %s", normPath)
		}
	}

	if err := WriteTasksMD(ctx, payload); err != nil {
		return err
	}

	if !isComplexIssue(payload) {
		return nil
	}

	changeDir := filepath.Join(normPath, "openspec", "changes", "issue-"+issueID)
	specsDir := filepath.Join(changeDir, "specs")
	if err := os.MkdirAll(specsDir, 0755); err != nil {
		return fmt.Errorf("failed to create openspec change dir: %w", err)
	}

	proposalContent := fmt.Sprintf("# Proposal: %s\n\n## Intent\n%s\n\n## Context\nURL: %s\nLabels: %s\n",
		payload.Title, payload.Body, payload.URL, strings.Join(payload.Labels, ", "))
	if err := os.WriteFile(filepath.Join(changeDir, "proposal.md"), []byte(proposalContent), 0644); err != nil {
		return err
	}

	designContent := fmt.Sprintf("# Design: %s\n\n## Architecture & Decisions\n- Target implementation for Issue #%s\n\n## Failure Modes & Mitigations\n- TDD verification enforced.\n",
		payload.Title, issueID)
	if err := os.WriteFile(filepath.Join(changeDir, "design.md"), []byte(designContent), 0644); err != nil {
		return err
	}

	specContent := fmt.Sprintf("# Spec: %s\n\n## Requirements\n- %s\n",
		payload.Title, payload.Title)
	if err := os.WriteFile(filepath.Join(specsDir, "spec.md"), []byte(specContent), 0644); err != nil {
		return err
	}

	tasksContent := fmt.Sprintf("# Tasks: %s\n\n- [ ] 1.1 Red Test (TDD)\n- [ ] 1.2 Implementation\n- [ ] 1.3 QA Verification\n",
		payload.Title)
	if err := os.WriteFile(filepath.Join(changeDir, "tasks.md"), []byte(tasksContent), 0644); err != nil {
		return err
	}

	return nil
}

func RunOrcaCreate(ctx ExecContext, issueID string) error {
	normPath := filepath.Clean(ctx.Cwd)

	homeDir, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("failed to get user home dir: %w", err)
	}
	validPrefix := filepath.Join(homeDir, ".loom", "worktrees")

	rel, err := filepath.Rel(validPrefix, normPath)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		// Allow test directories in TempDir for unit tests
		tempRel, tempErr := filepath.Rel(os.TempDir(), normPath)
		if tempErr != nil || tempRel == ".." || strings.HasPrefix(tempRel, ".."+string(filepath.Separator)) {
			return fmt.Errorf("path traversal attempt rejected: %s", normPath)
		}
	}

	// 1. Create real Git worktree checkout from target repo so the AI agent has the real codebase
	baseRepoDir := ResolveTargetRepoDir()
	runCtx, cancel := commandCtx(ctx, orcaCreateTimeout)
	defer cancel()
	if _, lookErr := exec.LookPath("git"); lookErr == nil {
		branchName := "issue-" + issueID
		cmd := DefaultCommandRunner(runCtx, "git", "worktree", "add", "-b", branchName, normPath, "HEAD")
		cmd.Dir = baseRepoDir
		cmd.Env = BuildEnv(ctx.EnvAllowlist)
		if gitErr := cmd.Run(); gitErr != nil {
			cmdExisting := DefaultCommandRunner(runCtx, "git", "worktree", "add", normPath, branchName)
			cmdExisting.Dir = baseRepoDir
			cmdExisting.Env = BuildEnv(ctx.EnvAllowlist)
			_ = cmdExisting.Run()
		}
	}

	// Fallback to mkdir if git worktree wasn't created
	_ = os.MkdirAll(normPath, 0755)

	// 2. If orca is installed, invoke worktree creation and reveal in Orca app
	if _, lookErr := exec.LookPath("orca"); lookErr == nil {
		cmd := DefaultCommandRunner(runCtx, "orca", "worktree", "create", "--name", "issue-"+issueID, "--issue", issueID, "--activate")
		cmd.Dir = normPath
		cmd.Env = BuildEnv(ctx.EnvAllowlist)
		_ = cmd.Run() // non-blocking if orca daemon not running
	}

	// 3. Initialize CodeGraph index if available so AI agents have instant access to intelligence
	_ = RunCodeGraphInit(ctx)

	return nil
}

// IsHerdrRunning checks if the Herdr daemon/socket is active
func IsHerdrRunning() bool {
	if _, lookErr := exec.LookPath("herdr"); lookErr != nil {
		return false
	}
	ctx, cancel := context.WithTimeout(context.Background(), quickCmdTimeout)
	defer cancel()
	cmd := DefaultCommandRunner(ctx, "herdr", "status")
	return cmd.Run() == nil
}

type HerdrTabCreateResponse struct {
	Result struct {
		RootPane struct {
			PaneID string `json:"pane_id"`
			TabID  string `json:"tab_id"`
		} `json:"root_pane"`
		Tab struct {
			TabID string `json:"tab_id"`
		} `json:"tab"`
	} `json:"result"`
}

// RunHerdrTabCreate creates an isolated tab in Herdr without stealing focus from Loom
func RunHerdrTabCreate(ctx ExecContext, label string) (tabID string, paneID string, err error) {
	normPath := filepath.Clean(ctx.Cwd)
	runCtx, cancel := commandCtx(ctx, agentCmdTimeout)
	defer cancel()
	cmd := DefaultCommandRunner(runCtx, "herdr", "tab", "create", "--cwd", normPath, "--label", label, "--no-focus")
	cmd.Dir = normPath
	cmd.Env = BuildEnv(ctx.EnvAllowlist)
	out, err := cmd.Output()
	if err != nil {
		return "", "", err
	}

	var resp HerdrTabCreateResponse
	if err := json.Unmarshal(out, &resp); err != nil {
		return "", "", err
	}

	tID := resp.Result.Tab.TabID
	if tID == "" {
		tID = resp.Result.RootPane.TabID
	}
	return tID, resp.Result.RootPane.PaneID, nil
}

// ToWslPath converts a Windows path (e.g. C:\path\to\dir) to its WSL mount path (/mnt/c/path/to/dir)
func ToWslPath(winPath string) string {
	clean := filepath.Clean(winPath)
	clean = strings.ReplaceAll(clean, `\`, `/`)
	if len(clean) >= 2 && clean[1] == ':' {
		drive := strings.ToLower(string(clean[0]))
		return "/mnt/" + drive + clean[2:]
	}
	return clean
}

// fxReadyMarker es la línea de banner que fx imprime cuando su TUI está listo
// para aceptar input; se usa como señal de readiness antes de inyectar el prompt.
const fxReadyMarker = "Run /help for commands"

// zcodeReadyMarker es la línea de banner tentativa del TUI de zcode. Es un
// default: si zcode cambia su banner, el wait-output va a timeout y el
// fallback (send-text sin esperar readiness) igual inyecta el prompt.
// Validar empiricamente lanzando zcode en el worktree y capturando el output
// del pane. Si se confirma otro marker, ajustar este const y mantener el
// fallback como red de seguridad.
const zcodeReadyMarker = "zcode>"

// RunHerdrAgentStart registers and starts the agent with its prompt flags in the specified pane
func RunHerdrAgentStart(ctx ExecContext, targetName string, agentKind string, paneID string, prompt string) error {
	normPath := filepath.Clean(ctx.Cwd)
	if agentKind == "" {
		agentKind = "opencode"
	}
	runCtx, cancel := commandCtx(ctx, agentCmdTimeout)
	defer cancel()

	quotedPrompt := fmt.Sprintf("\"%s\"", prompt)

	// 1. Launch the agent with its prompt flags with retry & exponential backoff on TTY readiness
	var lastRunErr error
	for attempt := 0; attempt < 4; attempt++ {
		time.Sleep(time.Duration(150*(1<<attempt)) * time.Millisecond) // 150ms, 300ms, 600ms, 1200ms

		var runCmd *exec.Cmd
		if agentKind == "agy" {
			runCmd = DefaultCommandRunner(runCtx, "herdr", "pane", "run", paneID, "agy", "--prompt-interactive", quotedPrompt)
		} else if agentKind == "fx" {
			runCmd = DefaultCommandRunner(runCtx, "herdr", "pane", "run", paneID, "wsl", "-d", "Ubuntu", "--cd", normPath, "bash", "-lc", "fx")
		} else if agentKind == "zcode" {
			runCmd = DefaultCommandRunner(runCtx, "herdr", "pane", "run", paneID, "cmd.exe", "/C", "zcode", normPath)
		} else if agentKind == "code" {
			runCmd = DefaultCommandRunner(runCtx, "herdr", "pane", "run", paneID, "cmd.exe", "/C", "code", normPath)
		} else {
			runCmd = DefaultCommandRunner(runCtx, "herdr", "pane", "run", paneID, "opencode", "--prompt", quotedPrompt)
		}
		runCmd.Dir = normPath
		runCmd.Env = BuildEnv(ctx.EnvAllowlist)
		if err := runCmd.Run(); err == nil {
			lastRunErr = nil
			break
		} else {
			lastRunErr = err
		}
	}
	_ = lastRunErr

	// 2. Branching por kind:
	//   - fx / zcode: TUIs inyectables via pane. Mismo patrón: wait-output
	//     del banner de readiness, send-text del prompt, send-keys Enter.
	//     Herdr no registra estos kinds (los adapters nativos no existen),
	//     así que se saltea `herdr agent start`.
	//   - code: GUI de VS Code, NO inyectable. Prompt va al portapapeles
	//     (CopyToClipboard) para que el operador lo pegue con Ctrl+V, y se
	//     registra con `herdr agent start --kind code` para que el resto del
	//     pipeline (read/focus/wait) pueda operar.
	switch agentKind {
	case "fx":
		return runHerdrPanePrompt(runCtx, ctx, normPath, paneID, prompt, fxReadyMarker, "fx")
	case "zcode":
		return runHerdrPanePrompt(runCtx, ctx, normPath, paneID, prompt, zcodeReadyMarker, "zcode")
	case "code":
		if err := copyToClipboardFn(prompt); err != nil {
			return fmt.Errorf("code prompt copy-to-clipboard failed: %w", err)
		}
		startCmd := DefaultCommandRunner(runCtx, "herdr", "agent", "start", targetName, "--kind", "code", "--pane", paneID)
		startCmd.Dir = normPath
		startCmd.Env = BuildEnv(ctx.EnvAllowlist)
		if err := startCmd.Run(); err != nil {
			return fmt.Errorf("code agent start failed: %w", err)
		}
		return nil
	}

	// 3. Register agent detection in Herdr for telemetry, read, focus, and wait
	startCmd := DefaultCommandRunner(runCtx, "herdr", "agent", "start", targetName, "--kind", agentKind, "--pane", paneID)
	startCmd.Dir = normPath
	startCmd.Env = BuildEnv(ctx.EnvAllowlist)
	return startCmd.Run()
}

// runHerdrPanePrompt inyecta el prompt en un TUI ya lanzado (fx, zcode u
// otros kinds inyectables a futuro). Los comandos de pane son agnósticos
// del kind (requerido porque `herdr agent prompt` depende de un registro
// que falla para fx/zcode): espera del banner de readiness, send-text del
// prompt y Enter para enviarlo.
//
// FALLBACK (issue #6 / AC4): si el banner de readiness no aparece (el
// TUI cambió su texto, arrancó en un estado raro, etc.), el wait-output
// va a timeout. En vez de abortar, proseguimos con send-text igual: el
// prompt llega al pane, el operador lo ve aunque el TUI no marque
// readiness formal. La inyección exitosa es la prioridad.
func runHerdrPanePrompt(runCtx context.Context, ctx ExecContext, dir string, paneID string, prompt string, marker string, label string) error {
	waitCmd := DefaultCommandRunner(runCtx, "herdr", "pane", "wait-output", "--match", marker, paneID)
	waitCmd.Dir = dir
	waitCmd.Env = BuildEnv(ctx.EnvAllowlist)
	waitErr := waitCmd.Run()
	if waitErr != nil {
		// Soft-fail: el banner no apareció. Logueamos al stderr del proceso
		// (no abortamos) y proseguimos con send-text. El operador puede
		// monitorear el pane y, si el prompt no llegó, reintentar manualmente.
		fmt.Fprintf(os.Stderr, "warn: %s readiness wait timeout (marker=%q): %v — proceeding with send-text\n", label, marker, waitErr)
	}

	sendCmd := DefaultCommandRunner(runCtx, "herdr", "pane", "send-text", paneID, prompt)
	sendCmd.Dir = dir
	sendCmd.Env = BuildEnv(ctx.EnvAllowlist)
	if err := sendCmd.Run(); err != nil {
		return fmt.Errorf("%s prompt send-text failed: %w", label, err)
	}

	enterCmd := DefaultCommandRunner(runCtx, "herdr", "pane", "send-keys", paneID, "Enter")
	enterCmd.Dir = dir
	enterCmd.Env = BuildEnv(ctx.EnvAllowlist)
	if err := enterCmd.Run(); err != nil {
		return fmt.Errorf("%s prompt submit failed: %w", label, err)
	}
	return nil
}

// RunHerdrAgentPrompt sends a prompt to the target agent, waiting for warmup and retrying
func RunHerdrAgentPrompt(ctx ExecContext, targetName string, prompt string) error {
	normPath := filepath.Clean(ctx.Cwd)
	runCtx, cancel := commandCtx(ctx, agentCmdTimeout)
	defer cancel()

	// Wait 1.2s for agent TTY / REPL to finish initializing
	time.Sleep(1200 * time.Millisecond)

	var lastErr error
	for attempt := 0; attempt < 4; attempt++ {
		cmd := DefaultCommandRunner(runCtx, "herdr", "agent", "prompt", targetName, prompt)
		cmd.Dir = normPath
		cmd.Env = BuildEnv(ctx.EnvAllowlist)
		if err := cmd.Run(); err == nil {
			return nil
		} else {
			lastErr = err
		}
		time.Sleep(600 * time.Millisecond)
	}
	return lastErr
}

// RunHerdrAgentWait waits for the agent to reach done, blocked, or idle
func RunHerdrAgentWait(ctx context.Context, targetName string) (string, error) {
	cmd := DefaultCommandRunner(ctx, "herdr", "agent", "wait", targetName, "--until", "done", "--until", "blocked", "--until", "idle")
	out, err := cmd.CombinedOutput()
	outStr := strings.TrimSpace(string(out))
	if strings.Contains(outStr, "blocked") {
		return "blocked", nil
	}
	if strings.Contains(outStr, "done") || strings.Contains(outStr, "idle") {
		return "done", nil
	}
	return outStr, err
}

// RunHerdrAgentRead returns live terminal text snapshot from the agent pane
func RunHerdrAgentRead(targetName string, lines int) string {
	if lines <= 0 {
		lines = 10
	}
	runCtx, cancel := context.WithTimeout(context.Background(), quickCmdTimeout)
	defer cancel()
	cmd := DefaultCommandRunner(runCtx, "herdr", "agent", "read", targetName, "--lines", fmt.Sprintf("%d", lines), "--format", "text")
	out, err := cmd.Output()
	if err != nil {
		return ""
	}
	return string(out)
}

// RunHerdrAgentFocus jumps focus to the agent pane in Herdr
func RunHerdrAgentFocus(targetName string) error {
	runCtx, cancel := context.WithTimeout(context.Background(), quickCmdTimeout)
	defer cancel()
	cmd := DefaultCommandRunner(runCtx, "herdr", "agent", "focus", targetName)
	return cmd.Run()
}

// RunHerdrTabClose closes a tab in Herdr
func RunHerdrTabClose(tabID string) error {
	if tabID == "" {
		return nil
	}
	runCtx, cancel := context.WithTimeout(context.Background(), agentCmdTimeout)
	defer cancel()
	cmd := DefaultCommandRunner(runCtx, "herdr", "tab", "close", tabID)
	return cmd.Run()
}

// RunHerdrTabAgent creates a dedicated Tab in Herdr for the worktree and starts the agent
func RunHerdrTabAgent(ctx ExecContext, issueID string, agentKind string, prompt string) error {
	label := "issue-" + issueID
	_, paneID, err := RunHerdrTabCreate(ctx, label)
	if err != nil {
		return err
	}
	targetName := "loom-" + issueID
	if prompt == "" {
		prompt = "Lee tasks.md y ejecuta las tareas de desarrollo con TDD."
	}
	return RunHerdrAgentStart(ctx, targetName, agentKind, paneID, prompt)
}

// RunHerdrVisualWorktree splits a pane in Herdr focused on the worktree path and launches OpenCode interactively
func RunHerdrVisualWorktree(ctx ExecContext, issueID string, prompt string) {
	_ = RunHerdrTabAgent(ctx, issueID, "opencode", prompt)
}

// OpenInExplorer opens the worktree folder directly in Windows Explorer
func OpenInExplorer(dirPath string) error {
	normPath := filepath.Clean(dirPath)
	cmd := DefaultCommandRunner(context.Background(), "explorer.exe", normPath)
	return cmd.Start()
}

func RunCodegraphInit(ctx ExecContext) error {
	normPath := filepath.Clean(ctx.Cwd)
	if _, lookErr := exec.LookPath("codegraph"); lookErr == nil {
		runCtx, cancel := commandCtx(ctx, codegraphInitTimeout)
		defer cancel()
		cmd := DefaultCommandRunner(runCtx, "codegraph", "init", ".")
		cmd.Dir = normPath
		cmd.Env = BuildEnv(ctx.EnvAllowlist)
		return cmd.Run()
	}
	return nil
}

func BuildEnv(allowlist []string) []string {
	if len(allowlist) == 0 {
		allowlist = []string{
			"HOME", "PATH", "TEMP", "TMP", "USERPROFILE", "SYSTEMROOT", "WINDIR",
			"LOCALAPPDATA", "APPDATA", "COMSPEC", "PATHEXT", "HOMEDRIVE", "HOMEPATH",
			"SYSTEMDRIVE", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "COMMONPROGRAMFILES",
			"OS", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "USER", "LOGNAME", "SHELL",
		}
	}

	allowMap := make(map[string]bool)
	for _, k := range allowlist {
		allowMap[strings.ToUpper(k)] = true
	}

	// Always deny GITHUB_TOKEN by default unless explicitly in allowlist
	if !allowMap["GITHUB_TOKEN"] {
		allowMap["GITHUB_TOKEN"] = false
	}

	var filtered []string
	for _, env := range os.Environ() {
		parts := strings.SplitN(env, "=", 2)
		if len(parts) > 0 {
			key := strings.ToUpper(parts[0])
			if allowMap[key] {
				filtered = append(filtered, env)
			}
		}
	}
	return filtered
}

// CopyToClipboard copies the given text to the Windows system clipboard
func CopyToClipboard(text string) error {
	cmd := exec.Command("clip.exe")
	cmd.Stdin = strings.NewReader(text)
	return cmd.Run()
}

func BuildAgentCmd(ctx ExecContext, promptText string, agentChoice string) *exec.Cmd {
	normPath := filepath.Clean(ctx.Cwd)
	var cmd *exec.Cmd

	if agentChoice == "" {
		agentChoice = strings.ToLower(strings.TrimSpace(os.Getenv("LOOM_AGENT")))
	}

	if agentChoice == "agy" {
		if _, lookErr := exec.LookPath("agy"); lookErr == nil {
			cmd = exec.Command("cmd.exe", "/C", "agy", "--prompt-interactive", promptText)
		}
	} else if agentChoice == "opencode" {
		if _, lookErr := exec.LookPath("opencode"); lookErr == nil {
			cmd = exec.Command("cmd.exe", "/C", "opencode", "--prompt", promptText)
		}
	} else if agentChoice == "zcode" {
		_ = CopyToClipboard(promptText)
		cmd = exec.Command("cmd.exe", "/C", "zcode", normPath)
	} else if agentChoice == "code" {
		_ = CopyToClipboard(promptText)
		cmd = exec.Command("cmd.exe", "/C", "code", normPath)
	} else if agentChoice == "fx" {
		if runtime.GOOS == "windows" {
			if _, lookErr := exec.LookPath("wsl"); lookErr == nil {
				cmd = exec.Command("wsl.exe", "-d", "Ubuntu", "--cd", normPath, "bash", "-lc", "fx")
			}
		} else {
			cmd = exec.Command("fx")
		}
	}

	if cmd == nil {
		if runtime.GOOS == "windows" {
			if _, lookErr := exec.LookPath("agy"); lookErr == nil {
				cmd = exec.Command("cmd.exe", "/C", "agy", "--prompt-interactive", promptText)
			} else if _, lookErr := exec.LookPath("opencode"); lookErr == nil {
				cmd = exec.Command("cmd.exe", "/C", "opencode", "--prompt", promptText)
			} else if _, lookErr := exec.LookPath("zcode"); lookErr == nil {
				cmd = exec.Command("cmd.exe", "/C", "zcode", normPath)
			} else if _, lookErr := exec.LookPath("code"); lookErr == nil {
				cmd = exec.Command("cmd.exe", "/C", "code", normPath)
			} else if _, lookErr := exec.LookPath("wsl"); lookErr == nil {
				cmd = exec.Command("wsl.exe", "-d", "Ubuntu", "--cd", normPath, "bash", "-lc", "fx")
			} else {
				cmd = exec.Command("cmd.exe", "/C", "echo [Loom] Worktree active at "+normPath+" && pause")
			}
		} else {
			if _, lookErr := exec.LookPath("agy"); lookErr == nil {
				cmd = exec.Command("agy", "--prompt-interactive", promptText)
			} else if _, lookErr := exec.LookPath("opencode"); lookErr == nil {
				cmd = exec.Command("opencode", "--prompt", promptText)
			} else if _, lookErr := exec.LookPath("zcode"); lookErr == nil {
				cmd = exec.Command("zcode", normPath)
			} else if _, lookErr := exec.LookPath("code"); lookErr == nil {
				cmd = exec.Command("code", normPath)
			} else if _, lookErr := exec.LookPath("fx"); lookErr == nil {
				cmd = exec.Command("fx")
			} else {
				cmd = exec.Command("sh", "-c", "echo '[Loom] Worktree active at "+normPath+"'")
			}
		}
	}

	cmd.Dir = normPath
	cmd.Env = BuildEnv(ctx.EnvAllowlist)
	return cmd
}

func RunHerdrStartHeadless(ctx ExecContext, cmdArgs string) error {
	if ctx.Ctx == nil {
		ctx.Ctx = context.Background()
	}

	// If a command timeout is set, wrap ctx
	if ctx.CommandTimeout > 0 {
		var cancel context.CancelFunc
		ctx.Ctx, cancel = context.WithTimeout(ctx.Ctx, ctx.CommandTimeout)
		defer cancel()
	}

	normPath := filepath.Clean(ctx.Cwd)
	logPath := filepath.Join(normPath, "execution.log")

	promptText := cmdArgs
	if promptText == "" || promptText == "start" {
		matches, _ := filepath.Glob(filepath.Join(normPath, "openspec", "changes", "issue-*"))
		if len(matches) > 0 {
			issueDir := filepath.Base(matches[0])
			promptText = fmt.Sprintf("Estás trabajando exclusivamente dentro del worktree aislado de este issue (%s). Lee openspec/changes/%s/ (proposal.md, design.md, specs/spec.md, tasks.md) y ejecuta las tareas en este directorio con la skill sdd-apply bajo TDD estricto (RED antes que GREEN). Todas las modificaciones deben realizarse en este worktree sin tocar el repositorio principal.", normPath, issueDir)
		} else {
			promptText = fmt.Sprintf("Estás trabajando exclusivamente dentro del worktree aislado de este issue (%s). Lee tasks.md y ejecuta las tareas de desarrollo con TDD estricto en este directorio sin tocar el repositorio principal.", normPath)
		}
	}

	var cmd *exec.Cmd
	agentChoice := strings.ToLower(strings.TrimSpace(os.Getenv("LOOM_AGENT")))
	if agentChoice == "fx" {
		if _, lookErr := exec.LookPath("wsl"); lookErr == nil {
			escapedPrompt := strings.ReplaceAll(promptText, `"`, `\"`)
			wslCmd := fmt.Sprintf("fx ask --auto \"%s\"", escapedPrompt)
			cmd = DefaultCommandRunner(ctx.Ctx, "wsl.exe", "-d", "Ubuntu", "--cd", normPath, "bash", "-lc", wslCmd)
		}
	} else if agentChoice == "opencode" {
		if _, lookErr := exec.LookPath("opencode"); lookErr == nil {
			cmd = DefaultCommandRunner(ctx.Ctx, "cmd.exe", "/C", "opencode", "run", promptText, "--auto")
		}
	} else if agentChoice == "zcode" {
		_ = CopyToClipboard(promptText)
		cmd = DefaultCommandRunner(ctx.Ctx, "cmd.exe", "/C", "zcode", normPath)
	} else if agentChoice == "code" {
		_ = CopyToClipboard(promptText)
		cmd = DefaultCommandRunner(ctx.Ctx, "cmd.exe", "/C", "code", normPath)
	} else if agentChoice == "agy" {
		if _, lookErr := exec.LookPath("agy"); lookErr == nil {
			cmd = DefaultCommandRunner(ctx.Ctx, "agy", "--auto", "--prompt", promptText)
		}
	}

	if cmd == nil {
		if _, lookErr := exec.LookPath("opencode"); lookErr == nil {
			cmd = DefaultCommandRunner(ctx.Ctx, "cmd.exe", "/C", "opencode", "run", promptText, "--auto")
		} else if _, lookErr := exec.LookPath("agy"); lookErr == nil {
			cmd = DefaultCommandRunner(ctx.Ctx, "agy", "--auto", "--prompt", promptText)
		} else if _, lookErr := exec.LookPath("zcode"); lookErr == nil {
			cmd = DefaultCommandRunner(ctx.Ctx, "cmd.exe", "/C", "zcode", normPath)
		} else if _, lookErr := exec.LookPath("code"); lookErr == nil {
			cmd = DefaultCommandRunner(ctx.Ctx, "cmd.exe", "/C", "code", normPath)
		} else if _, lookErr := exec.LookPath("wsl"); lookErr == nil {
			escapedPrompt := strings.ReplaceAll(promptText, `"`, `\"`)
			wslCmd := fmt.Sprintf("fx ask --auto \"%s\"", escapedPrompt)
			cmd = DefaultCommandRunner(ctx.Ctx, "wsl.exe", "-d", "Ubuntu", "--cd", normPath, "bash", "-lc", wslCmd)
		} else {
			cmd = DefaultCommandRunner(ctx.Ctx, "cmd.exe", "/C", "echo [Loom] Worktree isolated & tasks.md materialized at "+normPath)
		}
	}
	cmd.Dir = normPath
	cmd.Env = BuildEnv(ctx.EnvAllowlist)

	// Stream stdout & stderr to execution.log for live TUI visibility
	logFile, err := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0644)
	if err == nil {
		defer logFile.Close()
		cmd.Stdout = logFile
		cmd.Stderr = logFile
	}

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("agent start failed: %w", err)
	}

	done := make(chan error, 1)
	go func() {
		done <- cmd.Wait()
	}()

	select {
	case <-ctx.Ctx.Done():
		if cmd.Process != nil && cmd.Process.Pid > 0 {
			_ = KillProcessTree(cmd.Process.Pid)
		}
		if logFile != nil {
			_ = logFile.Close()
		}
		return ctx.Ctx.Err()
	case err := <-done:
		if logFile != nil {
			_ = logFile.Close()
		}
		if err != nil {
			return fmt.Errorf("agent execution failed: %w", err)
		}
		return nil
	}
}

// ReadRecentLogs returns the last maxLines lines from review.log or execution.log if present
func ReadRecentLogs(worktreePath string, maxLines int) string {
	if worktreePath == "" {
		return ""
	}
	reviewLogPath := filepath.Join(worktreePath, "review.log")
	if rData, rErr := os.ReadFile(reviewLogPath); rErr == nil && len(rData) > 0 {
		lines := strings.Split(strings.TrimSpace(string(rData)), "\n")
		if maxLines > 0 && len(lines) > maxLines {
			lines = lines[len(lines)-maxLines:]
		}
		return "[Review Log]\n" + strings.Join(lines, "\n")
	}
	logPath := filepath.Join(worktreePath, "execution.log")
	data, err := os.ReadFile(logPath)
	if err != nil || len(data) == 0 {
		return ""
	}
	lines := strings.Split(strings.TrimSpace(string(data)), "\n")
	if maxLines > 0 && len(lines) > maxLines {
		lines = lines[len(lines)-maxLines:]
	}
	return strings.Join(lines, "\n")
}

// CommandRunner defines the execution function
type CommandRunner func(ctx context.Context, name string, args ...string) *exec.Cmd

// DefaultCommandRunner uses real os/exec.CommandContext
var DefaultCommandRunner CommandRunner = exec.CommandContext

// copyToClipboardFn es el seam mockeable de CopyToClipboard. Por default
// delega a la implementación real; los tests lo sobreescriben para
// capturar la invocación sin tocar el portapapeles del sistema.
var copyToClipboardFn = CopyToClipboard

// ErrGentleAINotInstalled signals that governance review cannot run because
// the gentle-ai binary is absent. Callers must treat it as a failed review
// (unmanaged seal), never as a pass.
var ErrGentleAINotInstalled = errors.New("gentle-ai not installed: risk review cannot run")

// Default hang cutoffs for external commands when the caller sets none.
const (
	quickCmdTimeout       = 10 * time.Second // status/read/focus probes
	agentCmdTimeout       = 30 * time.Second // agent start/prompt/tab create/close
	orcaRemoveTimeout     = 30 * time.Second
	orcaCreateTimeout     = 2 * time.Minute
	reviewModeTimeout     = 2 * time.Minute
	prCreateTimeout       = 2 * time.Minute
	codegraphInitTimeout  = 2 * time.Minute
	pytestEvidenceTimeout = 10 * time.Minute // evidencia ejecutable (-m pytest) del ciclo de review
)

// commandCtx resolves the context for an external command: the caller's Ctx
// wins as parent, CommandTimeout caps it when set, and the per-operation
// fallback applies otherwise. It never returns a bare Background, so every
// external command has a hang cutoff.
func commandCtx(ctx ExecContext, fallback time.Duration) (context.Context, context.CancelFunc) {
	base := ctx.Ctx
	if base == nil {
		base = context.Background()
	}
	timeout := ctx.CommandTimeout
	if timeout <= 0 {
		timeout = fallback
	}
	return context.WithTimeout(base, timeout)
}

func RunGentleReviewMode(ctx ExecContext) (GentleGateResult, error) {
	binPath, lookErr := exec.LookPath("gentle-ai")
	if lookErr != nil {
		// Fail closed: a review that cannot run must never count as a pass.
		return GentleGateResult{Allowed: false, Reason: "gentle-ai not installed"}, ErrGentleAINotInstalled
	}
	normPath := filepath.Clean(ctx.Cwd)
	revCtx, cancel := commandCtx(ctx, reviewModeTimeout)
	defer cancel()

	cmd := DefaultCommandRunner(revCtx, binPath, "review", "validate", "--gate", "pre-pr", "--cwd", normPath)
	cmd.Dir = normPath
	if len(ctx.EnvAllowlist) > 0 {
		cmd.Env = BuildEnv(ctx.EnvAllowlist)
	}
	out, err := cmd.CombinedOutput()

	// Save review log for live telemetry in Loom inspector
	reviewLogPath := filepath.Join(normPath, "review.log")
	_ = os.WriteFile(reviewLogPath, out, 0644)

	var gateResult GentleGateResult
	trimmed := bytes.TrimSpace(out)
	if jsonErr := json.Unmarshal(trimmed, &gateResult); jsonErr != nil {
		if err != nil {
			return GentleGateResult{Allowed: false, Reason: string(out)}, fmt.Errorf("governance validation error: %q (%w)", string(out), err)
		}
		return GentleGateResult{Allowed: false, Reason: string(out)}, fmt.Errorf("invalid governance gate response: %q (%w)", string(out), jsonErr)
	}

	if err != nil && gateResult.Allowed {
		return gateResult, fmt.Errorf("governance validation command failed with exit error: %w", err)
	}

	if !gateResult.Allowed {
		// Per the gentle-ai review-integration contract, a result with
		// delivery "disabled/unmanaged" is a pass-through to ordinary
		// repository policy (hooks, tests, CI), not a blocked gate. Only
		// non-disabled rejections must fail closed. See:
		// gentle-ai.review-integration contract v2, "Delivery" clause.
		if gateResult.Delivery == "disabled/unmanaged" {
			return gateResult, nil
		}
		return gateResult, fmt.Errorf("governance review not satisfied (%s): %s", gateResult.Delivery, gateResult.Reason)
	}

	return gateResult, nil
}

func RunOrcaRemove(ctx ExecContext) error {
	if ctx.Cwd == "" {
		return nil
	}
	normPath := filepath.Clean(ctx.Cwd)

	homeDir, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("failed to get user home dir: %w", err)
	}
	validPrefix := filepath.Join(homeDir, ".loom", "worktrees")

	rel, err := filepath.Rel(validPrefix, normPath)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		// Allow test directories in TempDir for unit tests
		tempRel, tempErr := filepath.Rel(os.TempDir(), normPath)
		if tempErr != nil || tempRel == ".." || strings.HasPrefix(tempRel, ".."+string(filepath.Separator)) {
			return fmt.Errorf("path traversal attempt rejected: %s", normPath)
		}
	}

	orcaCtx, cancel := commandCtx(ctx, orcaRemoveTimeout)
	defer cancel()

	// Try removing from orca if available
	if _, lookErr := exec.LookPath("orca"); lookErr == nil {
		cmd := DefaultCommandRunner(orcaCtx, "orca", "worktree", "rm", "--worktree", "path:"+normPath, "--force")
		cmd.Env = BuildEnv(ctx.EnvAllowlist)
		_ = cmd.Run()
	}

	// Try removing git worktree if git is available
	baseRepoDir := ResolveTargetRepoDir()
	if _, lookErr := exec.LookPath("git"); lookErr == nil {
		cmd := DefaultCommandRunner(orcaCtx, "git", "worktree", "remove", "--force", normPath)
		cmd.Dir = baseRepoDir
		cmd.Env = BuildEnv(ctx.EnvAllowlist)
		_ = cmd.Run()
	}

	// On Windows, retry RemoveAll with exponential backoff to handle OS file handle release latency
	var removeErr error
	for attempt := 0; attempt < 5; attempt++ {
		removeErr = os.RemoveAll(normPath)
		if removeErr == nil || os.IsNotExist(removeErr) {
			return nil
		}
		time.Sleep(time.Duration(50*(attempt+1)) * time.Millisecond)
	}
	return removeErr
}

func RunCreatePR(ctx ExecContext, issueID, title, repo string) (string, error) {
	normPath := filepath.Clean(ctx.Cwd)
	if _, lookErr := exec.LookPath("gh"); lookErr == nil {
		prCtx, cancel := commandCtx(ctx, prCreateTimeout)
		defer cancel()
		body := fmt.Sprintf("Fixes #%s\n\nAutomated delivery by Loom AI Orchestrator.", issueID)
		args := []string{"pr", "create", "--title", title, "--body", body}
		if repo != "" {
			args = append(args, "--repo", repo)
		}
		cmd := DefaultCommandRunner(prCtx, "gh", args...)
		cmd.Dir = normPath
		cmd.Env = BuildEnv(append(ctx.EnvAllowlist, "GITHUB_TOKEN"))
		output, err := cmd.CombinedOutput()
		if err != nil {
			return "", fmt.Errorf("gh pr create failed: %s (%w)", string(output), err)
		}
		return strings.TrimSpace(string(output)), nil
	}
	return "", fmt.Errorf("gh CLI not installed")
}

// RunCodeGraphInit initializes the CodeGraph index for a worktree.
// It prefers gentle-ai if installed, falling back to upstream codegraph CLI.
func RunCodeGraphInit(ctx ExecContext) error {
	if ctx.Cwd == "" {
		return nil
	}
	normPath := filepath.Clean(ctx.Cwd)
	if normPath == "" || normPath == "." {
		return nil
	}

	initCtx, cancel := commandCtx(ctx, codegraphInitTimeout)
	defer cancel()

	if _, lookErr := exec.LookPath("gentle-ai"); lookErr == nil {
		cmd := DefaultCommandRunner(initCtx, "gentle-ai", "codegraph", "init", "--cwd", normPath)
		cmd.Dir = normPath
		cmd.Env = BuildEnv(ctx.EnvAllowlist)
		return cmd.Run()
	}

	if _, lookErr := exec.LookPath("codegraph"); lookErr == nil {
		cmd := DefaultCommandRunner(initCtx, "codegraph", "init", normPath)
		cmd.Dir = normPath
		cmd.Env = BuildEnv(ctx.EnvAllowlist)
		return cmd.Run()
	}

	return nil
}
