package judge

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// Seams inyectables para tests: home del operador y stat por archivo.
var (
	homeDirFn = os.UserHomeDir
	statFn    = os.Stat
)

// SkillsPaths materializa los paths resueltos a los recursos del motor
// judgment-day y del adapter judge-phase. Devuelve error fail-closed si falta
// cualquier recurso crítico (engine SKILL.md, prompts-and-formats.md, o el
// criteria-<mode>.md del modo pedido).
type SkillsPaths struct {
	Home          string
	JudgmentDay   string
	JudgePhase    string
	Prompts       string
	Criteria      string
	CriteriaMode  string
	AgentsTarget  string // AGENTS.md del repo target (puede no existir)
}

// ResolveSkillsPaths localiza los recursos de las skills user-level y los
// devuelve junto con la metadata del modo.
//
//	~/.agents/skills/judgment-day/SKILL.md              (engine)
//	~/.agents/skills/judgment-day/references/prompts-and-formats.md
//	~/.agents/skills/judge-phase/SKILL.md               (adapter)
//	~/.agents/skills/judge-phase/references/criteria-<mode>.md
//	<worktree>/AGENTS.md                                (target invariants; opcional)
//
// La búsqueda de `mode` es case-insensitive. La falta de cualquier recurso
// crítico devuelve ErrSkillMissing con el path exacto que faltó.
func ResolveSkillsPaths(worktree string, mode Mode) (*SkillsPaths, error) {
	home, err := homeDirFn()
	if err != nil {
		return nil, fmt.Errorf("%w: cannot resolve home: %v", ErrSkillMissing, err)
	}

	jd := filepath.Join(home, ".agents", "skills", "judgment-day")
	jp := filepath.Join(home, ".agents", "skills", "judge-phase")
	prompts := filepath.Join(jd, "references", "prompts-and-formats.md")
	crit := filepath.Join(jp, "references", fmt.Sprintf("criteria-%s.md", strings.ToLower(string(mode))))
	agents := filepath.Join(worktree, "AGENTS.md")

	for _, p := range []string{
		filepath.Join(jd, "SKILL.md"),
		prompts,
		filepath.Join(jp, "SKILL.md"),
		crit,
	} {
		if _, err := statFn(p); err != nil {
			return nil, fmt.Errorf("%w: missing %s", ErrSkillMissing, p)
		}
	}

	// AGENTS.md del target es opcional: lo registramos si existe, vacío si no.
	agentsFound := ""
	if _, err := statFn(agents); err == nil {
		agentsFound = agents
	}

	return &SkillsPaths{
		Home:         home,
		JudgmentDay:  jd,
		JudgePhase:   jp,
		Prompts:      prompts,
		Criteria:     crit,
		CriteriaMode: strings.ToLower(string(mode)),
		AgentsTarget: agentsFound,
	}, nil
}

// Bundle contiene solo las secciones del bundle de prompts que el juez
// necesita verbatim. El resto (judgment-day SKILL.md, judge-phase SKILL.md,
// AGENTS.md del target) se referencia por path en BuildJudgePrompt — los
// jueces tienen acceso al worktree y pueden leer esos archivos ellos
// mismos, sin necesidad de inlinear el contenido.
//
// Diseño (verificado empiricamente durante dogfooding con #68, ago-2026):
// el bundle "completo" inline producía prompts de ~50KB que saturaban el
// pane de Herdr y provocaban errores de parseo en terminales PowerShell.
// Esta version compacta deja la prompt en ~10-15KB sin perder fidelidad
// al engine contract: template + criteria siguen inline porque son lo
// que el juez necesita para formatear su respuesta.
type Bundle struct {
	// Template es el contenido verbatim de `prompts-and-formats.md`. El
	// juez lo necesita para saber que está en Judgment Day mode y qué
	// output shape producir.
	Template string

	// Criteria es el contenido verbatim de `criteria-<mode>.md`. Es la
	// lista de cosas específicas que el juez debe verificar.
	Criteria string
}

// LoadInlinedBundle carga SOLO las secciones que el juez necesita verbatim:
// el template de output (prompts-and-formats.md) y los criterios del modo
// (criteria-<mode>.md). Falla cerrado si falta cualquiera de las dos.
//
// La engine self-doc (judgment-day/SKILL.md), la adapter self-doc
// (judge-phase/SKILL.md) y el AGENTS.md del target NO se cargan aquí:
// se referencian por path en BuildJudgePrompt.
func LoadInlinedBundle(paths *SkillsPaths) (*Bundle, error) {
	if paths == nil {
		return nil, fmt.Errorf("%w: nil paths", ErrSkillMissing)
	}

	templateRaw, err := os.ReadFile(paths.Prompts)
	if err != nil {
		return nil, fmt.Errorf("%w: read template %s: %v", ErrSkillMissing, paths.Prompts, err)
	}
	criteriaRaw, err := os.ReadFile(paths.Criteria)
	if err != nil {
		return nil, fmt.Errorf("%w: read criteria %s: %v", ErrSkillMissing, paths.Criteria, err)
	}

	return &Bundle{
		Template: string(templateRaw),
		Criteria: string(criteriaRaw),
	}, nil
}

