package judge

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	loomExec "github.com/mmarcoschambi/loom/internal/exec"
	"github.com/mmarcoschambi/loom/internal/fsm"
)

// Seams inyectables para tests: runners de herdr y stat.
var (
	herdrTabCreateFn = loomExec.RunHerdrTabCreate
	herdrAgentStart  = loomExec.RunHerdrAgentStart
	statFnLaunch     = os.Stat
	mkdirAllFn       = os.MkdirAll
	writeFileFn      = os.WriteFile
)

// LaunchResult es la metadata de los dos tabs creados para una ronda de juicio.
// No muta el FSM ni escribe state.json; se persiste solo en el frozen-<mode>.md.
type LaunchResult struct {
	Mode    Mode
	IssueID string
	TabA    string
	TabB    string
	PaneA   string
	PaneB   string
	PromptA string
	PromptB string
	Hash    string
	Round   int
	Path    string
	EngineA string
	EngineB string
	Warning string
}

// LaunchDualTabs crea los dos tabs ciegos de jueces con su prompt idéntico
// (excepto la marca {A|B}) y los lanza en Herdr con los motores elegidos.
//
// Precondiciones (validadas por el caller vía handleJudge):
//   - issue en WORKING (o SEALING si mode=pr)
//   - skills resueltos (sin esto nunca llegamos acá)
//   - target congelado (sin freeze no hay juicio)
//
// Aditividad: usa RunHerdrTabCreate y RunHerdrAgentStart ya exportados. No
// modifica el FSM.
func LaunchDualTabs(iss *fsm.IssueFSM, mode Mode, fr *FreezeResult, paths *SkillsPaths, engineA, engineB string) (*LaunchResult, error) {
	if iss == nil {
		return nil, fmt.Errorf("launch: nil issue")
	}
	if fr == nil {
		return nil, fmt.Errorf("%w: cannot launch without freeze", ErrNoFreeze)
	}
	if paths == nil {
		return nil, fmt.Errorf("%w: cannot launch without skills", ErrSkillMissing)
	}
	for _, e := range []string{engineA, engineB} {
		if !EngineValid(e) {
			return nil, fmt.Errorf("%w: %q not in %v", ErrInvalidEngine, e, ValidEngines)
		}
	}

	bundle, err := LoadInlinedBundle(paths)
	if err != nil {
		return nil, err
	}

	promptA := BuildJudgePrompt("A", fr, paths, bundle)
	promptB := BuildJudgePrompt("B", fr, paths, bundle)

	// Persistir el prompt idéntico en disco bajo <worktree>/judgment/ para
	// que cualquier sesión/skill pueda reproducir lo que cada juez vio.
	// Esto es trazabilidad, no mutación del FSM.
	jdir := filepath.Join(iss.WorktreePath, "judgment")
	if err := mkdirAllFn(jdir, 0755); err != nil {
		return nil, err
	}
	if err := writeFileFn(filepath.Join(jdir, "prompt-A.md"), []byte(promptA), 0644); err != nil {
		return nil, err
	}
	if err := writeFileFn(filepath.Join(jdir, "prompt-B.md"), []byte(promptB), 0644); err != nil {
		return nil, err
	}

	ctx := loomExec.ExecContext{Cwd: iss.WorktreePath}
	tabIDA, paneIDA, err := herdrTabCreateFn(ctx, "judge-a-"+iss.ID)
	if err != nil {
		return nil, fmt.Errorf("herdr tab create (judge A): %w", err)
	}
	tabIDB, paneIDB, err := herdrTabCreateFn(ctx, "judge-b-"+iss.ID)
	if err != nil {
		return nil, fmt.Errorf("herdr tab create (judge B): %w", err)
	}

	// Los prompts se inyectan en background: un fallo de Herdr no invalida
	// el freeze ni el veredicto futuro. El merge se hace cuando ambos
	// result-A.md y result-B.md están escritos.
	_ = herdrAgentStart(ctx, "judge-a-"+iss.ID, engineA, paneIDA, promptA)
	_ = herdrAgentStart(ctx, "judge-b-"+iss.ID, engineB, paneIDB, promptB)

	warn := SameEngineWarn(engineA, engineB)

	return &LaunchResult{
		Mode:    mode,
		IssueID: iss.ID,
		TabA:    tabIDA,
		TabB:    tabIDB,
		PaneA:   paneIDA,
		PaneB:   paneIDB,
		PromptA: promptA,
		PromptB: promptB,
		Hash:    fr.Hash,
		Round:   fr.Round,
		Path:    fr.Path,
		EngineA: engineA,
		EngineB: engineB,
		Warning: warn,
	}, nil
}

// ResultFilePaths devuelve los paths esperados para los resultados de los
// jueces A y B. La fase de merge los espera; cualquier ausencia es
// ErrResultsPending.
func ResultFilePaths(worktree string) (pathA, pathB string) {
	jdir := filepath.Join(worktree, "judgment")
	return filepath.Join(jdir, "result-A.md"), filepath.Join(jdir, "result-B.md")
}

// ParseJudgeResult extrae un JudgeResult del archivo escrito por un juez.
// El formato canónico es un único JSON object (con o sin markdown fences).
// Cualquier desviación es ErrResultsInvalid.
type JudgeResult struct {
	Findings []JudgeFinding `json:"findings"`
	Evidence []string       `json:"evidence"`
}

type JudgeFinding struct {
	Location          string   `json:"location"`
	Severity          string   `json:"severity"`
	Claim             string   `json:"claim"`
	EvidenceClass     string   `json:"evidence_class"`
	CausalDisposition string   `json:"causal_disposition"`
	ProofRefs         []string `json:"proof_refs"`
}

// ParseJudgeResult acepta el contenido bruto del archivo de resultado de un
// juez y devuelve la estructura tipada. Falla cerrado: cualquier JSON
// malformado, campo faltante o shape incorrecto devuelve ErrResultsInvalid.
func ParseJudgeResult(raw string) (*JudgeResult, error) {
	// Los jueces a veces envuelven el JSON en ```json ... ``` o lo
	// preceden con prosa. Buscar el primer '{' balanceado.
	start := -1
	depth := 0
	for i, r := range raw {
		if r == '{' {
			if start == -1 {
				start = i
			}
			depth++
		} else if r == '}' {
			depth--
			if start != -1 && depth == 0 {
				raw = raw[start : i+1]
				break
			}
		}
	}
	if start == -1 {
		return nil, fmt.Errorf("%w: no JSON object found", ErrResultsInvalid)
	}

	var r JudgeResult
	dec := json.NewDecoder(strings.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&r); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrResultsInvalid, err)
	}
	// Filtra campos top-level prohibidos por el engine.
	if len(r.Findings) == 0 && len(r.Evidence) == 0 {
		// No es estrictamente error: un judge clean devuelve {findings:[]}.
		// Pero evidencia vacía sí es WARNING.
	}
	return &r, nil
}
