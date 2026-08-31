package judge

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/mmarcoschambi/loom/internal/fsm"
)

// TestEngineValid cubre el set cerrado del AC5 y la base del S10.
func TestEngineValid(t *testing.T) {
	for _, e := range ValidEngines {
		if !EngineValid(e) {
			t.Errorf("EngineValid(%q) = false; want true (in ValidEngines)", e)
		}
	}
	for _, e := range []string{"", "claude", "gpt", "unknown", "OpenCode"} {
		if EngineValid(e) {
			t.Errorf("EngineValid(%q) = true; want false", e)
		}
	}
}

// TestSameEngineWarn valida el warning del AC5 (S10) — texto exacto para que
// el operador lo pueda grep en logs.
func TestSameEngineWarn(t *testing.T) {
	if got := SameEngineWarn("opencode", "agy"); got != "" {
		t.Errorf("SameEngineWarn(diverse) = %q; want empty", got)
	}
	if got := SameEngineWarn("opencode", "opencode"); !strings.Contains(got, "WARNING") || !strings.Contains(got, "diversidad") {
		t.Errorf("SameEngineWarn(same) = %q; want WARNING + diversidad", got)
	}
}

// TestIsSevere calibra CRITICAL|WARNING vs SUGGESTION|INFO.
func TestIsSevere(t *testing.T) {
	if !IsSevere("CRITICAL") || !IsSevere("WARNING") {
		t.Error("CRITICAL y WARNING deben ser severos")
	}
	if IsSevere("SUGGESTION") || IsSevere("INFO") || IsSevere("") || IsSevere("FOO") {
		t.Error("SUGGESTION/INFO/''/FOO no son severos")
	}
}

// TestParseJudgeResultClean — un juez clean devuelve {findings:[], evidence:[...]}.
func TestParseJudgeResultClean(t *testing.T) {
	raw := `{"findings":[],"evidence":["12 criteria mapped to 14 BDD scenarios"]}`
	r, err := ParseJudgeResult(raw)
	if err != nil {
		t.Fatalf("ParseJudgeResult: %v", err)
	}
	if len(r.Findings) != 0 {
		t.Errorf("clean: findings = %d; want 0", len(r.Findings))
	}
	if len(r.Evidence) != 1 {
		t.Errorf("clean: evidence = %d; want 1", len(r.Evidence))
	}
}

// TestParseJudgeResultFenced — los jueces a veces escriben ```json ...```.
func TestParseJudgeResultFenced(t *testing.T) {
	raw := "noise before\n```json\n{\"findings\":[{\"location\":\"a.go:1\",\"severity\":\"WARNING\",\"claim\":\"x\",\"evidence_class\":\"deterministic\",\"causal_disposition\":\"introduced\",\"proof_refs\":[\"a.go:1\"]}],\"evidence\":[\"e\"]}\n```\ntrailing"
	r, err := ParseJudgeResult(raw)
	if err != nil {
		t.Fatalf("ParseJudgeResult: %v", err)
	}
	if len(r.Findings) != 1 {
		t.Errorf("fenced: findings = %d; want 1", len(r.Findings))
	}
	if r.Findings[0].Location != "a.go:1" {
		t.Errorf("fenced: location = %q; want a.go:1", r.Findings[0].Location)
	}
}

// TestParseJudgeResultInvalid — JSON malformado es E_RESULTS_INVALID.
func TestParseJudgeResultInvalid(t *testing.T) {
	for _, raw := range []string{
		"",
		"not json at all",
		"{\"summary\": \"forbidden field\"}", // DisallowUnknownFields
	} {
		if _, err := ParseJudgeResult(raw); err == nil {
			t.Errorf("ParseJudgeResult(%q) = nil err; want E_RESULTS_INVALID", raw)
		}
	}
}

// TestMergeConfirmed valida la regla de merge principal: ambos severos y misma
// severidad → confirmed → ESCALATED.
func TestMergeConfirmed(t *testing.T) {
	ra := &JudgeResult{
		Findings: []JudgeFinding{
			{Location: "a.go:10", Severity: "CRITICAL", Claim: "race", EvidenceClass: "deterministic", ProofRefs: []string{"a.go:10"}},
		},
		Evidence: []string{"a"},
	}
	rb := &JudgeResult{
		Findings: []JudgeFinding{
			{Location: "a.go:10", Severity: "CRITICAL", Claim: "race", EvidenceClass: "deterministic", ProofRefs: []string{"a.go:10"}},
		},
		Evidence: []string{"b"},
	}
	rep := MergeResults(issueStub("3"), ModePlan, 1, "deadbeef", ra, rb)
	if rep.Verdict != "ESCALATED" {
		t.Errorf("Verdict = %q; want ESCALATED (confirmed severe)", rep.Verdict)
	}
	if rep.ConfirmedCount != 1 {
		t.Errorf("ConfirmedCount = %d; want 1", rep.ConfirmedCount)
	}
	if len(rep.Findings) != 1 || rep.Findings[0].Category != CategoryConfirmed {
		t.Errorf("Findings category = %+v; want [confirmed]", rep.Findings)
	}
}

