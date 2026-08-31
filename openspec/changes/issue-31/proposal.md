# Proposal: feat(tui): persistent validation progress indicator and explicit completion modal on [v]

## Intent

Provide persistent visual feedback during asynchronous validation routines initiated by `[v]`, display an explicit, non-transient confirmation banner when transitioning to `[SEALING]`, and ensure validation failures and review gate rejections remain permanently pinned in the inspector pane until operator intervention.

## What this is

- Persistent progress and busy telemetry (`⏳ VALIDATING & SEALING...`) rendered in the inspector header and telemetry pane while the validation goroutine executes.
- Decoupling of validation progress indication from transient toast notifications (`ToastMsg`), ensuring keyboard navigation during execution does not wipe the active validation state.
- Distinct, non-transient success banner in `[SEALING]` (`✅ SEALED: Ready for [p] PR or [d] Done`) embedded directly in the inspector pane.
- Persistent error/denial diagnostics panel in the inspector pane when validation fails (e.g., pytest errors, review gate denials, blocker severity), preventing diagnostic details from disappearing upon the next keystroke.
- Formal verification via a closed BDD scenario matrix and explicit edge cases.

## What this is not

- Does not alter underlying FSM state machine transitions (`internal/fsm/`).
- Does not modify test execution runners, pytest interpreters, or review gate binaries (`internal/exec/`).
- Does not alter GitHub poller synchronization logic (`internal/poller/`).
- Does not introduce new external UI dependencies beyond Bubble Tea and Lipgloss.

## Context

- Issue: https://github.com/mmarcoschambi/loom/issues/31
- Labels: enhancement, tui
- Affected components: `internal/tui/tui.go`, `internal/tui/validation_modal.go`, `internal/tui/tui_test.go`

### Acceptance Criteria

- [ ] Active validation shows persistent busy state in the inspector pane.
- [ ] Successful validation displays a non-transient success banner in `[SEALING]`.
- [ ] Error toasts and failure diagnostics from rejected reviews or failed test suites remain pinned in the inspector pane until dismissed or re-dispatched.
