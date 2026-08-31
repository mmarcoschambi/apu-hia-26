package judge

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"
	osexec "os/exec"
	"path/filepath"
	"sort"
	"strings"

	"github.com/mmarcoschambi/loom/internal/fsm"
)

// Seams inyectables para tests: congelan el diff/PR sin tocar red ni git real.
var (
	gitRunner = func(dir string, args ...string) (string, error) {
		cmd := osexec.Command("git", args...)
		cmd.Dir = dir
		out, err := cmd.Output()
		return string(out), err
	}
	ghRunner = func(args ...string) (string, error) {
		cmd := osexec.Command("gh", args...)
		out, err := cmd.Output()
		return string(out), err
	}
)

// FreezeResult describe el target congelado de una ronda.
type FreezeResult struct {
	Path    string
	Hash    string
	Round   int
	Sources []string
	Content string
}

// Freeze materializa el target inmutable del modo y escribe frozen-<mode>-r<N>.md
// + sidecar .sha256 ANTES de que nada se lance. Sin artefacto no hay juicio.
func Freeze(mode Mode, iss *fsm.IssueFSM) (*FreezeResult, error) {
	if iss == nil || iss.WorktreePath == "" {
		return nil, fmt.Errorf("%w: issue without worktree", ErrNoFreeze)
	}

	var content string
	var sources []string
	var err error

	switch mode {
	case ModePlan:
		content, sources, err = planTarget(iss)
	case ModeApply:
		content, sources, err = applyTarget(iss)
	case ModePR:
		content, sources, err = prTarget(iss)
	default:
		return nil, fmt.Errorf("%w: unknown mode %q", ErrNoFreeze, mode)
	}
	if err != nil {
		return nil, err
	}

	jdir := judgmentDir(iss.WorktreePath)
	if err := os.MkdirAll(jdir, 0755); err != nil {
		return nil, err
	}

	round := NextRound(jdir, string(mode))
	name := fmt.Sprintf("frozen-%s-r%d.md", mode, round)
	path := filepath.Join(jdir, name)

	full := frozenHeader(mode, iss.ID, round, sources) + content

	if err := os.WriteFile(path, []byte(full), 0644); err != nil {
		return nil, err
	}
	hash := HashString(full)
	if err := os.WriteFile(path+".sha256", []byte(hash+"  "+name+"\n"), 0644); err != nil {
		return nil, err
	}
	return &FreezeResult{Path: path, Hash: hash, Round: round, Sources: sources, Content: full}, nil
}

// planTarget congela issue body + specs/spec.md + tasks.md del change del issue.
func planTarget(iss *fsm.IssueFSM) (string, []string, error) {
	base := filepath.Join(iss.WorktreePath, "openspec", "changes", "issue-"+iss.ID)
	specPath := filepath.Join(base, "specs", "spec.md")
	tasksPath := filepath.Join(base, "tasks.md")

	if _, err := os.Stat(specPath); err != nil {
		return "", nil, fmt.Errorf("%w: missing %s", ErrNoFreeze, specPath)
	}
	if _, err := os.Stat(tasksPath); err != nil {
		return "", nil, fmt.Errorf("%w: missing %s", ErrNoFreeze, tasksPath)
	}

	spec, err := os.ReadFile(specPath)
	if err != nil {
		return "", nil, err
	}
	tasks, err := os.ReadFile(tasksPath)
	if err != nil {
		return "", nil, err
	}

	var b strings.Builder
	fmt.Fprintf(&b, "## SECTION 1 — Issue body (registry)\n\n%s\n\n", iss.Body)
	fmt.Fprintf(&b, "## SECTION 2 — %s (verbatim)\n\n%s\n\n", specPath, string(spec))
	fmt.Fprintf(&b, "## SECTION 3 — %s (verbatim)\n\n%s\n", tasksPath, string(tasks))
	return b.String(), []string{"issue body", specPath, tasksPath}, nil
}

// applyTarget congela el diff contra el branch-base. El base se resuelve por
// merge-base contra candidatos de rama default — inmune a topologías donde no
// existe 'main' local o donde el worktree se bifurcó de un HEAD adelantado.
func applyTarget(iss *fsm.IssueFSM) (string, []string, error) {
	wt := iss.WorktreePath
	candidates := []string{"origin/main", "main", "origin/master", "master", "origin/HEAD"}
	var base string
	var lastErr error
	for _, c := range candidates {
		out, err := gitRunner(wt, "merge-base", "HEAD", c)
		if err == nil {
			base = strings.TrimSpace(out)
			break
		}
		lastErr = err
	}
	if base == "" {
		return "", nil, fmt.Errorf("%w: cannot resolve branch base (last err: %v)", ErrNoFreeze, lastErr)
	}
	diff, err := gitRunner(wt, "diff", base+"..HEAD")
	if err != nil {
		return "", nil, fmt.Errorf("%w: git diff failed: %v", ErrNoFreeze, err)
	}
	return fmt.Sprintf("## SECTION 1 — git diff %s..HEAD (verbatim)\n\n%s\n", base, diff),
		[]string{"git diff " + base + "..HEAD"}, nil
}

