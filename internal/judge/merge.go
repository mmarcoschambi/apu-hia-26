package judge

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/mmarcoschambi/loom/internal/fsm"
)

// Category clasifica un hallazgo emparejado por location entre A y B.
//
//	confirmed         — ambos jueces severos (CRITICAL|WARNING), misma severidad o no.
//	corroborated_div  — mismo claim, evidencia determinista, pero severidad divergente (p.ej. A=WARNING, B=CRITICAL).
//	contradictory     — los jueces se contradicen factualmente (mismo location, claims incompatibles).
//	suspect           — solo un juez lo reporta; queda como info, jamás auto-fix.
//	info              — SUGGESTION/limpio, no afecta el veredicto.
type Category string

const (
	CategoryConfirmed    Category = "confirmed"
	CategoryDivergent    Category = "corroborated_divergent"
	CategoryContradict   Category = "contradictory"
	CategorySuspect      Category = "suspect"
	CategoryInfo         Category = "info"
)

// SeverityString normaliza la severidad; cualquier valor fuera del set cerrado
// del engine se trata como INFO (no severo).
func SeverityString(s string) string {
	switch s {
	case "CRITICAL", "WARNING", "SUGGESTION":
		return s
	}
	return "INFO"
}

// IsSevereEngine replica el helper interno (exportado para reuso en merge).
func IsSevereEngine(sev string) bool {
	return SeverityString(sev) == "CRITICAL" || SeverityString(sev) == "WARNING"
}

// MergedFinding es un hallazgo emparejado o huérfano, listo para el ledger.
type MergedFinding struct {
	Location          string
	Claim             string
	EvidenceClass     string
	ProofRefs         []string
	SeverityA         string
	SeverityB         string
	FromA             bool
	FromB             bool
	Category          Category
	NeedsOperatorAsk  bool
}

// MergeReport es la salida del merge mecÃ¡nico.
type MergeReport struct {
	IssueID   string
	Mode      Mode
	Round     int
	TargetHash string
	Findings  []MergedFinding
	Verdict   string // "APPROVED" o "ESCALATED"
	Reason    string
	ASKCount  int
	ConfirmedCount int
	SuspectCount   int
	InfoCount      int
}

// VerdictContract es la línea exacta que el contrato de salida exige.
func (m *MergeReport) VerdictContract() string {
	if m.Verdict == "APPROVED" {
		return fmt.Sprintf("PHASE GATE: APPROVED ✅ — verde para presionar [next key] (target %s-%s, sha256:%s, ronda %d)",
			strings.ToLower(string(m.Mode)), m.IssueID, shortHash(m.TargetHash), m.Round)
	}
	return fmt.Sprintf("PHASE GATE: ESCALATED ⚠️  — NO presiones [next key]; leé %s",
		filepath.Join("judgment", fmt.Sprintf("ledger-%s-r%d.md", strings.ToLower(string(m.Mode)), m.Round)))
}

func shortHash(h string) string {
	if len(h) >= 8 {
		return h[:8]
	}
	return h
}

// LoadResultsPending valida que ambos result-A.md y result-B.md existan.
// Devuelve ErrResultsPending con los paths esperados si falta alguno.
func LoadResultsPending(worktree string) error {
	a, b := ResultFilePaths(worktree)
	missing := []string{}
	if _, err := os.Stat(a); err != nil {
		missing = append(missing, a)
	}
	if _, err := os.Stat(b); err != nil {
		missing = append(missing, b)
	}
	if len(missing) > 0 {
		return fmt.Errorf("%w: missing %s", ErrResultsPending, strings.Join(missing, ", "))
	}
	return nil
}

// LoadJudgeResult lee y parsea el archivo de resultado de un juez.
func LoadJudgeResult(path string) (*JudgeResult, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("%w: cannot read %s: %v", ErrResultsInvalid, path, err)
	}
	return ParseJudgeResult(string(raw))
}

