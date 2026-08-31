# Spec: feat(tui): persistent validation progress indicator and explicit completion modal on [v]

Issue: https://github.com/mmarcoschambi/loom/issues/31  
Change directory: `openspec/changes/issue-31/`

## Purpose

Specify formal telemetry, progress indicator, and persistent status banners in Loom TUI during and after asynchronous validation triggered by `[v]`, preventing visual loss of execution state upon user keystrokes and clearly surfacing completion and blocker diagnostics.

## Scope

- **In**:
  - `LoomModel` state management for active validation (`m.IsBusy`, `m.BusyIssueID`).
  - Rendering persistent validation telemetry in the TUI header and inspector pane.
  - Rendering a non-transient, sticky success banner in `[SEALING]` state.
  - Rendering pinned failure and gate rejection diagnostics in the inspector pane.
  - BDD scenario validation and edge case handling.
- **Out**:
  - Modifications to FSM transition rules or state definitions (`internal/fsm/`).
  - Changes to underlying execution commands or pytest runners (`internal/exec/`).
  - Alterations to poller or CLI subcommands (`cmd/loomctl/`).

## Requirements

### R1 — Validation Busy State Tracking
When the operator triggers `[v]` on an eligible issue (`WORKING` or `STALE`), the model MUST set `m.IsBusy = true` and `m.BusyIssueID = issue.ID` until the asynchronous validation routine completes.

### R2 — Persistent Validation Indicator in Inspector
While an issue is actively validating, the TUI header MUST display `⏳ VALIDATING & SEALING ISSUE #<id>...` and the right inspector pane MUST render an active progress badge indicating ongoing test execution and review gate evaluation.

### R3 — Keystroke Immunity for Telemetry
Keystrokes (such as `[j]`, `[k]`, `[up]`, `[down]`, `[Tab]`) that clear transient `ToastMsg` MUST NOT clear or hide the persistent validation indicator, the sealed banner, or pinned failure diagnostics.

### R4 — Non-Transient SEALED Banner
When an issue is in `[SEALING]` state, the inspector pane MUST display a prominent sticky confirmation banner (`✅ SEALED: Validation Passed & Ready for [p] PR or [d] Done`) and step-by-step guidance for PR creation or worktree cleanup.

### R5 — Pinned Validation Failure & Review Blocker Diagnostics
When validation or review gate evaluation fails:
1. The issue's `ReviewSeverity` and failure reason/denial info MUST be updated in the registry.
2. The inspector pane MUST render a pinned error alert box displaying the failure cause.
3. The alert MUST remain pinned until the operator takes corrective action (e.g. `[s]` to fix or `[r]` to reset).

### R6 — Build & Test Suite Compliance
All code changes MUST compile cleanly (`go vet ./...`) and pass the full unit test suite (`go test -short ./...`).

---

## BDD Scenario Matrix (Closed)

```gherkin
Feature: Persistent Validation Indicator and Explicit Completion Banner

  Background:
    Given a running Loom TUI model with registered issues
    And an issue "#31" in "WORKING" state with an active worktree

  # --- R1 & R2: Active Validation Telemetry ---

  Scenario: S1 - Triggering validation sets busy state and displays persistent progress
    Given the operator selects issue "#31" in "WORKING" state
    When the operator presses "v"
    Then the model sets IsBusy to true and BusyIssueID to "31"
    And the TUI header displays "⏳ AGENT WORKING ON ISSUE #31..." or "⏳ VALIDATING & SEALING ISSUE #31..."
    And the inspector pane renders the active validation progress indicator

  Scenario: S2 - Keystroke navigation does not wipe validation progress indicator
    Given issue "#31" is actively validating with IsBusy set to true
    When the operator presses "j", "k", "up", or "down"
    Then the transient ToastMsg is reset
    And the header and inspector pane continue to display the persistent validation indicator

  # --- R4: Non-Transient SEALED Banner ---

  Scenario: S3 - Successful validation displays sticky SEALED banner
    Given issue "#31" finishes validation successfully
    When the FSM transitions to "SEALING"
    Then the inspector pane displays the persistent "✅ SEALED" banner
    And the Step-by-Step Action section displays options for "[p] PR" and "[d] Done"
    And pressing any navigation key preserves the "✅ SEALED" banner in the inspector

  # --- R5: Pinned Failure & Blocker Diagnostics ---

  Scenario: S4 - Pytest execution failure renders pinned failure alert in inspector
    Given issue "#31" fails during pytest evidence execution
    When the validation command returns an error message
    Then the issue ReviewSeverity is set to "BLOCKER"
    And the issue ActivePhase is set to "FIX"
    And the inspector pane displays a pinned failure alert box containing the error details
    And subsequent navigation keys do not clear the pinned failure alert

  Scenario: S5 - Gentle Review Gate rejection displays pinned gate denial
    Given issue "#31" fails the Gentle Review Gate
    When the gate returns Allowed=false with denial code and reason
    Then the issue records the gate denial info
    And the inspector pane renders a pinned blocker alert showing the denial code and reason

  # --- Multi-Issue & State Transitions ---

  Scenario: S6 - Switching issues during validation reflects accurate busy state
    Given issue "#31" is actively validating
    When the operator navigates to inspect issue "#32"
    Then the header indicates that issue "#31" is busy
    And pressing "v" on issue "#32" is rejected with a busy alert

  Scenario: S7 - Starting fix or resetting issue clears previous failure alert
    Given issue "#31" has a pinned validation failure alert
    When the operator presses "s" to dispatch a fix session or "r" to reset
    Then the previous failure alert is cleared or updated to the new session state

  Scenario: S8 - Layout responsiveness across ViewModes
    Given issue "#31" in "SEALING" or active validation state
    When the operator switches ViewMode using "[Tab]" (Split, BacklogOnly, InspectorOnly)
    Then the inspector content adapts width and height while maintaining persistent status banners
```

---

## Explicit Edge Cases Table

| ID | Edge Case | Expected Behavior | Mitigation / Mechanism |
|---|---|---|---|
| **E1** | Rapid consecutive `[v]` keypresses while validation is already executing. | The duplicate request is rejected immediately; the busy indicator remains uninterrupted. | Checked via `if m.IsBusy` guard at top of `"v"` handler. |
| **E2** | Validation goroutine times out (>3 min) or encounters a runtime error. | Returns `hardRemoveMsg`, resets `m.IsBusy = false`, and pins timeout error in inspector pane. | Context timeout (`context.WithTimeout`) in validation command. |
| **E3** | Operator presses `[q]` or `Ctrl+C` while validation is actively running. | Clean teardown without leaving orphaned hanging goroutines or corrupt FSM locks. | Process trees and context cancellation handled on shutdown. |
| **E4** | Issue has empty or missing test evidence command in environment. | Fails closed with descriptive error pinned in inspector; does not transition to `SEALING`. | Fail-closed validation pipeline in `exec.RunPytestEvidence`. |
| **E5** | Window resized to small dimensions (<60x20) during active validation. | Lipgloss styles truncate or wrap gracefully without crashing or corrupting viewport layout. | Clamped width/height bounds in `LoomModel.View()`. |
