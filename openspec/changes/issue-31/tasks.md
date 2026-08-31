# Tasks: feat(tui): persistent validation progress indicator and explicit completion modal on [v]

## Phase 1 — Baseline & Pre-Verification

- [x] 1.1 Record repository baseline status (`git status --short`, `git rev-parse HEAD`).
- [x] 1.2 Inspect `internal/tui/tui.go` key handling and view rendering pipeline.

## Phase 2 — Red Tests (TDD)

- [x] 2.1 Add red unit test in `internal/tui/tui_test.go` verifying `m.IsBusy` and `m.BusyIssueID` are set upon triggering `[v]`.
- [x] 2.2 Add red unit test in `internal/tui/tui_test.go` verifying inspector pane renders persistent validation telemetry when `IsBusy` is active.
- [x] 2.3 Add red unit test in `internal/tui/tui_test.go` verifying sticky `✅ SEALED` banner renders in inspector when issue is in `fsm.SEALING`.
- [x] 2.4 Add red unit test in `internal/tui/tui_test.go` verifying pinned failure alert box renders in inspector upon validation error or gate denial.

## Phase 3 — Implementation

- [x] 3.1 Update `[v]` key handler in `internal/tui/tui.go` to set `m.IsBusy = true` and `m.BusyIssueID = issueID` before launching validation `tea.Cmd`.
- [x] 3.2 Update `LoomModel.View()` in `internal/tui/tui.go` to render persistent validation progress telemetry in header and inspector pane.
- [x] 3.3 Update `LoomModel.View()` in `internal/tui/tui.go` to render sticky `✅ SEALED` banner and clear PR/Done action guidance for `fsm.SEALING`.
- [x] 3.4 Update `LoomModel.View()` in `internal/tui/tui.go` to render pinned error diagnostics box for validation failures and review blockers.
- [x] 3.5 Ensure navigation keys (`j`, `k`, `up`, `down`) reset `ToastMsg` without clearing persistent telemetry or pinned alerts.

## Phase 4 — QA & Verification

- [x] 4.1 Run static analysis: `go vet ./...`.
- [x] 4.2 Run unit test suite: `go test -v ./internal/tui/...`.
- [x] 4.3 Run full test suite: `go test -short ./...`.
- [x] 4.4 Verify all BDD scenarios (S1 - S8) and edge cases (E1 - E5) in `specs/spec.md`.

## Phase 5 — Delivery

- [ ] 5.1 Verify clean git status and scope adherence.
- [ ] 5.2 Conventional commit: `feat(tui): persistent validation progress indicator and explicit completion modal on [v]. Fixes #31`.
