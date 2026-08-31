package tui

import (
	"strings"
	"testing"

	"github.com/mmarcoschambi/loom/internal/fsm"
)

// TestPipelineIndex cubre el mapeo estado→posición. Los branched states
// (FAILED, ORPHAN) devuelven -1; STALE ya NO devuelve -1 porque es
// recuperable y se renderiza con renderStaleStepper.
func TestPipelineIndex(t *testing.T) {
	want := map[fsm.State]int{
		fsm.PENDING:    0,
		fsm.ISOLATING:  1,
		fsm.DELEGATING: 2,
		fsm.WORKING:    3,
		fsm.REVIEWING:  4,
		fsm.SEALING:    5,
		fsm.CLEANING:   6,
		fsm.DONE:       7,
	}
	for s, expected := range want {
		if got := pipelineIndex(s); got != expected {
			t.Errorf("pipelineIndex(%q) = %d; want %d", s, got, expected)
		}
	}
	// Solo FAILED y ORPHAN son branched. STALE ahora se considera
	// recuperable y va por renderStaleStepper.
	for _, s := range []fsm.State{fsm.FAILED, fsm.ORPHAN} {
		if got := pipelineIndex(s); got != -1 {
			t.Errorf("pipelineIndex(%q branched) = %d; want -1", s, got)
		}
	}
	// STALE no debe devolverse como branched desde pipelineIndex: se
	// rutea explícitamente por renderStaleStepper.
	if got := pipelineIndex(fsm.STALE); got != -1 {
		t.Errorf("pipelineIndex(STALE) = %d; want -1 (STALE es recuperable, no branched)", got)
	}
}

// TestInferStalePosition mapea ActivePhase → posición del pipeline.
// Vacío → PENDING (nunca llegó a WORKING). PLAN/APPLY/FIX/DIRECT → WORKING.
// REVIEW → REVIEWING.
func TestInferStalePosition(t *testing.T) {
	cases := map[fsm.SubPhase]int{
		"":                  0, // PENDING
		fsm.PhasePlan:       3, // WORKING
		fsm.PhaseApply:      3,
		fsm.PhaseFix:        3,
		fsm.PhaseDirect:     3,
		fsm.PhaseReview:     4, // REVIEWING
	}
	for phase, want := range cases {
		if got := inferStalePosition(phase); got != want {
			t.Errorf("inferStalePosition(%q) = %d; want %d", phase, got, want)
		}
	}
}

// TestShortLabel garantiza que las labels existen y son cortas (<=5 chars) —
// la estética del stepper depende de que ninguna desborde el ancho.
func TestShortLabel(t *testing.T) {
	for _, p := range pipelineStates {
		lbl := shortLabel(p)
		if lbl == "" {
			t.Errorf("shortLabel(%q) vacía", p)
		}
		if len(lbl) > 5 {
			t.Errorf("shortLabel(%q) = %q (%d chars); quiere <=5", p, lbl, len(lbl))
		}
	}
}

// TestRenderPipelineStepper_HappyPath valida que cada estado del track feliz
// produce un stepper con (a) la marca ▶ flanqueando la label actual, (b) el
// caption "Step N/8" correcto, y (c) el nombre del estado en el caption.
func TestRenderPipelineStepper_HappyPath(t *testing.T) {
	for i, p := range pipelineStates {
		out := renderPipelineStepper(p, "", 60)
		// Caption: "Step N/8: STATE"
		wantCaption := "Step " + itoa(i+1) + "/8: " + string(p)
		if !strings.Contains(out, wantCaption) {
			t.Errorf("stepper[%s]: caption falta %q\noutput:\n%s", p, wantCaption, out)
		}
		// El marker ▶ (current) debe aparecer exactamente una vez en línea 1.
		lines := strings.Split(out, "\n")
		if len(lines) < 1 {
			t.Fatalf("stepper[%s]: sin line1", p)
		}
		if c := strings.Count(lines[0], "▶"); c != 1 {
			t.Errorf("stepper[%s]: line1 tiene %d marcadores current; quiere 1", p, c)
		}
		// El shortLabel del estado actual debe estar presente en línea 1.
		if !strings.Contains(lines[0], shortLabel(p)) {
			t.Errorf("stepper[%s]: line1 no contiene label %q\noutput:\n%s", p, shortLabel(p), out)
		}
		// La línea 1 debe contener todos los labels del track.
		for _, q := range pipelineStates {
			if !strings.Contains(lines[0], shortLabel(q)) {
				t.Errorf("stepper[%s]: line1 no contiene %q (todos los labels del track deben estar)\noutput:\n%s", p, shortLabel(q), out)
			}
		}
		// El marker ◀ (cierre del current) debe aparecer una vez.
		if c := strings.Count(lines[0], "◀"); c != 1 {
			t.Errorf("stepper[%s]: line1 tiene %d marcadores ◀; quiere 1", p, c)
		}
	}
}

// TestRenderPipelineStepper_Branched cubre FAILED/ORPHAN: deben preservar el
// track completo de 8 estados con el marker ✕ en el punto de fallo/abandono.
func TestRenderPipelineStepper_Branched(t *testing.T) {
	for _, s := range []fsm.State{fsm.FAILED, fsm.ORPHAN} {
		out := renderPipelineStepper(s, "", 60)
		if !strings.Contains(out, "✕ "+string(s)) {
			t.Errorf("stepper[%s branched]: falta badge ✕ %s\noutput:\n%s", s, s, out)
		}
		// El stepper branched DEBE mantener el track completo (› y todos los labels).
		if !strings.Contains(out, "PEND") || !strings.Contains(out, "DONE") {
			t.Errorf("stepper[%s branched]: debe contener labels del track completo (PEND..DONE)", s)
		}
		if !strings.Contains(out, "✕") {
			t.Errorf("stepper[%s branched]: falta marker ✕", s)
		}
		for _, q := range pipelineStates {
			if !strings.Contains(out, shortLabel(q)) {
				t.Errorf("stepper[%s branched]: falta label %q\noutput:\n%s", s, shortLabel(q), out)
			}
		}
	}
}

