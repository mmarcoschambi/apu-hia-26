package fsm

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// 2.1 RED TEST for Atomic Persistence
func TestAtomicPersistence(t *testing.T) {
	// GIVEN a mock registry
	reg := NewFSMRegistry(filepath.Join(os.TempDir(), "loom_test_state"))
	defer os.RemoveAll(reg.StateDir)

	// WHEN persisting state
	issue := &IssueFSM{
		ID:           "test-1",
		PID:          12345,
		WorktreePath: "/tmp/loom/wt-123",
		State:        WORKING,
	}
	if err := reg.Save(issue); err != nil {
		t.Fatalf("Failed to save state: %v", err)
	}

	// THEN we expect a state.json to exist
	// In a complete test, we would mock the fsync and rename to ensure it happens,
	// or at least verify the file exists and is valid JSON.
	if _, err := os.Stat(filepath.Join(reg.StateDir, "state.json")); os.IsNotExist(err) {
		t.Fatal("Expected state.json to be created atomically")
	}
}

// 2.2 RED TEST for Full Timeout Semantics
func TestTimeoutSemantics(t *testing.T) {
	reg := NewFSMRegistry(filepath.Join(os.TempDir(), "loom_test_state_timeout"))
	defer os.RemoveAll(reg.StateDir)

	issue := &IssueFSM{State: WORKING, PID: 999999, ID: "test-timeout"}
	if err := reg.Save(issue); err != nil {
		t.Fatalf("Failed to save state: %v", err)
	}

	// Triggering timeout transition
	// Should fail because TransitionTo is undefined
	err := reg.TransitionTo(issue, FAILED, "Timeout reached")
	if err != nil {
		t.Fatalf("Expected timeout transition to succeed, got %v", err)
	}
}

// 2.3 RED TEST for Corrupt JSON Recovery
func TestCorruptJSONRecovery(t *testing.T) {
	dir := filepath.Join(os.TempDir(), "loom_test_corrupt")
	if err := os.MkdirAll(dir, 0755); err != nil {
		t.Fatalf("Failed to create test dir: %v", err)
	}
	defer os.RemoveAll(dir)

	stateFile := filepath.Join(dir, "state.json")
	if err := os.WriteFile(stateFile, []byte("{invalid_json: true"), 0644); err != nil {
		t.Fatalf("Failed to write corrupt state file: %v", err)
	}

	// Boot process should recover without panic
	reg := NewFSMRegistry(dir)
	err := reg.LoadState()

	if err != nil {
		t.Fatalf("Expected LoadState to recover gracefully from corrupt JSON, got error: %v", err)
	}
}

// 2.4 RED TEST for FAILED Retry Idempotency
func TestFailedRetryIdempotency(t *testing.T) {
	// GIVEN an FSM in FAILED state with a partial directory
	reg := NewFSMRegistry(filepath.Join(os.TempDir(), "loom_test_retry"))
	defer os.RemoveAll(reg.StateDir)

	wtPath := filepath.Join(reg.StateDir, "wt-mock")
	if err := os.MkdirAll(wtPath, 0755); err != nil {
		t.Fatalf("Failed to create mock worktree: %v", err)
	}

	issue := &IssueFSM{State: FAILED, WorktreePath: wtPath, ID: "test-retry"}
	if err := reg.Save(issue); err != nil {
		t.Fatalf("Failed to save state: %v", err)
	}

	// WHEN retrying (Transition FAILED -> ISOLATING)
	err := reg.TransitionTo(issue, ISOLATING, "Retry")

	// THEN the partial directory must be wiped
	if _, statErr := os.Stat(wtPath); !os.IsNotExist(statErr) {
		t.Fatal("Expected partial worktree to be wiped on FAILED -> ISOLATING retry")
	}

	if err != nil {
		t.Fatalf("Expected transition to succeed, got %v", err)
	}
}