// TestMergeCorroboratedDivergent — caso clave del AC7/S13: misma location,
// evidencia determinista, severidad divergente. NUNCA descarte silencioso.
func TestMergeCorroboratedDivergent(t *testing.T) {
	ra := &JudgeResult{
		Findings: []JudgeFinding{{Location: "fsm.go:50", Severity: "WARNING", Claim: "atomicity gap", EvidenceClass: "deterministic", ProofRefs: []string{"fsm.go:50"}}},
		Evidence: []string{"a"},
	}
	rb := &JudgeResult{
		Findings: []JudgeFinding{{Location: "fsm.go:50", Severity: "CRITICAL", Claim: "atomicity gap", EvidenceClass: "deterministic", ProofRefs: []string{"fsm.go:50"}}},
		Evidence: []string{"b"},
	}
	rep := MergeResults(issueStub("3"), ModePlan, 1, "h", ra, rb)
	if rep.Verdict != "ESCALATED" {
		t.Errorf("Verdict = %q; want ESCALATED (divergent → ASK)", rep.Verdict)
	}
	if rep.ASKCount != 1 {
		t.Errorf("ASKCount = %d; want 1 (divergent counts as ASK)", rep.ASKCount)
	}
	if len(rep.Findings) != 1 || rep.Findings[0].Category != CategoryDivergent {
		t.Errorf("category = %v; want corroborated_divergent", rep.Findings[0].Category)
	}
	if !rep.Findings[0].NeedsOperatorAsk {
		t.Error("divergent must request operator ASK (never silent drop)")
	}
}

// TestMergeSuspect — un solo juez reporta → suspect, APPROVED si nada más.
func TestMergeSuspect(t *testing.T) {
	ra := &JudgeResult{
		Findings: []JudgeFinding{{Location: "x.go:1", Severity: "SUGGESTION", Claim: "naming", EvidenceClass: "deterministic", ProofRefs: []string{"x.go:1"}}},
		Evidence: []string{"a"},
	}
	rb := &JudgeResult{
		Findings: []JudgeFinding{},
		Evidence: []string{"b"},
	}
	rep := MergeResults(issueStub("3"), ModePlan, 1, "h", ra, rb)
	if rep.Verdict != "APPROVED" {
		t.Errorf("Verdict = %q; want APPROVED (suspect no bloquea)", rep.Verdict)
	}
	if rep.SuspectCount != 1 {
		t.Errorf("SuspectCount = %d; want 1", rep.SuspectCount)
	}
}

// TestMergeClean — sin findings, APPROVED.
func TestMergeClean(t *testing.T) {
	ra := &JudgeResult{Findings: []JudgeFinding{}, Evidence: []string{"a"}}
	rb := &JudgeResult{Findings: []JudgeFinding{}, Evidence: []string{"b"}}
	rep := MergeResults(issueStub("3"), ModePlan, 1, "h", ra, rb)
	if rep.Verdict != "APPROVED" {
		t.Errorf("Verdict = %q; want APPROVED", rep.Verdict)
	}
	if rep.VerdictContract() == "" {
		t.Error("VerdictContract empty")
	}
}

// TestMergeContradictory — claims materialmente distintos en mismo location.
func TestMergeContradictory(t *testing.T) {
	ra := &JudgeResult{
		Findings: []JudgeFinding{{Location: "a.go:1", Severity: "CRITICAL", Claim: "introduces a memory leak", EvidenceClass: "deterministic", ProofRefs: []string{"a.go:1"}}},
	}
	rb := &JudgeResult{
		Findings: []JudgeFinding{{Location: "a.go:1", Severity: "CRITICAL", Claim: "fixes a memory leak", EvidenceClass: "deterministic", ProofRefs: []string{"a.go:1"}}},
	}
	rep := MergeResults(issueStub("3"), ModePlan, 1, "h", ra, rb)
	if rep.Verdict != "ESCALATED" {
		t.Errorf("Verdict = %q; want ESCALATED (contradictory → ASK)", rep.Verdict)
	}
	if rep.ASKCount == 0 {
		t.Error("ASKCount = 0; contradictory debe ser ASK")
	}
}

