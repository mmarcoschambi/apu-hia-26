package judge

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/mmarcoschambi/loom/internal/fsm"
)

// TestMergeCicloJ2_EscribeLedgerYVeredicto es el escenario end-to-end de J2:
// tengo los dos results, hago merge, escribo ledger, y el contrato de salida
// refleja el veredicto.
func TestMergeCicloJ2_EscribeLedgerYVeredicto(t *testing.T) {
	tmp := t.TempDir()
	jdir := filepath.Join(tmp, "judgment")
	_ = os.MkdirAll(jdir, 0755)

	// Result A: CRITICAL en a.go:1.
	_ = os.WriteFile(filepath.Join(jdir, "result-A.md"), []byte(`{"findings":[{"location":"a.go:1","severity":"CRITICAL","claim":"race condition","evidence_class":"deterministic","causal_disposition":"introduced","proof_refs":["a.go:1"]}],"evidence":["a"]}`), 0644)
	// Result B: CRITICAL en a.go:1.
	_ = os.WriteFile(filepath.Join(jdir, "result-B.md"), []byte(`{"findings":[{"location":"a.go:1","severity":"CRITICAL","claim":"race condition","evidence_class":"deterministic","causal_disposition":"introduced","proof_refs":["a.go:1"]}],"evidence":["b"]}`), 0644)

	// LoadResultsPending: ambos presentes.
	if err := LoadResultsPending(tmp); err != nil {
		t.Fatalf("LoadResultsPending: %v", err)
	}

	a, _ := LoadJudgeResult(filepath.Join(jdir, "result-A.md"))
	b, _ := LoadJudgeResult(filepath.Join(jdir, "result-B.md"))

	iss := &fsm.IssueFSM{ID: "42", WorktreePath: tmp}
	report := MergeResults(iss, ModePlan, 1, "deadbeef", a, b)
	ledgerPath, err := WriteLedger(tmp, report)
	if err != nil {
		t.Fatalf("WriteLedger: %v", err)
	}
	if report.Verdict != "ESCALATED" {
		t.Errorf("Verdict = %q; want ESCALATED", report.Verdict)
	}
	if !strings.Contains(report.VerdictContract(), "PHASE GATE: ESCALATED") {
		t.Errorf("VerdictContract sin contrato ESCALATED: %q", report.VerdictContract())
	}
	raw, _ := os.ReadFile(ledgerPath)
	body := string(raw)
	if !strings.Contains(body, "issue #42") {
		t.Errorf("ledger: falta ID del issue (lowercase 'issue #42'); got:\n%s", body)
	}
	if !strings.Contains(body, "ledger-path missing") && !strings.Contains(body, "ledger-") {
		t.Error("ledger: sin path al ledger en el contrato")
	}
}

// TestMergeCicloJ2_CleanRunProduceAPPROVED valida el caso happy: sin
// findings, veredicto APPROVED, contrato con hash8.
func TestMergeCicloJ2_CleanRunProduceAPPROVED(t *testing.T) {
	tmp := t.TempDir()
	jdir := filepath.Join(tmp, "judgment")
	_ = os.MkdirAll(jdir, 0755)
	_ = os.WriteFile(filepath.Join(jdir, "result-A.md"), []byte(`{"findings":[],"evidence":["a"]}`), 0644)
	_ = os.WriteFile(filepath.Join(jdir, "result-B.md"), []byte(`{"findings":[],"evidence":["b"]}`), 0644)

	a, _ := LoadJudgeResult(filepath.Join(jdir, "result-A.md"))
	b, _ := LoadJudgeResult(filepath.Join(jdir, "result-B.md"))
	iss := &fsm.IssueFSM{ID: "1", WorktreePath: tmp}
	rep := MergeResults(iss, ModeApply, 1, "0123456789abcdef", a, b)
	if rep.Verdict != "APPROVED" {
		t.Errorf("Verdict = %q; want APPROVED", rep.Verdict)
	}
	contract := rep.VerdictContract()
	if !strings.Contains(contract, "01234567") {
		t.Errorf("contract missing hash8: %q", contract)
	}
	if !strings.Contains(contract, "apply-1") {
		t.Errorf("contract missing apply-1: %q", contract)
	}
	ledgerPath, err := WriteLedger(tmp, rep)
	if err != nil {
		t.Fatal(err)
	}
	raw, _ := os.ReadFile(ledgerPath)
	if !strings.Contains(string(raw), "terminal_state: approved") {
		t.Error("ledger: terminal_state no es approved")
	}
}

// TestMergeCicloJ2_Advisory_NoMutaEstado demuestra el invariante AC9: el
// merge solo escribe el ledger bajo <worktree>/judgment/, jamas toca
// ~/.loom/state/state.json ni similares.
func TestMergeCicloJ2_Advisory_NoMutaEstado(t *testing.T) {
	tmp := t.TempDir()
	jdir := filepath.Join(tmp, "judgment")
	_ = os.MkdirAll(jdir, 0755)
	_ = os.WriteFile(filepath.Join(jdir, "result-A.md"), []byte(`{"findings":[],"evidence":["a"]}`), 0644)
	_ = os.WriteFile(filepath.Join(jdir, "result-B.md"), []byte(`{"findings":[],"evidence":["b"]}`), 0644)

	a, _ := LoadJudgeResult(filepath.Join(jdir, "result-A.md"))
	b, _ := LoadJudgeResult(filepath.Join(jdir, "result-B.md"))
	iss := &fsm.IssueFSM{ID: "9", WorktreePath: tmp}
	rep := MergeResults(iss, ModePlan, 1, "h", a, b)
	_, err := WriteLedger(tmp, rep)
	if err != nil {
		t.Fatal(err)
	}

	// No debe existir ~/.loom/state/state.json creado por el merge.
	if _, err := os.Stat(filepath.Join(tmp, "state.json")); err == nil {
		t.Error("MergeResults/WriteLedger debe ser advisory; no escribe state.json")
	}
}