// 2.10 Unit tests verifying invalid state jumps are rejected
func TestInvalidTransitions(t *testing.T) {
	reg := NewFSMRegistry(filepath.Join(os.TempDir(), "loom_test_invalid"))
	defer os.RemoveAll(reg.StateDir)

	issue := &IssueFSM{State: WORKING, ID: "test-1"}
	if err := reg.Save(issue); err != nil {
		t.Fatalf("Failed to save issue: %v", err)
	}

	err := reg.TransitionTo(issue, ISOLATING, "Backward jump not allowed")
	if err == nil {
		t.Fatal("Expected error when jumping backwards from WORKING to ISOLATING")
	}

	err = reg.TransitionTo(issue, DONE, "Skip intermediate states")
	if err == nil {
		t.Fatal("Expected error when skipping states from WORKING to DONE")
	}
}

// 2.11 RED TEST for the non-blocking concurrency semaphore
func TestTryAcquireSemaphoreLimit(t *testing.T) {
	reg := NewFSMRegistry(t.TempDir())

	// GIVEN the first MaxConcurrentAgents issues take all available slots
	for i := 1; i <= MaxConcurrentAgents; i++ {
		id := fmt.Sprintf("issue-%d", i)
		if !reg.TryAcquire(id) {
			t.Fatalf("Expected TryAcquire(%s) to succeed with %d/%d slots used", id, i, MaxConcurrentAgents)
		}
	}

	// THEN the next issue must be rejected without blocking
	if reg.TryAcquire("issue-4") {
		t.Fatal("Expected TryAcquire to reject the 4th concurrent agent")
	}

	// AND releasing an issue that never acquired must not free foreign slots
	reg.Release("ghost-issue")
	if reg.ActiveAgents() != MaxConcurrentAgents {
		t.Fatalf("Expected ActiveAgents()=%d after foreign Release, got %d", MaxConcurrentAgents, reg.ActiveAgents())
	}
	if reg.TryAcquire("issue-4") {
		t.Fatal("Expected foreign Release to not free a slot")
	}

	// AND releasing a holder frees exactly one slot for the next issue
	reg.Release("issue-2")
	if reg.ActiveAgents() != MaxConcurrentAgents-1 {
		t.Fatalf("Expected ActiveAgents()=%d after Release, got %d", MaxConcurrentAgents-1, reg.ActiveAgents())
	}
	if !reg.TryAcquire("issue-4") {
		t.Fatal("Expected TryAcquire to succeed after freeing a slot")
	}

	// AND double release stays idempotent (no slot stealing)
	reg.Release("issue-2")
	if reg.ActiveAgents() != MaxConcurrentAgents {
		t.Fatalf("Expected double Release to be idempotent, got %d", reg.ActiveAgents())
	}
}

// 2.12 Cross-process concurrency limit verification across independent FSM instances
func TestCrossProcessConcurrencyLimit(t *testing.T) {
	stateDir := t.TempDir()

	// Process 1: TUI or background runner starts 3 issues and saves them as WORKING
	reg1 := NewFSMRegistry(stateDir)
	for i := 1; i <= MaxConcurrentAgents; i++ {
		id := fmt.Sprintf("issue-%d", i)
		if !reg1.TryAcquire(id) {
			t.Fatalf("Process 1 expected TryAcquire(%s) to succeed", id)
		}
		_ = reg1.Save(&IssueFSM{
			ID:    id,
			State: WORKING,
		})
	}

	// Process 2: loomctl invocation (separate instance, fresh memory)
	reg2 := NewFSMRegistry(stateDir)
	if reg2.ActiveAgents() != MaxConcurrentAgents {
		t.Fatalf("Process 2 expected ActiveAgents() = %d, got %d", MaxConcurrentAgents, reg2.ActiveAgents())
	}

	// Process 2 tries to acquire a 4th slot
	if reg2.TryAcquire("issue-4") {
		t.Fatal("Process 2 expected TryAcquire(issue-4) to be rejected due to 3 active issues in state.json")
	}

	// Process 1 transitions issue-1 to DONE
	_ = reg1.Save(&IssueFSM{
		ID:    "issue-1",
		State: DONE,
	})

	// Process 3: another loomctl invocation now sees 2 active and can acquire
	reg3 := NewFSMRegistry(stateDir)
	if reg3.ActiveAgents() != MaxConcurrentAgents-1 {
		t.Fatalf("Process 3 expected ActiveAgents() = %d, got %d", MaxConcurrentAgents-1, reg3.ActiveAgents())
	}
	if !reg3.TryAcquire("issue-4") {
		t.Fatal("Process 3 expected TryAcquire(issue-4) to succeed after slot freed on disk")
	}
}

