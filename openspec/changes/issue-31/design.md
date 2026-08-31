# Design: feat(tui): persistent validation progress indicator and explicit completion modal on [v]

## Architecture & Decisions

### D1 — Explicit Validation Busy State Tracking in `LoomModel`
When the operator presses `[v]` on an issue in `WORKING` or `STALE`:
1. `m.IsBusy` is set to `true` and `m.BusyIssueID` is set to `selectedIssue.ID`.
2. The asynchronous validation tea.Cmd is dispatched with a context timeout.
3. Upon receiving the completion message (`transitionOkMsg`, `hardRemoveMsg`, or `validationResultMsg`), `m.IsBusy` and `m.BusyIssueID` are reset.

```go
case "v":
    if m.IsBusy {
        m.ToastMsg = fmt.Sprintf("⏳ Cannot validate while busy on Issue #%s.", m.BusyIssueID)
        return m, nil
    }
    m.IsBusy = true
    m.BusyIssueID = m.SelectedIssue.ID
    return m, runValidationCmd(m.SelectedIssue)
```

### D2 — Persistent Inspector Header & Progress Telemetry
While `m.IsBusy` is true for the selected issue:
1. **Header Banner**: The main orchestrator header displays `⏳ VALIDATING & SEALING ISSUE #<id>...` in place of the static header title.
2. **Inspector Telemetry Badge**: The right inspector panel renders an active progress box:
   `⏳ VALIDATING & SEALING: Executing test suite & Gentle Review Gate...`
3. **Action Guidance**: The Step-by-Step Action section displays an amber progress warning: `Validation in progress. Please wait for test execution and gate seal.`

### D3 — Decoupling Persistent State from Keystroke-cleared Toasts
- Currently, navigation keys (`j`, `k`, `up`, `down`) reset `m.ToastMsg = ""`.
- By moving validation progress, sealed status, and blocker errors into dedicated sections of the Inspector rendering pipeline (`LoomModel.View()`), visual telemetry remains 100% persistent regardless of operator navigation or cursor movement.

### D4 — Non-Transient SEALED Banner in `[SEALING]` State
When an issue transitions to `fsm.SEALING`:
1. The inspector pane renders a distinct emerald sticky banner:
   `✅ SEALED: Validation Passed & Changes Staged`
2. The Step-by-Step Action block provides explicit options:
   `Press [p] to create PR or [d] to clean worktree & mark [DONE]`
3. This banner remains permanently visible whenever the sealed issue is inspected, eliminating the need to query terminal logs or `loomctl status`.

### D5 — Pinned Validation Failure & Review Blocker Diagnostics
When validation fails (pytest failure, Git stage error, or Gentle Review Gate rejection):
1. The failure reason and severity (`iss.ReviewSeverity`, `iss.LastGateDenial`) are persisted in the issue registry.
2. The inspector pane renders a high-visibility soft-red alert box:
   `⚠️ VALIDATION / GATE FAILURE: <error_message_or_denial_reason>`
3. The pinned error persists across backlog navigation until the operator re-dispatches with `[s]`, resets with `[r]`, or resolves the blocker.

## Failure Modes & Mitigations

| Failure Mode | Impact | Mitigation Strategy |
|---|---|---|
| **Operator navigates backlog while validation is running** | Toast disappears; operator might think validation aborted. | Persistent inspector badge and header reflect `m.IsBusy` and `m.BusyIssueID`. |
| **Validation times out (>3 min) or test fails** | Workflow halted without clear feedback. | Return `hardRemoveMsg`, pin error details in Inspector alert box, and mark `ReviewSeverity: BLOCKER`. |
| **Operator switches focus to another issue during validation** | Active validation might be obscured. | Backlog item for busy issue retains busy indicator; selecting it immediately displays ongoing validation telemetry. |
| **Rapid keypresses / double [v]** | Multiple concurrent validation routines. | Guard check `if m.IsBusy` rejects duplicate triggers with a busy alert. |

## Verification Approach

1. **Unit & TUI Tests (`internal/tui/tui_test.go`)**:
   - Verify `m.IsBusy` is set on `[v]`.
   - Verify Inspector output contains `⏳ VALIDATING & SEALING` during busy validation.
   - Verify Inspector output contains `✅ SEALED` banner when issue is in `fsm.SEALING`.
   - Verify Inspector output retains pinned error box after `hardRemoveMsg`.
2. **BDD Scenario Matrix Verification**: Execute all Given/When/Then scenarios defined in `specs/spec.md`.
3. **Full Suite Regression**: Run `go test -short ./...` and `go vet ./...`.
