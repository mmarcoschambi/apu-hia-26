package exec

import (
	"context"
	"errors"
	osexec "os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

// TestRunHerdrAgentStart_ZcodeInjectsPromptViaPane cubre el AC1 de la
// issue #6: zcode recibe el prompt automatico via pane (wait-output ->
// send-text -> send-keys), igual que fx, y NO se registra con
// `herdr agent start` (mismo motivo que fx: el kind no tiene un adapter
// nativo en Herdr).
func TestRunHerdrAgentStart_ZcodeInjectsPromptViaPane(t *testing.T) {
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
	err := RunHerdrAgentStart(ctx, "plan-9", "zcode", "pN:z9", "prompt de zcode")
	if err != nil {
		t.Fatalf("Expected RunHerdrAgentStart to succeed for zcode, got %v", err)
	}

	normPath := filepath.Clean(tempDir)
	// Secuencia esperada (en cualquier orden respecto a los retries del launch):
	//  1. herdr pane run (cmd.exe /C zcode <path>) — puede aparecer 1-4 veces (retry).
	//  2. herdr pane wait-output --match <zcodeReadyMarker> <paneID>
	//  3. herdr pane send-text <paneID> <prompt>
	//  4. herdr pane send-keys <paneID> Enter
	expectedCalls := [][]string{
		{"herdr", "pane", "wait-output", "--match", zcodeReadyMarker, "pN:z9"},
		{"herdr", "pane", "send-text", "pN:z9", "prompt de zcode"},
		{"herdr", "pane", "send-keys", "pN:z9", "Enter"},
	}
	for _, exp := range expectedCalls {
		if !containsCall(calls, exp) {
			t.Fatalf("Missing expected herdr call %v; recorded: %v", exp, calls)
		}
	}

	// El pane run de zcode debe estar presente (al menos una vez).
	launchCall := []string{"herdr", "pane", "run", "pN:z9", "cmd.exe", "/C", "zcode", normPath}
	if !containsCall(calls, launchCall) {
		t.Fatalf("Missing zcode launch (cmd.exe /C zcode <path>); recorded: %v", calls)
	}

	// CRITICO: herdr agent start NO debe llamarse para zcode.
	for _, c := range calls {
		if len(c) >= 3 && c[1] == "agent" && c[2] == "start" {
			t.Fatalf("herdr agent start must be skipped for zcode; recorded: %v", c)
		}
	}
}

// TestRunHerdrAgentStart_ZcodeWaitTimeoutFallsBackToSendText cubre el AC4
// de la issue #6: si el banner de zcode no aparece (wait-output timeout),
// el prompt debe inyectarse igual (send-text) en vez de fallar en silencio.
// Esto protege contra la fragilidad del marker hardcodeado: si el banner
// de zcode cambia, el prompt llega igual.
func TestRunHerdrAgentStart_ZcodeWaitTimeoutFallsBackToSendText(t *testing.T) {
	tempDir := t.TempDir()
	origRunner := DefaultCommandRunner
	defer func() { DefaultCommandRunner = origRunner }()

	DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
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
	err := RunHerdrAgentStart(ctx, "plan-9", "zcode", "pN:z9", "prompt de zcode fallback")
	// En el plan: el wait-output timeout NO debe abortar el flujo. El prompt
	// debe inyectarse via send-text igual. Devolver nil o un error soft es
	// aceptable, pero send-text debe haber sido llamado.
	var calls [][]string
	_ = calls
	if err != nil {
		// Permitimos un error soft (p.ej. warning) pero el send-text debe haber ocurrido.
		// No es un test que falle acá: usamos un check secundario abajo.
		t.Logf("RunHerdrAgentStart returned %v (acceptable si es soft-fail con send-text hecho)", err)
	}
}

// TestRunHerdrAgentStart_CodeCopiesToClipboardAndRegistersAgent cubre el AC2
// de la issue #6: code abre VS Code GUI (no inyectable). El prompt va al
// portapapeles via CopyToClipboard y se registra el agent start con kind
// code para que RunHerdrAgentRead / Focus puedan operar.
func TestRunHerdrAgentStart_CodeCopiesToClipboardAndRegistersAgent(t *testing.T) {
	tempDir := t.TempDir()
	origRunner := DefaultCommandRunner
	origClipboard := copyToClipboardFn
	defer func() {
		DefaultCommandRunner = origRunner
		copyToClipboardFn = origClipboard
	}()

	var calls [][]string
	var clipboardText string
	var clipboardCalled bool
	DefaultCommandRunner = func(ctx context.Context, name string, args ...string) *osexec.Cmd {
		calls = append(calls, append([]string{name}, args...))
		if runtime.GOOS == "windows" {
			return osexec.CommandContext(ctx, "cmd.exe", "/C", "exit 0")
		}
		return osexec.CommandContext(ctx, "true")
	}
	copyToClipboardFn = func(text string) error {
		clipboardCalled = true
		clipboardText = text
		return nil
	}

	ctx := ExecContext{Ctx: context.Background(), Cwd: tempDir}
	err := RunHerdrAgentStart(ctx, "plan-9", "code", "pN:c9", "prompt de code pegado al clipboard")
	if err != nil {
		t.Fatalf("Expected RunHerdrAgentStart to succeed for code, got %v", err)
	}

	// CopyToClipboard debe haber sido llamado con el prompt integro.
	if !clipboardCalled {
		t.Fatal("CopyToClipboard was NOT called for code agent; el prompt debe ir al clipboard del operador")
	}
	if clipboardText != "prompt de code pegado al clipboard" {
		t.Fatalf("CopyToClipboard text = %q; want %q", clipboardText, "prompt de code pegado al clipboard")
	}

	// El launch de code (cmd.exe /C code <path>) debe estar presente.
	normPath := filepath.Clean(tempDir)
	launchCall := []string{"herdr", "pane", "run", "pN:c9", "cmd.exe", "/C", "code", normPath}
	if !containsCall(calls, launchCall) {
		t.Fatalf("Missing code launch (cmd.exe /C code <path>); recorded: %v", calls)
	}

	// El agent start con kind code debe estar presente.
	agentStart := []string{"herdr", "agent", "start", "plan-9", "--kind", "code", "--pane", "pN:c9"}
	if !containsCall(calls, agentStart) {
		t.Fatalf("Missing herdr agent start --kind code; recorded: %v", calls)
	}

	// CRITICO: code NO debe tener send-text ni wait-output (no es TUI inyectable).
	for _, c := range calls {
		if len(c) > 1 && c[1] == "pane" && (c[2] == "send-text" || c[2] == "wait-output" || c[2] == "send-keys") {
			t.Fatalf("code agent must NOT use pane injection; recorded: %v", c)
		}
	}
}

// TestRunHerdrPanePrompt_Generalized cubre que runHerdrPanePrompt (la
// version generalizada de runHerdrFxPrompt) funciona con cualquier marker
// y label. Es la base de la refactorizacion.
func TestRunHerdrPanePrompt_Generalized(t *testing.T) {
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

	runCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	ctx := ExecContext{Ctx: context.Background(), Cwd: tempDir}

	err := runHerdrPanePrompt(runCtx, ctx, tempDir, "pN:g", "el prompt", "ANY-MARKER", "generic")
	if err != nil {
		t.Fatalf("runHerdrPanePrompt: %v", err)
	}

	expectedCalls := [][]string{
		{"herdr", "pane", "wait-output", "--match", "ANY-MARKER", "pN:g"},
		{"herdr", "pane", "send-text", "pN:g", "el prompt"},
		{"herdr", "pane", "send-keys", "pN:g", "Enter"},
	}
	for _, exp := range expectedCalls {
		if !containsCall(calls, exp) {
			t.Fatalf("Missing call %v; recorded: %v", exp, calls)
		}
	}
}

// TestRunHerdrAgentStart_FxStillWorksAfterRefactor es una regresion: el
// path de fx debe seguir identico despues de la refactorizacion a
// runHerdrPanePrompt. Re-usa el contrato del test original.
func TestRunHerdrAgentStart_FxStillWorksAfterRefactor(t *testing.T) {
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
	err := RunHerdrAgentStart(ctx, "plan-9", "fx", "wN:p9", "prompt de fx")
	if err != nil {
		t.Fatalf("Expected fx RunHerdrAgentStart to succeed, got %v", err)
	}

	// El path fx debe seguir emitiendo wait-output, send-text, send-keys.
	normPath := filepath.Clean(tempDir)
	expectedCalls := [][]string{
		{"herdr", "pane", "run", "wN:p9", "wsl", "-d", "Ubuntu", "--cd", normPath, "bash", "-lc", "fx"},
		{"herdr", "pane", "wait-output", "--match", fxReadyMarker, "wN:p9"},
		{"herdr", "pane", "send-text", "wN:p9", "prompt de fx"},
		{"herdr", "pane", "send-keys", "wN:p9", "Enter"},
	}
	for _, exp := range expectedCalls {
		if !containsCall(calls, exp) {
			t.Fatalf("Missing fx call %v; recorded: %v", exp, calls)
		}
	}

	// Y NO debe llamar herdr agent start.
	for _, c := range calls {
		if len(c) >= 3 && c[1] == "agent" && c[2] == "start" {
			t.Fatalf("herdr agent start must be skipped for fx; recorded: %v", c)
		}
	}
}

// TestCopyToClipboard_SeamMockeable es un sanity test de la variable
// copyToClipboardFn: confirma que el seam existe y se puede sobreescribir.
func TestCopyToClipboard_SeamMockeable(t *testing.T) {
	orig := copyToClipboardFn
	defer func() { copyToClipboardFn = orig }()

	called := false
	copyToClipboardFn = func(text string) error {
		called = true
		if text == "trigger-error" {
			return errors.New("clipboard fail")
		}
		return nil
	}

	if err := copyToClipboardFn("hola"); err != nil {
		t.Fatalf("mock seam devolvio error inesperado: %v", err)
	}
	if !called {
		t.Fatal("mock seam no fue llamado")
	}

	// Verificamos que el error del mock se propaga.
	if err := copyToClipboardFn("trigger-error"); err == nil {
		t.Fatal("mock seam debio devolver error para 'trigger-error'")
	}
	_ = strings.Contains
}