// TestRenderPipelineStepper_Stale es el fix del issue del usuario: STALE debe
// mostrar el pipeline con la posición inferida desde ActivePhase y la
// anotación de pausa "⏸ STALE — press [s] to resume". NO debe ser branched.
func TestRenderPipelineStepper_Stale(t *testing.T) {
	cases := []struct {
		phase         fsm.SubPhase
		wantIdx       int    // posición del marker ▶◀ en el breadcrumb
		wantLabel     string // label que debe estar flanqueada
		wantPhaseNote bool   // si debe aparecer "(last phase: ...)"
	}{
		{fsm.PhasePlan, 3, "WORK", true},
		{fsm.PhaseApply, 3, "WORK", true},
		{fsm.PhaseFix, 3, "WORK", true},
		{fsm.PhaseDirect, 3, "WORK", true},
		{fsm.PhaseReview, 4, "REV", true},
		{"", 0, "PEND", false}, // nunca llegó a WORKING
	}
	for _, c := range cases {
		out := renderPipelineStepper(fsm.STALE, c.phase, 60)

		// NO debe ser branched: ni ✕ STALE ni "branched at".
		if strings.Contains(out, "✕ STALE") {
			t.Errorf("STALE[phase=%q] NO debe ser branched; output:\n%s", c.phase, out)
		}
		if strings.Contains(out, "branched at") {
			t.Errorf("STALE[phase=%q] NO debe decir 'branched at'; output:\n%s", c.phase, out)
		}

		// Debe tener el breadcrumb con el marker en la posición correcta.
		lines := strings.Split(out, "\n")
		if len(lines) < 1 {
			t.Fatalf("STALE[phase=%q]: sin line1", c.phase)
		}
		// El marker ▶ debe estar en la posición esperada. Como el line1
		// contiene los 8 labels con › entre ellos, contar tokens hasta
		// encontrar ▶◀<label>.
		if !strings.Contains(lines[0], "▶"+c.wantLabel+"◀") {
			t.Errorf("STALE[phase=%q]: line1 no contiene ▶%s◀\noutput:\n%s",
				c.phase, c.wantLabel, out)
		}
		// Done markers (✓ via color, pero acá el verde es bold): contar
		// cuántos estados previos a idx hay.
		// Como el render usa ANSI, contar por posición de string es
		// complejo; verificamos que los labels previos están.
		for i := 0; i < c.wantIdx; i++ {
			if !strings.Contains(lines[0], shortLabel(pipelineStates[i])) {
				t.Errorf("STALE[phase=%q]: line1 no contiene done %q\noutput:\n%s",
					c.phase, shortLabel(pipelineStates[i]), out)
			}
		}

		// Anotación de pausa.
		if !strings.Contains(out, "⏸ STALE") {
			t.Errorf("STALE[phase=%q]: falta anotación ⏸ STALE\noutput:\n%s", c.phase, out)
		}
		if !strings.Contains(out, "press [s] to resume") {
			t.Errorf("STALE[phase=%q]: falta instrucción de resume\noutput:\n%s", c.phase, out)
		}

		// Caption "Step N/8: STALE" correcto.
		wantCaption := "Step " + itoa(c.wantIdx+1) + "/8: STALE"
		if !strings.Contains(out, wantCaption) {
			t.Errorf("STALE[phase=%q]: caption falta %q\noutput:\n%s",
				c.phase, wantCaption, out)
		}

		// Phase note condicional.
		hasNote := strings.Contains(out, "last phase:")
		if c.wantPhaseNote && !hasNote {
			t.Errorf("STALE[phase=%q]: falta 'last phase:' note\noutput:\n%s", c.phase, out)
		}
		if !c.wantPhaseNote && hasNote {
			t.Errorf("STALE[phase=%q] sin ActivePhase: NO debe tener 'last phase:' note\noutput:\n%s", c.phase, out)
		}
	}
}

// TestRenderPipelineStepper_AnchoAjustaConector garantiza que el stepper
// funciona con cualquier ancho (no debe crashear ni producir un layout
// inválido). El breadcrumb single-line tiene un ancho casi fijo (~52 chars).
func TestRenderPipelineStepper_AnchoAjustaConector(t *testing.T) {
	for _, w := range []int{0, 20, 40, 60, 100, 200} {
		out := renderPipelineStepper(fsm.WORKING, "", w)
		if out == "" {
			t.Errorf("stepper width=%d: output vacío", w)
		}
		if !strings.Contains(out, "▶") {
			t.Errorf("stepper width=%d: falta marcador current", w)
		}
		if !strings.Contains(out, "WORK") {
			t.Errorf("stepper width=%d: falta label WORK", w)
		}
	}
}

// itoa mínimo: evita arrastrar strconv a un test que solo cuenta 1-8.
func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var digits []byte
	for n > 0 {
		digits = append([]byte{byte('0' + n%10)}, digits...)
		n /= 10
	}
	return string(digits)
}
