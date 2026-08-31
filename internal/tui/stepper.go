package tui

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/mmarcoschambi/loom/internal/fsm"
)

// pipelineStates enumera el track feliz de la FSM, en orden. Las claves
// viven también en internal/fsm (PENDING..DONE) pero el orden canónico del
// pipeline es decisión de UI: el paquete fsm no debería saber del orden de
// presentación.
var pipelineStates = []fsm.State{
	fsm.PENDING,
	fsm.ISOLATING,
	fsm.DELEGATING,
	fsm.WORKING,
	fsm.REVIEWING,
	fsm.SEALING,
	fsm.CLEANING,
	fsm.DONE,
}

// shortLabel es la versión corta de cada estado del stepper. Cada label se
// diseña para caber en 4-5 caracteres sin sacrificar lectura.
func shortLabel(s fsm.State) string {
	switch s {
	case fsm.PENDING:
		return "PEND"
	case fsm.ISOLATING:
		return "ISOL"
	case fsm.DELEGATING:
		return "DELE"
	case fsm.WORKING:
		return "WORK"
	case fsm.REVIEWING:
		return "REV"
	case fsm.SEALING:
		return "SEAL"
	case fsm.CLEANING:
		return "CLEAN"
	case fsm.DONE:
		return "DONE"
	}
	return string(s)
}

// pipelineIndex devuelve la posición del estado en el track feliz, o -1 si
// el estado es una rama terminal (FAILED / ORPHAN). STALE no devuelve -1
// porque es recuperable y debe mostrar el pipeline (con anotación de pausa).
func pipelineIndex(s fsm.State) int {
	for i, p := range pipelineStates {
		if p == s {
			return i
		}
	}
	return -1
}

// stepperColors mantiene el set de estilos que usa el stepper. Los nombres
// siguen el vocabulario del resto del TUI para que se lea como parte de la
// misma UI.
var (
	stepperDoneStyle     = lipgloss.NewStyle().Foreground(lipgloss.Color("#9ECE6A")).Bold(true) // verde
	stepperCurrentStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("#7AA2F7")).Bold(true) // azul accent
	stepperPendingStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("#565F89"))            // gris muted
	stepperBranchStyle   = lipgloss.NewStyle().Foreground(lipgloss.Color("#F7768E")).Bold(true) // rojo failed
	stepperStaleStyle    = lipgloss.NewStyle().Foreground(lipgloss.Color("#E0AF68")).Bold(true) // amber (Tokyo Night)
	stepperLabelStyle    = lipgloss.NewStyle().Foreground(lipgloss.Color("#A9B1D6"))            // texto base
	stepperCurrentLabel  = lipgloss.NewStyle().Foreground(lipgloss.Color("#FFFFFF")).Bold(true) // highlight del current
	stepperCaptionStyle  = lipgloss.NewStyle().Foreground(lipgloss.Color("#565F89")).Italic(true)
	stepperStaleAnnStyle = lipgloss.NewStyle().Foreground(lipgloss.Color("#E0AF68")).Bold(true) // amber
)

// renderPipelineStepper dibuja el stepper del track feliz de la FSM.
//
//	state          — el estado actual del issue (PENDING..DONE, FAILED, ORPHAN, STALE).
//	activePhase    — la fase activa del issue (PhasePlan/Apply/Review/Fix/Direct/"").
//	                 Se usa SOLO para inferir la posición del marker cuando state=STALE.
//	width          — informativo; el stepper tiene un layout fijo (~52 chars).
//
// Comportamiento por estado:
//   - Happy path (PENDING..DONE): breadcrumb con ▶◀ en el estado actual.
//   - STALE: breadcrumb del track feliz con el marker en la posición inferida
//     desde activePhase (default WORKING si activePhase está vacío) + anotación
//     "⏸ STALE — press [s] to resume" en amber. STALE no es terminal: el
//     operador puede volver a WORKING con [s].
//   - FAILED / ORPHAN: badge "✕ STATE" en rojo, sin track.
func renderPipelineStepper(state fsm.State, activePhase fsm.SubPhase, width int) string {
	return renderPipelineStepperImpl(state, activePhase, width)
}