func TestUniversalStaleRecovery(t *testing.T) {
	activeStates := []State{ISOLATING, DELEGATING, WORKING, REVIEWING, SEALING, CLEANING}

	for _, activeState := range activeStates {
		t.Run(string(activeState), func(t *testing.T) {
			tempDir := t.TempDir()

			reg := NewFSMRegistry(tempDir)
			// Mock dead PID (99999999)
			issue := &IssueFSM{
				ID:                  "issue-" + string(activeState),
				State:               activeState,
				PID:                 99999999,
				ProcessCreationTime: 12345678,
			}
			if err := reg.Save(issue); err != nil {
				t.Fatalf("Failed to save state: %v", err)
			}

			// Simulate application restart: instantiate new registry and recover
			newReg := NewFSMRegistry(tempDir)
			if err := newReg.RecoverState(); err != nil {
				t.Fatalf("Recovery failed: %v", err)
			}

			recovered, exists := newReg.states[issue.ID]
			if !exists {
				t.Fatalf("Expected issue %s to exist after recovery", issue.ID)
			}
			if recovered.State != STALE {
				t.Fatalf("Expected state %s to recover as STALE, got %s", activeState, recovered.State)
			}
			if !strings.Contains(recovered.LastReason, "Process") {
				t.Fatalf("Expected LastReason to mention process termination, got %q", recovered.LastReason)
			}
		})
	}
}

func TestCircuitBreaker(t *testing.T) {
	iss := &IssueFSM{
		ID:            "test-cb",
		State:         WORKING,
		ActivePhase:   PhaseApply,
		FixRetryCount: 0,
	}

	if !iss.CanRetryFix() {
		t.Fatal("Expected CanRetryFix() to be true initially")
	}

	iss.IncrementFixRetry()
	if iss.FixRetryCount != 1 || !iss.CanRetryFix() {
		t.Fatalf("Expected FixRetryCount=1 and CanRetryFix=true, got count=%d", iss.FixRetryCount)
	}

	iss.IncrementFixRetry()
	if iss.FixRetryCount != 2 {
		t.Fatalf("Expected FixRetryCount=2, got %d", iss.FixRetryCount)
	}
	if iss.CanRetryFix() {
		t.Fatal("Expected CanRetryFix() to be false at MaxFixRetries=2")
	}
}

func TestResetPhaseState(t *testing.T) {
	tempDir := t.TempDir()
	reg := NewFSMRegistry(tempDir)

	iss := &IssueFSM{
		ID:             "test-reset",
		State:          WORKING,
		ActivePhase:    PhaseFix,
		FixRetryCount:  2,
		ReviewSeverity: "BLOCKER",
		DirectMode:     true,
	}
	iss.RecordGateDenial("candidate-or-paths-mismatch", "scope-changed", "receipt mismatch")
	if err := reg.Save(iss); err != nil {
		t.Fatalf("Failed to save state: %v", err)
	}

	// 1. Transition to REVIEWING -> SEALING resets metadata
	if err := reg.TransitionTo(iss, REVIEWING, "Gate approved"); err != nil {
		t.Fatalf("Transition to REVIEWING failed: %v", err)
	}
	if err := reg.TransitionTo(iss, SEALING, "Audit passed"); err != nil {
		t.Fatalf("Transition to SEALING failed: %v", err)
	}

	if iss.ActivePhase != PhaseNone || iss.FixRetryCount != 0 || iss.ReviewSeverity != "" || iss.DirectMode != false {
		t.Fatalf("Expected ResetPhaseState on SEALING, got phase=%s, count=%d, sev=%s, direct=%v",
			iss.ActivePhase, iss.FixRetryCount, iss.ReviewSeverity, iss.DirectMode)
	}
	if iss.LastGateDenial != nil {
		t.Fatalf("Expected LastGateDenial cleared on SEALING, got %+v", iss.LastGateDenial)
	}

	// 2. ResetIssue resets metadata
	iss.FixRetryCount = 1
	iss.ReviewSeverity = "BLOCKER"
	iss.ActivePhase = PhaseFix
	iss.RecordGateDenial("candidate-or-paths-mismatch", "denied", "receipt mismatch")
	if err := reg.ResetIssue(iss); err != nil {
		t.Fatalf("ResetIssue failed: %v", err)
	}
	if iss.ActivePhase != PhaseNone || iss.FixRetryCount != 0 || iss.ReviewSeverity != "" {
		t.Fatalf("Expected ResetPhaseState on ResetIssue, got phase=%s, count=%d, sev=%s",
			iss.ActivePhase, iss.FixRetryCount, iss.ReviewSeverity)
	}
	if iss.LastGateDenial != nil {
		t.Fatalf("Expected LastGateDenial cleared on ResetIssue, got %+v", iss.LastGateDenial)
	}

	// 3. Relaunch from FAILED / STALE resets metadata
	iss.State = FAILED
	iss.FixRetryCount = 2
	iss.ActivePhase = PhaseFix
	iss.RecordGateDenial("scope-changed", "denied", "reason")
	if err := reg.Save(iss); err != nil {
		t.Fatalf("Failed to save FAILED issue: %v", err)
	}
	if err := reg.TransitionTo(iss, ISOLATING, "Relaunching failed issue"); err != nil {
		t.Fatalf("Transition FAILED->ISOLATING failed: %v", err)
	}
	if iss.ActivePhase != PhaseNone || iss.FixRetryCount != 0 || iss.LastGateDenial != nil {
		t.Fatalf("Expected ResetPhaseState on relaunch from FAILED, got phase=%s, count=%d, denial=%+v",
			iss.ActivePhase, iss.FixRetryCount, iss.LastGateDenial)
	}
}

