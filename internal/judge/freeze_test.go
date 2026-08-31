package judge

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/mmarcoschambi/loom/internal/fsm"
)

// TestFreezePlan_MaterializaSidecarYHeader es la base del AC3/S6: el freeze
// produce un archivo + un sidecar sha256 con el mismo nombre base.
func TestFreezePlan_MaterializaSidecarYHeader(t *testing.T) {
	wt := t.TempDir()
	// scaffold openspec/changes/issue-3/{specs/spec.md, tasks.md}
	base := filepath.Join(wt, "openspec", "changes", "issue-3")
	if err := os.MkdirAll(filepath.Join(base, "specs"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(base, "specs", "spec.md"), []byte("# Spec\nbody\n"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(base, "tasks.md"), []byte("# Tasks\n- one\n"), 0644); err != nil {
		t.Fatal(err)
	}

	iss := &fsm.IssueFSM{ID: "3", WorktreePath: wt, Body: "issue body here"}
	fr, err := Freeze(ModePlan, iss)
	if err != nil {
		t.Fatalf("Freeze: %v", err)
	}
	if fr.Round != 1 {
		t.Errorf("first freeze Round = %d; want 1", fr.Round)
	}
	if !strings.HasSuffix(fr.Path, "frozen-plan-r1.md") {
		t.Errorf("Path = %q; want suffix frozen-plan-r1.md", fr.Path)
	}
	if _, err := os.Stat(fr.Path); err != nil {
		t.Errorf("frozen file missing: %v", err)
	}
	sidecar := fr.Path + ".sha256"
	raw, _ := os.ReadFile(sidecar)
	if !strings.HasPrefix(string(raw), fr.Hash) {
		t.Errorf("sidecar hash mismatch: got %q, want prefix %q", string(raw), fr.Hash)
	}
	if !strings.Contains(fr.Content, "issue body here") {
		t.Error("frozen content missing issue body")
	}
	if !strings.Contains(fr.Content, "# Spec") {
		t.Error("frozen content missing spec.md")
	}
	if !strings.Contains(fr.Content, "# Tasks") {
		t.Error("frozen content missing tasks.md")
	}
}

// TestFreezePlan_NoArtifact es el caso S7: sin spec.md o tasks.md, no hay
// freeze. Devuelve ErrNoFreeze.
func TestFreezePlan_NoArtifact(t *testing.T) {
	wt := t.TempDir()
	// Solo el directorio del change, sin spec ni tasks.
	_ = os.MkdirAll(filepath.Join(wt, "openspec", "changes", "issue-3", "specs"), 0755)
	iss := &fsm.IssueFSM{ID: "3", WorktreePath: wt}
	if _, err := Freeze(ModePlan, iss); err == nil {
		t.Error("Freeze sin artefactos: nil err; want ErrNoFreeze")
	}
}

// TestFreezePlan_NextRoundIncrementa: cada freeze crea una nueva ronda; nunca
// sobreescribe.
func TestFreezePlan_NextRoundIncrementa(t *testing.T) {
	wt := t.TempDir()
	base := filepath.Join(wt, "openspec", "changes", "issue-3")
	_ = os.MkdirAll(filepath.Join(base, "specs"), 0755)
	_ = os.WriteFile(filepath.Join(base, "specs", "spec.md"), []byte("s"), 0644)
	_ = os.WriteFile(filepath.Join(base, "tasks.md"), []byte("t"), 0644)

	iss := &fsm.IssueFSM{ID: "3", WorktreePath: wt, Body: "b"}
	fr1, err := Freeze(ModePlan, iss)
	if err != nil {
		t.Fatal(err)
	}
	fr2, err := Freeze(ModePlan, iss)
	if err != nil {
		t.Fatal(err)
	}
	if fr2.Round != fr1.Round+1 {
		t.Errorf("Round 2 = %d; want %d", fr2.Round, fr1.Round+1)
	}
	if fr2.Path == fr1.Path {
		t.Error("Round 2 reused Round 1 path; should be a new file")
	}
}

// TestVerifyUntouched_DetectaMutacion — el AC6/S15: si el artefacto cambia
// después del freeze, la verificación falla con ErrTargetMutated.
func TestVerifyUntouched_DetectaMutacion(t *testing.T) {
	wt := t.TempDir()
	base := filepath.Join(wt, "openspec", "changes", "issue-3")
	_ = os.MkdirAll(filepath.Join(base, "specs"), 0755)
	_ = os.WriteFile(filepath.Join(base, "specs", "spec.md"), []byte("s"), 0644)
	_ = os.WriteFile(filepath.Join(base, "tasks.md"), []byte("t"), 0644)

	iss := &fsm.IssueFSM{ID: "3", WorktreePath: wt, Body: "b"}
	fr, err := Freeze(ModePlan, iss)
	if err != nil {
		t.Fatal(err)
	}

	// Verificar primero que está intacto.
	if err := VerifyUntouched(ModePlan, iss, fr.Round); err != nil {
		t.Fatalf("VerifyUntouched antes de mutar: %v", err)
	}

	// Mutar el spec.md.
	if err := os.WriteFile(filepath.Join(base, "specs", "spec.md"), []byte("MODIFIED"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := VerifyUntouched(ModePlan, iss, fr.Round); err == nil {
		t.Error("VerifyUntouched post-mutación: nil err; want ErrTargetMutated")
	}
}

// TestNextRound_BasadoEnDirectorio valida el seam de numeración.
func TestNextRound_BasadoEnDirectorio(t *testing.T) {
	wt := t.TempDir()
	jdir := filepath.Join(wt, "judgment")
	_ = os.MkdirAll(jdir, 0755)

	if got := NextRound(jdir, "plan"); got != 1 {
		t.Errorf("empty dir: NextRound = %d; want 1", got)
	}
	_ = os.WriteFile(filepath.Join(jdir, "frozen-plan-r3.md"), []byte("x"), 0644)
	if got := NextRound(jdir, "plan"); got != 4 {
		t.Errorf("con r3: NextRound = %d; want 4", got)
	}
	if got := LatestRound(jdir, "plan"); got != 3 {
		t.Errorf("LatestRound = %d; want 3", got)
	}
}

// TestResolveSkillsPaths_Estructura valida la carga de paths y la falla
// cerrada cuando falta la skill engine.
func TestResolveSkillsPaths_Estructura(t *testing.T) {
	// No podemos tocar ~/.agents/skills real en CI; usamos el seam homeDirFn
	// y statFn para simular.
	fakeHome := t.TempDir()
	mkSkill := func(rel string) {
		full := filepath.Join(fakeHome, rel)
		_ = os.MkdirAll(filepath.Dir(full), 0755)
		_ = os.WriteFile(full, []byte("x"), 0644)
	}
	mkSkill(".agents/skills/judgment-day/SKILL.md")
	mkSkill(".agents/skills/judgment-day/references/prompts-and-formats.md")
	mkSkill(".agents/skills/judge-phase/SKILL.md")
	mkSkill(".agents/skills/judge-phase/references/criteria-plan.md")

	origHome := homeDirFn
	origStat := statFn
	t.Cleanup(func() {
		homeDirFn = origHome
		statFn = origStat
	})
	homeDirFn = func() (string, error) { return fakeHome, nil }
	statFn = os.Stat

	wt := t.TempDir()
	paths, err := ResolveSkillsPaths(wt, ModePlan)
	if err != nil {
		t.Fatalf("ResolveSkillsPaths: %v", err)
	}
	if paths.CriteriaMode != "plan" {
		t.Errorf("CriteriaMode = %q; want plan", paths.CriteriaMode)
	}
	if paths.AgentsTarget != "" {
		t.Errorf("AgentsTarget con worktree sin AGENTS.md = %q; want empty", paths.AgentsTarget)
	}

	// Falla cerrada si falta criteria-apply.md.
	_, err = ResolveSkillsPaths(wt, ModeApply)
	if err == nil {
		t.Error("ResolveSkillsPaths(apply) sin criteria-apply.md: nil err; want ErrSkillMissing")
	}
}

// TestBuildJudgePrompt_ContieneIdentidadInmutable — el prompt lleva la
// identidad del frozen arriba para que el juez opere sobre la misma copia.
func TestBuildJudgePrompt_ContieneIdentidadInmutable(t *testing.T) {
	fr := &FreezeResult{
		Path:    "/tmp/wt/judgment/frozen-plan-r1.md",
		Hash:    "abcdef1234567890",
		Round:   1,
		Sources: []string{"issue body", "/tmp/spec.md", "/tmp/tasks.md"},
	}
	paths := &SkillsPaths{
		JudgmentDay:  "/home/x/.agents/skills/judgment-day",
		JudgePhase:   "/home/x/.agents/skills/judge-phase",
		Prompts:      "/home/x/.agents/skills/judgment-day/references/prompts-and-formats.md",
		Criteria:     "/home/x/.agents/skills/judge-phase/references/criteria-plan.md",
		CriteriaMode: "plan",
	}
	bundle := &Bundle{
		Template: "## engine template here",
		Criteria: "## criteria here",
	}
	p := BuildJudgePrompt("A", fr, paths, bundle)
	for _, must := range []string{
		"blind Judge A",
		fr.Path,
		fr.Hash,
		"Round: 1",
		"## Output template (judgment-day engine, verbatim)",
		"## engine template here",
		"## Criteria (mode=plan, verbatim)",
		"## criteria here",
		"Engine self-doc (judgment-day):",
		"Adapter self-doc (judge-phase):",
		"## Output contract reminder",
		"Skill Resolution",
	} {
		if !strings.Contains(p, must) {
			t.Errorf("prompt falta %q", must)
		}
	}
}

// TestBuildJudgePrompt_Compact_Size verifica que la prompt compacta cabe
// en ~15KB o menos, no en los ~50KB que producia el bundle completo
// inline. Es un guard contra regresiones que vuelvan a inline todo.
func TestBuildJudgePrompt_CompactSize(t *testing.T) {
	fr := &FreezeResult{
		Path:    "/tmp/wt/judgment/frozen-plan-r1.md",
		Hash:    "abcdef1234567890",
		Round:   1,
		Sources: []string{"issue body", "/tmp/spec.md", "/tmp/tasks.md"},
	}
	paths := &SkillsPaths{
		JudgmentDay:  "/home/x/.agents/skills/judgment-day",
		JudgePhase:   "/home/x/.agents/skills/judge-phase",
		Prompts:      "/home/x/.agents/skills/judgment-day/references/prompts-and-formats.md",
		Criteria:     "/home/x/.agents/skills/judge-phase/references/criteria-plan.md",
		CriteriaMode: "plan",
		AgentsTarget: "",
	}
	// Simulamos un template y criteria de tamano real (los archivos reales
	// pesan ~4-5KB cada uno).
	bundle := &Bundle{
		Template: strings.Repeat("template-line\n", 200), // ~3KB
		Criteria: strings.Repeat("criteria-line\n", 200), // ~3KB
	}
	p := BuildJudgePrompt("A", fr, paths, bundle)

	const maxBytes = 15 * 1024 // 15KB cap para el header + template + criteria + paths + output contract
	if len(p) > maxBytes {
		t.Errorf("prompt size = %d bytes; exceeds %d-byte cap (engine self-doc + adapter self-doc + AGENTS.md deben ser por path, no inline)", len(p), maxBytes)
	}
	t.Logf("prompt size: %d bytes (~%d KB)", len(p), len(p)/1024)
}

// TestBuildJudgePrompt_AgentesMdPathNoInline garantiza que cuando el
// target TIENE AGENTS.md, la prompt incluye el path (para que el juez
// lo lea del worktree) en vez de inlinearlo (que era lo que saturaba
// el pane en el dogfooding con #68).
func TestBuildJudgePrompt_AgentesMdPathNoInline(t *testing.T) {
	fr := &FreezeResult{Path: "/x", Hash: "h", Round: 1, Sources: []string{"x"}}
	paths := &SkillsPaths{
		JudgmentDay:  "/jd",
		JudgePhase:   "/jp",
		Prompts:      "/jd/p",
		Criteria:     "/jp/c",
		CriteriaMode: "plan",
		AgentsTarget: "/worktree/AGENTS.md",
	}
	bundle := &Bundle{Template: "t", Criteria: "c"}
	p := BuildJudgePrompt("A", fr, paths, bundle)

	// Debe aparecer el path...
	if !strings.Contains(p, "/worktree/AGENTS.md") {
		t.Errorf("prompt debe referenciar AGENTS.md por path; output:\n%s", p)
	}
	// ...pero NO debe tener el contenido inlined de un AGENTS.md real.
	// (Si el path aparece como path, NO como contenido, eso indica que NO
	// se inlineo. La heuristica: que el path aparezca con el sufijo `.md`
	// tal cual, no precedido por headers markdown o "== AGENTS.md (target) ==".)
	if strings.Contains(p, "== AGENTS.md (target) ==") {
		t.Error("prompt contiene el header viejo '== AGENTS.md (target) =='; deberia ser por path, no por contenido inlined")
	}
}

// TestBuildJudgePrompt_AgentesMdAusenteNotaExplicita cubre el caso
// edge: el target NO tiene AGENTS.md. La prompt debe decir "none; judge
// on generic core only" en vez de fallar o inlinear un placeholder raro.
func TestBuildJudgePrompt_AgentesMdAusenteNotaExplicita(t *testing.T) {
	fr := &FreezeResult{Path: "/x", Hash: "h", Round: 1, Sources: []string{"x"}}
	paths := &SkillsPaths{
		JudgmentDay:  "/jd",
		JudgePhase:   "/jp",
		Prompts:      "/jd/p",
		Criteria:     "/jp/c",
		CriteriaMode: "plan",
		AgentsTarget: "", // no AGENTS.md
	}
	bundle := &Bundle{Template: "t", Criteria: "c"}
	p := BuildJudgePrompt("A", fr, paths, bundle)
	if !strings.Contains(p, "Target AGENTS.md: (none; judge on generic core only)") {
		t.Errorf("prompt sin AGENTS.md debe incluir la nota 'none; judge on generic core only'; output:\n%s", p)
	}
}
