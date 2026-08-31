package poller

import (
	"context"
	"os"
	"path/filepath"
	"testing"
	"time"

	"github.com/mmarcoschambi/loom/internal/fsm"
)

// 3.1 RED TEST for Exponential Backoff
func TestExponentialBackoff(t *testing.T) {
	p := NewGithubPoller(10*time.Millisecond, 100*time.Millisecond, nil, nil)

	// First error -> 20ms (+/- jitter)
	delay1 := p.calculateBackoff(1)
	if delay1 < 16*time.Millisecond || delay1 > 24*time.Millisecond {
		t.Fatalf("Expected ~20ms backoff, got %v", delay1)
	}

	// Fourth error -> 160ms (capped at 100ms +/- jitter)
	delay4 := p.calculateBackoff(4)
	if delay4 < 80*time.Millisecond || delay4 > 120*time.Millisecond {
		t.Fatalf("Expected ~100ms capped backoff, got %v", delay4)
	}
}

// 3.2 RED TEST for Manual Override
func TestManualOverride(t *testing.T) {
	fetchCalled := make(chan struct{})
	fetchFn := func(ctx context.Context) ([]string, error) {
		close(fetchCalled)
		return nil, nil
	}
	reg := fsm.NewFSMRegistry(filepath.Join(os.TempDir(), "test_manual_override"))
	defer os.RemoveAll(reg.StateDir)

	p := NewGithubPoller(1*time.Hour, 1*time.Hour, reg, fetchFn)
	ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
	defer cancel()

	p.Start(ctx)
	p.ForcePoll()

	select {
	case <-fetchCalled:
		// Success
	case <-ctx.Done():
		t.Fatal("Expected manual override to fetch immediately")
	}
}

// 3.3 RED TEST for Upstream Closure
func TestUpstreamClosure(t *testing.T) {
	reg := fsm.NewFSMRegistry(filepath.Join(os.TempDir(), "test_closure"))
	defer os.RemoveAll(reg.StateDir)

	issue := &fsm.IssueFSM{ID: "issue-1", State: fsm.WORKING}
	if err := reg.Save(issue); err != nil {
		t.Fatalf("Failed to save issue: %v", err)
	}

	fetchFn := func(ctx context.Context) ([]string, error) {
		// Omit issue-1
		return []string{"issue-2"}, nil
	}

	p := NewGithubPoller(10*time.Millisecond, 100*time.Millisecond, reg, fetchFn)
	err := p.fetchAndDiff(context.Background())
	if err != nil {
		t.Fatalf("Unexpected error: %v", err)
	}

	select {
	case delta := <-p.Deltas():
		if delta.IssueID != "issue-1" || delta.Type != DeltaRemoved {
			t.Fatalf("Expected Removed delta for issue-1, got %v %v", delta.IssueID, delta.Type)
		}
	default:
		t.Fatal("Expected delta to be emitted")
	}

	states := reg.GetStates()
	if !states["issue-1"].GithubClosed {
		t.Fatal("Expected GithubClosed to be true")
	}
}

// 3.4 RED TEST for PENDING Dropping
func TestPendingDropping(t *testing.T) {
	reg := fsm.NewFSMRegistry(filepath.Join(os.TempDir(), "test_pending"))
	defer os.RemoveAll(reg.StateDir)

	issue := &fsm.IssueFSM{ID: "issue-1", State: fsm.PENDING}
	if err := reg.Save(issue); err != nil {
		t.Fatalf("Failed to save issue: %v", err)
	}

	fetchFn := func(ctx context.Context) ([]string, error) {
		// Empty fetch
		return []string{}, nil
	}

	p := NewGithubPoller(10*time.Millisecond, 100*time.Millisecond, reg, fetchFn)
	if err := p.fetchAndDiff(context.Background()); err != nil {
		t.Fatalf("Unexpected error: %v", err)
	}

	select {
	case delta := <-p.Deltas():
		if delta.Type != DeltaRemoved {
			t.Fatalf("Expected Removed delta, got %v", delta.Type)
		}
	default:
		t.Fatal("Expected delta to be emitted")
	}

	states := reg.GetStates()
	if iss, exists := states["issue-1"]; exists && iss.GithubClosed {
		t.Fatal("PENDING issues should not be flagged as GithubClosed, they should just vanish")
	}
}

func TestMultiRepoPoller_ReconciliationAndIsolation(t *testing.T) {
	stateDir := t.TempDir()
	reg := fsm.NewFSMRegistry(stateDir)

	_, _ = reg.AddTrackedRepo("mmarcoschambi/loom")
	_, _ = reg.AddTrackedRepo("mmarcoschambi/swing-momentum-v1")

	// Pre-seed an issue in swing-momentum-v1
	seedIssue := &fsm.IssueFSM{
		ID:    "68",
		Repo:  "mmarcoschambi/swing-momentum-v1",
		Title: "Existing issue in swing",
		State: fsm.WORKING,
	}
	if err := reg.Save(seedIssue); err != nil {
		t.Fatalf("Failed to save seed issue: %v", err)
	}

	fetchRepoFn := func(ctx context.Context, repo string) ([]IssueInfo, error) {
		if repo == "mmarcoschambi/loom" {
			return []IssueInfo{
				{
					ID:    "14",
					Title: "feat(poller): multi-repo",
					Body:  "Multi-repo poller registry",
					URL:   "https://github.com/mmarcoschambi/loom/issues/14",
				},
			}, nil
		}
		if repo == "mmarcoschambi/swing-momentum-v1" {
			// Issue 68 is no longer returned (upstream closed)
			return []IssueInfo{}, nil
		}
		return nil, nil
	}

	p := NewMultiRepoGithubPoller(10*time.Millisecond, 100*time.Millisecond, reg, fetchRepoFn)
	if err := p.fetchAndDiff(context.Background()); err != nil {
		t.Fatalf("Unexpected error in multi-repo fetchAndDiff: %v", err)
	}

	states := reg.GetStates()

	// Verify loom#14 is created
	loomKey := "mmarcoschambi/loom#14"
	loomIss, exists := states[loomKey]
	if !exists {
		t.Fatalf("Expected %s to exist in states, got: %v", loomKey, states)
	}
	if loomIss.Title != "feat(poller): multi-repo" || loomIss.Repo != "mmarcoschambi/loom" {
		t.Fatalf("Unexpected issue data: %+v", loomIss)
	}

	// Verify swing#68 is flagged GithubClosed because it was in WORKING state
	swingKey := "mmarcoschambi/swing-momentum-v1#68"
	swingIss, exists := states[swingKey]
	if !exists {
		// Fallback check by raw "68"
		swingIss, exists = states["68"]
	}
	if !exists {
		t.Fatalf("Expected swing issue 68 to still exist in states, got: %v", states)
	}
	if !swingIss.GithubClosed {
		t.Fatalf("Expected swing issue 68 to be flagged GithubClosed=true")
	}
}