// RenderPreview es la versión exportada para tooling externo (smoke tests,
// exporters). Para preview simple, asume ActivePhase vacío.
func RenderPreview(state fsm.State, width int) string {
	return renderPipelineStepperImpl(state, "", width)
}

func renderPipelineStepperImpl(state fsm.State, activePhase fsm.SubPhase, width int) string {
	idx := pipelineIndex(state)
	if idx < 0 {
		// Estados no felices: FAILED u ORPHAN son terminales. STALE
		// también pasa por acá como fallback si activePhase es vacío,
		// pero el caller lo trata especialmente abajo.
		if state == fsm.STALE {
			return renderStaleStepper(activePhase, width)
		}
		return renderBranchedStepper(state, width)
	}
	_ = width

	// Construir el breadcrumb (línea 1) y el caption (línea 2).
	arrow := " › "
	currentOpen := stepperCurrentStyle.Render("▶")
	currentClose := stepperCurrentStyle.Render("◀")

	var parts []string
	for i, p := range pipelineStates {
		lbl := shortLabel(p)
		switch {
		case i < idx:
			parts = append(parts, stepperDoneStyle.Render(lbl))
		case i == idx:
			parts = append(parts, currentOpen+stepperCurrentLabel.Render(lbl)+currentClose)
		default:
			parts = append(parts, stepperPendingStyle.Render(lbl))
		}
	}
	line := strings.Join(parts, arrow)

	caption := stepperCaptionStyle.Render(
		fmt.Sprintf("  Step %d/8: %s", idx+1, string(state)))

	// Si el state es STALE, enriquecemos con la anotación amber de pausa.
	// (STALE pasa por acá si su inferencia de idx ya dio 3 vía activePhase,
	// o si state==STALE fue tratado como idx=0 por error: el caller ya
	// filtra, pero igual defendemos acá.)
	if state == fsm.STALE {
		// No deberíamos llegar acá normalmente porque pipelineIndex(STALE) = -1,
		// pero por seguridad renderizamos con la anotación stale.
		return line + "\n" + renderStaleCaption(activePhase)
	}

	return line + "\n" + caption
}

// renderStaleStepper produce el breadcrumb del track feliz con el marker
// posicionado según la fase activa del issue, más la anotación amber de
// pausa. La inferencia de posición es:
//
//	activePhase vacío      → PENDING (idx 0) — nunca se llegó a WORKING
//	PhasePlan/Apply/Fix/Direct → WORKING (idx 3)
//	PhaseReview            → REVIEWING (idx 4)
func renderStaleStepper(activePhase fsm.SubPhase, width int) string {
	idx := inferStalePosition(activePhase)
	_ = width

	arrow := " › "
	currentOpen := stepperStaleStyle.Render("▶")
	currentClose := stepperStaleStyle.Render("◀")

	var parts []string
	for i, p := range pipelineStates {
		lbl := shortLabel(p)
		switch {
		case i < idx:
			parts = append(parts, stepperDoneStyle.Render(lbl))
		case i == idx:
			parts = append(parts, currentOpen+stepperCurrentLabel.Render(lbl)+currentClose)
		default:
			parts = append(parts, stepperPendingStyle.Render(lbl))
		}
	}
	line := strings.Join(parts, arrow)

	caption := renderStaleCaption(activePhase)
	return line + "\n" + caption
}

