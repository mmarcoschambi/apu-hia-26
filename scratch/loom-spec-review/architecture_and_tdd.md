# Architecture and TDD Invariants

When designing systems or implementing code, you must strictly adhere to the following constraints:

1. **Strict TDD Ordering**: Test-Driven Development requires that every RED test MUST precede the implementation it is intended to cover. Never write the implementation first; the failing test must exist in the tasks or codebase before its solution.
2. **Force Kill Completeness**: In state machine design, a "force kill" or similar cancellation transition MUST explicitly define the physical termination mechanism (e.g., OS-level process killing, resource releasing), not merely the memory state transition.
3. **PID Reuse Hazard Mitigation**: A Process ID (PID) persisted to disk MUST NOT be blindly trusted after a system reboot or crash. To prevent killing an unrelated process due to OS PID reuse, additional verification (e.g., checking process identity, command-line arguments, or creation time) is mandatory before executing a kill command.

## Validation and Context Boundaries

4. **Physical File Validation**: Never declare a task complete or affirm closure based solely on a summary of intended changes. You must physically validate that the actual files in the correct target worktree contain the expected modifications.
5. **Contextual Isolation and Artifact Cleanup**: When extracting a component or system into its own dedicated repository or worktree, you must ensure that all outdated "ghost" artifacts are purged from the original repository to prevent conflicting audits and maintaining strict context boundaries.

## Systems Design Constraints

6. **Terminal State Consistency**: If a state in a Finite State Machine (FSM) is defined as "terminal" (e.g., ORPHAN, DONE), all subsequent UI actions and FSM transition rules must mathematically and physically enforce that terminality (no backdoors or uncontrolled bypasses).
7. **Crash-Safe Persistence**: A concurrency lock (like a Mutex) only prevents in-memory race conditions; it does NOT guarantee persistence against power failures or process crashes. True crash-safe persistence demands atomic disk operations (e.g., `write temp file -> fsync -> rename`).
8. **Exhaustive Timeout Definitions**: Whenever a timeout is introduced in a system specification, it must explicitly define five parameters: Duration, Clock Start Event, Cancellation Mechanism (e.g., OS signal), Cleanup Protocol, and the resulting State Transition.
9. **Physical OS Wrapper Verification**: When writing RED tests for OS-level wrappers (e.g., process killing, file removal), test against the actual physical exit code/error of the underlying command (e.g., `taskkill`) rather than bypassing the execution with hardcoded mock identifiers (e.g., `pid == 999999`).

## Executable Planning Requirements

10. **Executable Plans Require Reproducible Bootstraps**: A design or specification is not fully executable unless the infrastructure initialization (e.g., repository creation, environment setup, module initialization) is mathematically reproducible and clearly sequenced before implementation begins.
11. **TDD Order Dictates Feasibility**: You cannot write a RED test for a component that relies on state, persistence, or structures that belong to a future phase. An executable plan must sequence tests so they logically precede and strictly isolate the implementation they cover in the current phase.

## Agent Operational Discipline

11. **Strict Accomplishment Truth**: Never declare a task, rule addition, or file modification as "Accomplished" in a summary unless the system explicitly returned a success status for that specific physical write operation. "Intending" to execute a tool call does not equal accomplishment.
12. **Holistic Document Validation**: When applying a systemic rule (like TDD RED-test-first ordering), you must validate the invariant across the *entire* document or system (e.g., all phases of a task list). Do not stop validating after the first few sections.
13. **Tool Safety and Escaping**: When writing ad-hoc scripts (e.g., Python) to modify files, you MUST use raw strings (`r"..."`) or properly escape sequences to prevent destructive interpolation (e.g., corrupting `\verify` into a vertical tab). Prefer native precise tools (like `multi_replace_file_content`) over quick, unsafe string replacements whenever possible.
14. **Semantic Consistency Audits**: When replacing deprecated concepts (e.g., migrating from Mutex to Atomic Persistence), do a thorough keyword search across all related specs and structs to ensure no orphaned terms, mismatched casing (e.g., `GITHUB_CLOSED` vs `GithubClosed`), or missing fields remain.
15. **Reactive UI Event Modeling**: In Reactive UI frameworks (e.g., Bubbletea, React, Elm), never mock state machine responses with `nil` or empty side-effects when a specific error propagation or physical action is expected. You must return, propagate, and explicitly assert against the actual side-effect structures (e.g., `tea.Cmd`) to ensure the UI handles failed transitions and side-effects correctly.