// MergeResults combina los dos JudgeResult y devuelve un MergeReport listo
// para escribirse como ledger y emitirse como veredicto. Es mecÃ¡nico: jamÃ¡s
// descarta hallazgos en silencio, jamÃ¡s inventa contenido.
func MergeResults(iss *fsm.IssueFSM, mode Mode, round int, hash string, ra, rb *JudgeResult) *MergeReport {
	idxA := indexByLocation(ra)
	idxB := indexByLocation(rb)

	report := &MergeReport{
		IssueID:    iss.ID,
		Mode:       mode,
		Round:      round,
		TargetHash: hash,
		Findings:   []MergedFinding{},
	}

	visited := map[string]bool{}

	// Walk both indexes deterministically (sorted by location).
	locations := unionLocations(idxA, idxB)
	for _, loc := range locations {
		fA, hasA := idxA[loc]
		fB, hasB := idxB[loc]
		visited[loc] = true

		switch {
		case hasA && hasB:
			mf := mergePair(loc, fA, fB)
			report.Findings = append(report.Findings, mf)
		case hasA:
			report.Findings = append(report.Findings, suspectFromA(loc, fA))
		case hasB:
			report.Findings = append(report.Findings, suspectFromB(loc, fB))
		}
	}

	// Count and decide verdict.
	for _, f := range report.Findings {
		switch f.Category {
		case CategoryConfirmed:
			report.ConfirmedCount++
			if f.NeedsOperatorAsk {
				report.ASKCount++
			}
		case CategoryDivergent:
			report.ASKCount++
		case CategoryContradict:
			report.ASKCount++
		case CategorySuspect:
			report.SuspectCount++
		case CategoryInfo:
			report.InfoCount++
		}
	}

	switch {
	case report.ASKCount > 0:
		report.Verdict = "ESCALATED"
		report.Reason = fmt.Sprintf("%d hallazgo(s) requieren decisión del operador (ASK_PENDING)", report.ASKCount)
	case report.ConfirmedCount > 0:
		report.Verdict = "ESCALATED"
		report.Reason = fmt.Sprintf("%d hallazgo(s) confirmado(s) por ambos jueces (severos)", report.ConfirmedCount)
	default:
		report.Verdict = "APPROVED"
		report.Reason = "sin hallazgos severos; suspect(s) e info no bloquean el gate"
	}
	return report
}

func indexByLocation(r *JudgeResult) map[string]JudgeFinding {
	idx := map[string]JudgeFinding{}
	if r == nil {
		return idx
	}
	for _, f := range r.Findings {
		idx[f.Location] = f
	}
	return idx
}