// prTarget congela el diff del PR + su metadata vía gh CLI.
func prTarget(iss *fsm.IssueFSM) (string, []string, error) {
	diff, err := ghRunner("pr", "diff", iss.ID)
	if err != nil {
		return "", nil, fmt.Errorf("%w: gh pr diff failed: %v", ErrNoFreeze, err)
	}
	meta, metaErr := ghRunner("pr", "view", iss.ID, "--json", "title,body")
	if metaErr != nil {
		meta = fmt.Sprintf("(metadata unavailable: %v)", metaErr)
	}
	return fmt.Sprintf("## SECTION 1 — PR metadata\n\n%s\n\n## SECTION 2 — gh pr diff (verbatim)\n\n%s\n", meta, diff),
		[]string{"gh pr view " + iss.ID, "gh pr diff " + iss.ID}, nil
}

// frozenHeader es el prólogo determinista del archivo congelado: idéntico en
// Freeze y en VerifyUntouched para que el hash sea reproducible.
func frozenHeader(mode Mode, issueID string, round int, sources []string) string {
	return fmt.Sprintf("# FROZEN TARGET — judge gate — issue #%s — mode %s — round %d\nsources: %s\n\n",
		issueID, mode, round, strings.Join(sources, " | "))
}

// VerifyUntouched re-deriva el target y compara el hash contra el sidecar de la
// ronda congelada. Mismatch ⇒ el artefacto mutó post-freeze: veredicto inválido.
func VerifyUntouched(mode Mode, iss *fsm.IssueFSM, round int) error {
	jdir := judgmentDir(iss.WorktreePath)
	sidecar := filepath.Join(jdir, fmt.Sprintf("frozen-%s-r%d.md.sha256", mode, round))
	stored, err := os.ReadFile(sidecar)
	if err != nil {
		return fmt.Errorf("%w: missing sidecar %s", ErrTargetMutated, sidecar)
	}
	storedHash := strings.Fields(strings.TrimSpace(string(stored)))
	if len(storedHash) == 0 {
		return fmt.Errorf("%w: empty sidecar %s", ErrTargetMutated, sidecar)
	}

	var content, sources = "", []string(nil)
	switch mode {
	case ModePlan:
		content, sources, err = planTarget(iss)
	case ModeApply:
		content, sources, err = applyTarget(iss)
	case ModePR:
		content, sources, err = prTarget(iss)
	default:
		return fmt.Errorf("%w: unknown mode %q", ErrTargetMutated, mode)
	}
	if err != nil {
		return fmt.Errorf("%w: %v", ErrTargetMutated, err)
	}

	full := frozenHeader(mode, iss.ID, round, sources) + content
	if HashString(full) != storedHash[0] {
		return fmt.Errorf("%w: artifact changed after freeze (round %d)", ErrTargetMutated, round)
	}
	return nil
}

// NextRound numera la próxima ronda: jamás sobreescribe una ronda previa.
func NextRound(jdir, mode string) int {
	entries, _ := filepath.Glob(filepath.Join(jdir, fmt.Sprintf("frozen-%s-r*.md", mode)))
	best := 0
	for _, e := range entries {
		var n int
		if _, err := fmt.Sscanf(filepath.Base(e), "frozen-"+mode+"-r%d.md", &n); err == nil && n > best {
			best = n
		}
	}
	return best + 1
}

// LatestRound devuelve la ronda congelada más reciente para el modo.
func LatestRound(jdir, mode string) int {
	return NextRound(jdir, mode) - 1
}

// SortedLedgers lista los ledgers por ronda descendente (más reciente primero).
func SortedLedgers(jdir string) []string {
	entries, _ := filepath.Glob(filepath.Join(jdir, "ledger-*.md"))
	sort.Sort(sort.Reverse(sort.StringSlice(entries)))
	return entries
}

func judgmentDir(worktree string) string {
	return filepath.Join(worktree, "judgment")
}

// HashString calcula el sha256 hex de un string.
func HashString(s string) string {
	sum := sha256.Sum256([]byte(s))
	return hex.EncodeToString(sum[:])
}