// TestVerdictContract — el contrato de salida (S16) tiene la forma exacta.
func TestVerdictContract(t *testing.T) {
	rep := &MergeReport{
		IssueID:    "3",
		Mode:       ModePlan,
		Round:      1,
		TargetHash: "deadbeef12345678",
		Verdict:    "APPROVED",
	}
	got := rep.VerdictContract()
	if !strings.HasPrefix(got, "PHASE GATE: APPROVED ✅") {
		t.Errorf("APPROVED prefix missing: %q", got)
	}
	if !strings.Contains(got, "deadbeef") {
		t.Errorf("hash8 missing: %q", got)
	}
	if !strings.Contains(got, "plan-3") {
		t.Errorf("mode-id missing: %q", got)
	}

	rep.Verdict = "ESCALATED"
	rep.ASKCount = 1
	got = rep.VerdictContract()
	if !strings.HasPrefix(got, "PHASE GATE: ESCALATED") {
		t.Errorf("ESCALATED prefix missing: %q", got)
	}
	if !strings.Contains(got, "ledger-") {
		t.Errorf("ledger path missing: %q", got)
	}
}

// TestWriteLedgerShape — el ledger respeta la forma del engine (yaml + tabla).
func TestWriteLedgerShape(t *testing.T) {
	tmp := t.TempDir()
	rep := &MergeReport{
		IssueID:        "3",
		Mode:           ModePlan,
		Round:          2,
		TargetHash:     "feedface",
		Verdict:        "ESCALATED",
		Reason:         "1 confirmed severe",
		ConfirmedCount: 1,
		SuspectCount:   1,
		InfoCount:      0,
		ASKCount:       0,
		Findings: []MergedFinding{
			{Location: "a.go:1", Category: CategoryConfirmed, SeverityA: "CRITICAL", SeverityB: "CRITICAL", Claim: "race", FromA: true, FromB: true},
			{Location: "b.go:2", Category: CategorySuspect, SeverityA: "SUGGESTION", FromA: true, Claim: "naming"},
		},
	}
	path, err := WriteLedger(tmp, rep)
	if err != nil {
		t.Fatalf("WriteLedger: %v", err)
	}
	raw, _ := os.ReadFile(path)
	body := string(raw)
	if !strings.Contains(body, "target_identity: feedface") {
		t.Error("ledger: falta target_identity")
	}
	if !strings.Contains(body, "terminal_state: escalated") {
		t.Error("ledger: falta terminal_state")
	}
	if !strings.Contains(body, "| 1 | `a.go:1` | confirmed |") {
		t.Error("ledger: tabla sin fila confirmed")
	}
	if !strings.Contains(body, "PHASE GATE: ESCALATED") {
		t.Error("ledger: contrato de salida ausente")
	}
}

// TestLoadResultsPending — fail-closed cuando falta un resultado.
func TestLoadResultsPending(t *testing.T) {
	tmp := t.TempDir()
	if err := os.MkdirAll(filepath.Join(tmp, "judgment"), 0755); err != nil {
		t.Fatal(err)
	}
	_ = os.WriteFile(filepath.Join(tmp, "judgment", "result-A.md"), []byte(`{"findings":[],"evidence":["a"]}`), 0644)
	if err := LoadResultsPending(tmp); err == nil {
		t.Error("LoadResultsPending con solo A: nil err; want E_RESULTS_PENDING")
	}
	_ = os.WriteFile(filepath.Join(tmp, "judgment", "result-B.md"), []byte(`{"findings":[],"evidence":["b"]}`), 0644)
	if err := LoadResultsPending(tmp); err != nil {
		t.Errorf("LoadResultsPending con ambos: err = %v; want nil", err)
	}
}

// TestParseJudgeResultOnlySummary — el engine rechaza campos top-level no
// permitidos; un judge que devuelve summary debe fallar.
func TestParseJudgeResultOnlySummary(t *testing.T) {
	_, err := ParseJudgeResult(`{"summary":"approved","findings":[],"evidence":["a"]}`)
	if err == nil {
		t.Error("summary field deberia ser rechazado por DisallowUnknownFields")
	}
}

// issueStub es un helper de tests: produce un *fsm.IssueFSM mínimo.
func issueStub(id string) *fsm.IssueFSM {
	return &fsm.IssueFSM{ID: id}
}