func unionLocations(a, b map[string]JudgeFinding) []string {
	set := map[string]bool{}
	for k := range a {
		set[k] = true
	}
	for k := range b {
		set[k] = true
	}
	out := make([]string, 0, len(set))
	for k := range set {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func mergePair(loc string, a, b JudgeFinding) MergedFinding {
	sevA := SeverityString(a.Severity)
	sevB := SeverityString(b.Severity)
	severeA := IsSevereEngine(sevA)
	severeB := IsSevereEngine(sevB)

	mf := MergedFinding{
		Location:      loc,
		Claim:         a.Claim, // primary claim from A; los jueces deben coincidir
		EvidenceClass: a.EvidenceClass,
		ProofRefs:     dedupStrings(append(append([]string{}, a.ProofRefs...), b.ProofRefs...)),
		SeverityA:     sevA,
		SeverityB:     sevB,
		FromA:         true,
		FromB:         true,
	}

	// Detect factual contradiction: mismo location, claims incompatibles.
	if !strings.EqualFold(strings.TrimSpace(a.Claim), strings.TrimSpace(b.Claim)) {
		// Si los claims son materialmente distintos, es contradictorio.
		if substantialClaimDiff(a.Claim, b.Claim) {
			mf.Category = CategoryContradict
			mf.NeedsOperatorAsk = true
			return mf
		}
	}

	// Corroborated (ambos severos, misma severidad, mismo claim)
	if severeA && severeB {
		if sevA == sevB {
			mf.Category = CategoryConfirmed
		} else {
			// Severidades divergentes sobre el mismo claim determinista
			// (a.EvidenceClass == deterministic): corroborated_divergent.
			if strings.EqualFold(a.EvidenceClass, "deterministic") {
				mf.Category = CategoryDivergent
				mf.NeedsOperatorAsk = true
			} else {
				mf.Category = CategoryConfirmed
			}
		}
		return mf
	}

	// Mixto: uno severo, otro no — el severo "tira" al otro, pero el delta
	// de severidad sobre el mismo claim es un ASK (corroborated_divergent).
	if severeA != severeB {
		mf.Category = CategoryDivergent
		mf.NeedsOperatorAsk = true
		return mf
	}

	// Ninguno severo: info.
	mf.Category = CategoryInfo
	return mf
}

func suspectFromA(loc string, a JudgeFinding) MergedFinding {
	return MergedFinding{
		Location:      loc,
		Claim:         a.Claim,
		EvidenceClass: a.EvidenceClass,
		ProofRefs:     a.ProofRefs,
		SeverityA:     SeverityString(a.Severity),
		SeverityB:     "",
		FromA:         true,
		Category:      CategorySuspect,
	}
}

func suspectFromB(loc string, b JudgeFinding) MergedFinding {
	return MergedFinding{
		Location:      loc,
		Claim:         b.Claim,
		EvidenceClass: b.EvidenceClass,
		ProofRefs:     b.ProofRefs,
		SeverityA:     "",
		SeverityB:     SeverityString(b.Severity),
		FromB:         true,
		Category:      CategorySuspect,
	}
}

func substantialClaimDiff(a, b string) bool {
	na := normalize(a)
	nb := normalize(b)
	if na == "" || nb == "" {
		return false
	}
	if na == nb {
		return false
	}
	// Si uno contiene al otro, no es contradicción (puede ser refinamiento).
	if strings.Contains(na, nb) || strings.Contains(nb, na) {
		return false
	}
	return true
}

func normalize(s string) string {
	return strings.Join(strings.Fields(strings.ToLower(s)), " ")
}

func dedupStrings(in []string) []string {
	seen := map[string]bool{}
	out := make([]string, 0, len(in))
	for _, s := range in {
		if s == "" {
			continue
		}
		if !seen[s] {
			seen[s] = true
			out = append(out, s)
		}
	}
	return out
}

// WriteLedger persiste el MergeReport en formato compatible con el motor
// (yaml de veredicto + tabla markdown de hallazgos con atribución A/B).
func WriteLedger(worktree string, report *MergeReport) (string, error) {
	jdir := filepath.Join(worktree, "judgment")
	if err := os.MkdirAll(jdir, 0755); err != nil {
		return "", err
	}
	ledgerPath := filepath.Join(jdir, fmt.Sprintf("ledger-%s-r%d.md", strings.ToLower(string(report.Mode)), report.Round))

	var b strings.Builder
	fmt.Fprintf(&b, "# Judgment Day Ledger — issue #%s — mode %s — round %d\n\n", report.IssueID, report.Mode, report.Round)
	fmt.Fprintf(&b, "```yaml\n")
	fmt.Fprintf(&b, "target_identity: %s\n", report.TargetHash)
	fmt.Fprintf(&b, "round: %d\n", report.Round)
	fmt.Fprintf(&b, "confirmed: %d\n", report.ConfirmedCount)
	fmt.Fprintf(&b, "suspect: %d\n", report.SuspectCount)
	fmt.Fprintf(&b, "info: %d\n", report.InfoCount)
	fmt.Fprintf(&b, "ask_pending: %d\n", report.ASKCount)
	fmt.Fprintf(&b, "terminal_state: %s\n", strings.ToLower(report.Verdict))
	fmt.Fprintf(&b, "skill_resolution: paths-injected\n")
	fmt.Fprintf(&b, "```\n\n")

	fmt.Fprintf(&b, "## Findings\n\n")
	if len(report.Findings) == 0 {
		fmt.Fprintf(&b, "_No findings — clean run._\n\n")
	} else {
		fmt.Fprintf(&b, "| # | location | category | sev A | sev B | claim | ask |\n")
		fmt.Fprintf(&b, "|---|----------|----------|-------|-------|-------|-----|\n")
		for i, f := range report.Findings {
			ask := ""
			if f.NeedsOperatorAsk {
				ask = "**ASK_PENDING**"
			}
			claim := f.Claim
			if len(claim) > 80 {
				claim = claim[:77] + "…"
			}
			fmt.Fprintf(&b, "| %d | `%s` | %s | %s | %s | %s | %s |\n",
				i+1, f.Location, f.Category, f.SeverityA, f.SeverityB, claim, ask)
		}
		fmt.Fprintf(&b, "\n")
	}

	fmt.Fprintf(&b, "## Verdict\n\n")
	fmt.Fprintf(&b, "%s — %s\n", report.Verdict, report.Reason)
	fmt.Fprintf(&b, "\n## Operator contract\n\n")
	fmt.Fprintf(&b, "```\n%s\n```\n", report.VerdictContract())

	if err := os.WriteFile(ledgerPath, []byte(b.String()), 0644); err != nil {
		return "", err
	}
	return ledgerPath, nil
}