func TestCrossProcess_SaveHydratesBeforePersist(t *testing.T) {
	stateDir := t.TempDir()
	regA := NewFSMRegistry(stateDir)
	regB := NewFSMRegistry(stateDir)

	iss1 := &IssueFSM{ID: "1", Title: "Issue 1", State: PENDING}
	iss2 := &IssueFSM{ID: "2", Title: "Issue 2", State: PENDING}

	_ = regA.Save(iss1)
	_ = regA.Save(iss2)

	// RegB hydrates
	_ = regB.HydrateState()

	// Process A (loomctl fix) updates Issue 1 on disk: FixRetryCount = 2, ActivePhase = FIX
	iss1.FixRetryCount = 2
	iss1.ActivePhase = PhaseFix
	_ = regA.Save(iss1)

	// Process B (TUI) updates Issue 2 and calls Save(iss2)
	iss2.Title = "Issue 2 updated by TUI"
	if err := regB.Save(iss2); err != nil {
		t.Fatalf("RegB Save failed: %v", err)
	}

	// Read state from a fresh process C
	regC := NewFSMRegistry(stateDir)
	_ = regC.HydrateState()
	states := regC.GetStates()

	// Issue 1's FixRetryCount must STILL be 2 (not overwritten with 0 by RegB's stale snapshot)
	if states["1"].FixRetryCount != 2 {
		t.Fatalf("Cross-process overwrite detected! Expected Issue 1 FixRetryCount=2, got %d", states["1"].FixRetryCount)
	}
	if states["2"].Title != "Issue 2 updated by TUI" {
		t.Fatalf("Expected Issue 2 Title updated, got %s", states["2"].Title)
	}
}

func TestGetStates_DefensiveCopying(t *testing.T) {
	stateDir := t.TempDir()
	reg := NewFSMRegistry(stateDir)

	iss := &IssueFSM{ID: "1", Title: "Original Title", State: WORKING, Labels: []string{"bug"}}
	_ = reg.Save(iss)

	states := reg.GetStates()
	readIss := states["1"]
	readIss.Title = "Mutated Title"
	readIss.Labels[0] = "mutated"

	freshStates := reg.GetStates()
	if freshStates["1"].Title != "Original Title" {
		t.Fatalf("GetStates exposed internal mutable pointer! Expected 'Original Title', got %q", freshStates["1"].Title)
	}
	if freshStates["1"].Labels[0] != "bug" {
		t.Fatalf("GetStates exposed internal slice! Expected 'bug', got %q", freshStates["1"].Labels[0])
	}
}