// BuildJudgePrompt compone el prompt completo que se inyecta a un juez
// (A o B). Estructura compacta para que entre comodo en el pane de Herdr:
//
//  1. Header + target identity (inmutable: path, sha256, round, sources).
//  2. Output template inline (prompts-and-formats.md) — el juez lo
//     necesita para formatear su respuesta.
//  3. Criteria inline (criteria-<mode>.md) — lista de cosas a verificar.
//  4. Path references para engine self-doc, adapter self-doc y AGENTS.md
//     del target. El juez los lee del worktree; inlinearlos era lo que
//     producia los prompts de ~50KB.
//  5. Output contract (JSON shape, skill_resolution footer).
//
// Reemplaza los placeholders del engine:
//   - {A|B} en el header
//   - {immutable target identity and exact paths} con el frozen path/hash/round
//   - {resolved SKILL.md paths} con paths (no inline)
//   - {Skill Resolution: ...} queda en blanco al inicio (lo emite el juez al final)
func BuildJudgePrompt(judgeLetter string, fr *FreezeResult, paths *SkillsPaths, bundle *Bundle) string {
	var b strings.Builder
	fmt.Fprintf(&b, "You are blind Judge %s in explicit Judgment Day mode.\n\n", judgeLetter)

	// 1. Target identity
	b.WriteString("## Target identity (immutable)\n\n")
	fmt.Fprintf(&b, "- Frozen artifact: %s\n", fr.Path)
	fmt.Fprintf(&b, "- sha256: %s\n", fr.Hash)
	fmt.Fprintf(&b, "- Round: %d\n", fr.Round)
	fmt.Fprintf(&b, "- Sources: %s\n\n", strings.Join(fr.Sources, " | "))

	// 2. Output template (inline)
	if bundle != nil && bundle.Template != "" {
		b.WriteString("## Output template (judgment-day engine, verbatim)\n\n")
		b.WriteString(bundle.Template)
		b.WriteString("\n")
	}

	// 3. Criteria (inline)
	if bundle != nil && bundle.Criteria != "" {
		fmt.Fprintf(&b, "## Criteria (mode=%s, verbatim)\n\n", paths.CriteriaMode)
		b.WriteString(bundle.Criteria)
		b.WriteString("\n")
	}

	// 4. Path references (load as needed; not inlined to keep this prompt manageable)
	b.WriteString("## Other references (load as needed; not inlined to keep this prompt manageable)\n\n")
	if paths != nil {
		fmt.Fprintf(&b, "- Engine self-doc (judgment-day): %s\n", filepath.Join(paths.JudgmentDay, "SKILL.md"))
		fmt.Fprintf(&b, "- Adapter self-doc (judge-phase): %s\n", filepath.Join(paths.JudgePhase, "SKILL.md"))
		if paths.AgentsTarget != "" {
			fmt.Fprintf(&b, "- Target AGENTS.md: %s\n", paths.AgentsTarget)
		} else {
			b.WriteString("- Target AGENTS.md: (none; judge on generic core only)\n")
		}
	}
	b.WriteString("\n")

	// 5. Output contract (already part of the template, but repeated here as
	// a quick reference the judge can't miss)
	b.WriteString("## Output contract reminder\n\n")
	b.WriteString("Return one JSON object and no prose, using exactly this native result shape:\n\n")
	b.WriteString(`{"findings":[{"location":"path:line or path:start-end","severity":"CRITICAL","claim":"observable incorrect behavior","evidence_class":"deterministic","causal_disposition":"introduced","proof_refs":["concrete proof"]}],"evidence":["what was inspected"]}` + "\n\n")
	b.WriteString("This is a judgment-day judge result, not a `gentle-ai review capture-result` lens artifact. The only allowed top-level fields are `findings` and `evidence`, and the only allowed finding fields are `location`, `severity`, `claim`, `evidence_class`, `causal_disposition`, and `proof_refs`. Never emit `summary`, `skill_resolution`, or any other unknown field. Keep orchestration metadata outside the native result JSON; `evidence` contains only genuine inspection evidence. Return `{\"findings\":[],\"evidence\":[\"what was inspected\"]}` when clean, then terminate.\n\n")
	b.WriteString("End with: Skill Resolution: <paths-injected|fallback-registry|fallback-path|none> — <details>\n")
	return b.String()
}