// renderStaleCaption construye la línea de caption específica para STALE.
// Incluye el "Step N/8" con la posición inferida, una etiqueta "⏸ STALE"
// en amber, y la instrucción de recuperación "press [s] to resume".
func renderStaleCaption(activePhase fsm.SubPhase) string {
	idx := inferStalePosition(activePhase)
	staleTag := stepperStaleAnnStyle.Render("⏸ STALE")
	resume := stepperCaptionStyle.Render("— press [s] to resume")
	phaseNote := ""
	if activePhase != "" {
		phaseNote = stepperCaptionStyle.Render(
			fmt.Sprintf(" (last phase: %s)", string(activePhase)))
	}
	return stepperCaptionStyle.Render(
			fmt.Sprintf("  Step %d/8: STALE ", idx+1)) +
		staleTag + " " + resume + phaseNote
}

// inferStalePosition mapea la fase activa del issue a la posición del
// pipeline donde se presume que quedó al momento de quedar STALE.
func inferStalePosition(activePhase fsm.SubPhase) int {
	switch activePhase {
	case fsm.PhasePlan, fsm.PhaseApply, fsm.PhaseFix, fsm.PhaseDirect:
		return 3 // WORKING
	case fsm.PhaseReview:
		return 4 // REVIEWING
	}
	return 0 // PENDING (nunca llegó a WORKING)
}

// renderBranchedStepper produce la versión persistente del stepper para
// estados terminales o no felices (FAILED, ORPHAN). Mantiene el track completo
// de 8 estados con el marker ✕ en el punto de interrupción.
func renderBranchedStepper(state fsm.State, width int) string {
	idx := 3 // fsm.WORKING (branch point canónico)
	_ = width

	arrow := " › "
	crossOpen := stepperBranchStyle.Render("✕")
	crossClose := stepperBranchStyle.Render("✕")

	var parts []string
	for i, p := range pipelineStates {
		lbl := shortLabel(p)
		switch {
		case i < idx:
			parts = append(parts, stepperDoneStyle.Render(lbl))
		case i == idx:
			parts = append(parts, crossOpen+stepperCurrentLabel.Render(lbl)+crossClose)
		default:
			parts = append(parts, stepperPendingStyle.Render(lbl))
		}
	}
	line := strings.Join(parts, arrow)

	badge := stepperBranchStyle.Render(fmt.Sprintf("✕ %s", string(state)))
	var caption string
	if state == fsm.ORPHAN {
		caption = stepperCaptionStyle.Render(
			fmt.Sprintf("  Step %d/8: %s %s — worktree abandoned (press [x] to purge)", idx+1, string(state), badge))
	} else {
		caption = stepperCaptionStyle.Render(
			fmt.Sprintf("  Step %d/8: %s %s — branched at %s (operator action required)", idx+1, string(state), badge, shortLabel(pipelineStates[idx])))
	}

	return line + "\n" + caption
}

// RenderHTML produce el stepper como HTML standalone con estilos inline
// (sin pasar por ANSI). Útil para previsualizar el stepper en un browser
// sin necesidad de TTY. Los colores se aplican directamente con los mismos
// hex codes que usan los estilos de lipgloss.
func RenderHTML(state fsm.State, width int) string {
	return renderHTMLImpl(state, "", width)
}

// RenderHTMLWithPhase es la versión HTML que acepta ActivePhase para
// posicionar correctamente el marker cuando el estado es STALE.
func RenderHTMLWithPhase(state fsm.State, activePhase fsm.SubPhase, width int) string {
	return renderHTMLImpl(state, activePhase, width)
}