func TestExtractBlockedBy(t *testing.T) {
	cases := []struct {
		name     string
		body     string
		expected []string
	}{
		{
			name:     "Spanish Markdown Blocked by list",
			body:     "## Dependencias\n- [ ] Bloqueado hasta mergear #67 e #73 (la constante vive hoy en ramas separadas).\n",
			expected: []string{"67", "73"},
		},
		{
			name:     "English Blocked By colon",
			body:     "Blocked by: #10, #11\nSome description",
			expected: []string{"10", "11"},
		},
		{
			name:     "Depends on syntax",
			body:     "Depends on #42 and #43",
			expected: []string{"42", "43"},
		},
		{
			name:     "No dependencies",
			body:     "Simple issue without blocking references",
			expected: nil,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			actual := ExtractBlockedBy(tc.body)
			if len(actual) != len(tc.expected) {
				t.Fatalf("Expected %v, got %v", tc.expected, actual)
			}
			for i := range actual {
				if actual[i] != tc.expected[i] {
					t.Errorf("Index %d: expected %s, got %s", i, tc.expected[i], actual[i])
				}
			}
		})
	}
}

func TestUnresolvedDependencies(t *testing.T) {
	stateDir := t.TempDir()
	reg := NewFSMRegistry(stateDir)

	_ = reg.Save(&IssueFSM{ID: "67", State: DONE})
	_ = reg.Save(&IssueFSM{ID: "73", State: PENDING})
	_ = reg.Save(&IssueFSM{
		ID:    "75",
		Title: "refactor(config): unificar umbral",
		Body:  "## Dependencias\n- [ ] Bloqueado hasta mergear #67 e #73\n",
		State: PENDING,
	})

	states := reg.GetStates()
	iss75 := states["75"]

	unresolved := reg.UnresolvedDependencies(iss75)
	if len(unresolved) != 1 || unresolved[0] != "73" {
		t.Fatalf("Expected only #73 as unresolved dependency, got %v", unresolved)
	}

	// When #73 is marked DONE, unresolved should be empty
	_ = reg.Save(&IssueFSM{ID: "73", State: DONE})
	unresolvedDone := reg.UnresolvedDependencies(iss75)
	if len(unresolvedDone) != 0 {
		t.Fatalf("Expected 0 unresolved dependencies after #73 is DONE, got %v", unresolvedDone)
	}
}

func TestTrackedReposPersistenceAndHydration(t *testing.T) {
	stateDir := t.TempDir()
	reg := NewFSMRegistry(stateDir)

	// Initial default should contain default repo
	repos := reg.GetTrackedRepos()
	if len(repos) == 0 {
		t.Fatal("Expected at least 1 default repository")
	}

	// Add new repo
	added, err := reg.AddTrackedRepo("mmarcoschambi/loom")
	if err != nil {
		t.Fatalf("Failed to add tracked repo: %v", err)
	}
	if !added {
		t.Fatal("Expected repo to be newly added")
	}

	// Idempotent add
	addedAgain, err := reg.AddTrackedRepo("mmarcoschambi/loom")
	if err != nil {
		t.Fatalf("Failed on idempotent add: %v", err)
	}
	if addedAgain {
		t.Fatal("Expected repo to not be added again")
	}

	// Hydrate fresh registry from persisted state
	reg2 := NewFSMRegistry(stateDir)
	if err := reg2.HydrateState(); err != nil {
		t.Fatalf("Failed to hydrate state: %v", err)
	}

	repos2 := reg2.GetTrackedRepos()
	found := false
	for _, r := range repos2 {
		if r == "mmarcoschambi/loom" {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("Expected mmarcoschambi/loom to be found in hydrated repos: %v", repos2)
	}

	// Remove repo
	removed, err := reg.RemoveTrackedRepo("mmarcoschambi/loom")
	if err != nil {
		t.Fatalf("Failed to remove repo: %v", err)
	}
	if !removed {
		t.Fatal("Expected repo to be removed")
	}

	// Verify removal after re-hydration
	reg3 := NewFSMRegistry(stateDir)
	_ = reg3.HydrateState()
	for _, r := range reg3.GetTrackedRepos() {
		if r == "mmarcoschambi/loom" {
			t.Fatal("Expected mmarcoschambi/loom to no longer be present")
		}
	}
}

