// Package judge implementa el gate de juicio de fases (judge-phase/judgment-day)
// como funcionalidad nativa de Loom. Advisory por diseño: ninguna función de este
// paquete muta el FSM ni escribe state.json.
package judge

import "errors"

// Mode es el modo de juicio (fase cuya frontera se juzga).
type Mode string

const (
	ModePlan  Mode = "plan"
	ModeApply Mode = "apply"
	ModePR    Mode = "pr"
)

// Sentinel errors — el CLI los mapea a códigos E_* del contrato OpenSpec.
var (
	ErrNoFreeze       = errors.New("no freezable phase artifact: E_NO_FREEZE")
	ErrSkillMissing   = errors.New("judge skills not found under ~/.agents/skills: E_SKILL_MISSING")
	ErrTargetMutated  = errors.New("frozen target mutated after freeze: E_TARGET_MUTATED")
	ErrResultsPending = errors.New("judge results incomplete (need result-A.md and result-B.md): E_RESULTS_PENDING")
	ErrResultsInvalid = errors.New("judge result JSON invalid: E_RESULTS_INVALID")
	ErrHerdrMissing   = errors.New("herdr is not running: E_HERDR_MISSING")
	ErrInvalidEngine  = errors.New("invalid judge engine: E_USAGE")
)

// ValidEngines es el set cerrado de motores soportados por RunHerdrAgentStart.
var ValidEngines = []string{"opencode", "agy", "zcode", "fx", "code"}

// EngineValid reporta si el motor pertenece al set cerrado.
func EngineValid(e string) bool {
	for _, v := range ValidEngines {
		if v == e {
			return true
		}
	}
	return false
}

// SameEngineWarn devuelve el warning de diversidad cuando ambos jueces usan el
// mismo motor (el juicio procede igual; el operador decide si acepta el sesgo).
func SameEngineWarn(a, b string) string {
	if a == b {
		return "WARNING: sin diversidad de proveedor (agent-a == agent-b)"
	}
	return ""
}

// IsSevere calibra severidad según la política de judge-phase (CRITICAL|WARNING).
func IsSevere(sev string) bool {
	return sev == "CRITICAL" || sev == "WARNING"
}