func renderHTMLImpl(state fsm.State, activePhase fsm.SubPhase, width int) string {
	const (
		cDone    = "#9ece6a" // verde
		cCurrent = "#7aa2f7" // azul accent
		cStale   = "#e0af68" // amber
		cPending = "#565f89" // gris muted
		cLabel   = "#a9b1d6" // texto base
		cHi      = "#ffffff" // current label
		cBranch  = "#f7768e" // rojo failed
		cCap     = "#565f89" // caption
	)
	_ = cLabel

	idx := pipelineIndex(state)
	if idx < 0 {
		if state == fsm.STALE {
			return renderStaleHTML(activePhase, cDone, cStale, cPending, cHi, cCap)
		}
		// FAILED / ORPHAN
		branchIdx := 3
		arrow := ` <span style="color:#565f89">›</span> `
		var parts []string
		for i, p := range pipelineStates {
			lbl := shortLabel(p)
			switch {
			case i < branchIdx:
				parts = append(parts, fmt.Sprintf(`<span style="color:%s;font-weight:bold">%s</span>`, cDone, lbl))
			case i == branchIdx:
				parts = append(parts, fmt.Sprintf(
					`<span style="color:%s;font-weight:bold">✕</span>`+
						`<span style="color:%s;font-weight:bold">%s</span>`+
						`<span style="color:%s;font-weight:bold">✕</span>`,
					cBranch, cHi, lbl, cBranch))
			default:
				parts = append(parts, fmt.Sprintf(`<span style="color:%s">%s</span>`, cPending, lbl))
			}
		}
		line := strings.Join(parts, arrow)
		badge := fmt.Sprintf(`<span style="color:%s;font-weight:bold">✕ %s</span>`, cBranch, string(state))
		caption := fmt.Sprintf(`  <span style="color:%s;font-style:italic">Step %d/8: %s %s — operator action required</span>`,
			cCap, branchIdx+1, string(state), badge)
		_ = width
		return line + "<br>" + caption
	}

	arrow := ` <span style="color:#565f89">›</span> `
	var parts []string
	for i, p := range pipelineStates {
		lbl := shortLabel(p)
		switch {
		case i < idx:
			parts = append(parts, fmt.Sprintf(`<span style="color:%s;font-weight:bold">%s</span>`, cDone, lbl))
		case i == idx:
			parts = append(parts, fmt.Sprintf(
				`<span style="color:%s;font-weight:bold">▶</span>`+
					`<span style="color:%s;font-weight:bold">%s</span>`+
					`<span style="color:%s;font-weight:bold">◀</span>`,
				cCurrent, cHi, lbl, cCurrent))
		default:
			parts = append(parts, fmt.Sprintf(`<span style="color:%s">%s</span>`, cPending, lbl))
		}
	}
	line := strings.Join(parts, arrow)
	caption := fmt.Sprintf(`  <span style="color:%s;font-style:italic">Step %d/8: %s</span>`,
		cCap, idx+1, string(state))
	_ = width
	return line + "<br>" + caption
}

func renderStaleHTML(activePhase fsm.SubPhase, cDone, cStale, cPending, cHi, cCap string) string {
	idx := inferStalePosition(activePhase)
	arrow := ` <span style="color:#565f89">›</span> `
	var parts []string
	for i, p := range pipelineStates {
		lbl := shortLabel(p)
		switch {
		case i < idx:
			parts = append(parts, fmt.Sprintf(`<span style="color:%s;font-weight:bold">%s</span>`, cDone, lbl))
		case i == idx:
			parts = append(parts, fmt.Sprintf(
				`<span style="color:%s;font-weight:bold">▶</span>`+
					`<span style="color:%s;font-weight:bold">%s</span>`+
					`<span style="color:%s;font-weight:bold">◀</span>`,
				cStale, cHi, lbl, cStale))
		default:
			parts = append(parts, fmt.Sprintf(`<span style="color:%s">%s</span>`, cPending, lbl))
		}
	}
	line := strings.Join(parts, arrow)
	phaseNote := ""
	if activePhase != "" {
		phaseNote = fmt.Sprintf(` (last phase: %s)`, string(activePhase))
	}
	caption := fmt.Sprintf(
		`  <span style="color:%s;font-style:italic">Step %d/8: STALE</span> `+
			`<span style="color:%s;font-weight:bold">⏸ STALE</span> `+
			`<span style="color:%s;font-style:italic">— press [s] to resume%s</span>`,
		cCap, idx+1, cStale, cCap, phaseNote)
	return line + "<br>" + caption
}
