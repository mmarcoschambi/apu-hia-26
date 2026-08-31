package poller

import (
	"context"
	"math/rand"
	"strings"
	"time"

	"github.com/mmarcoschambi/loom/internal/fsm"
)

type DeltaType string

const (
	DeltaAdded   DeltaType = "Added"
	DeltaUpdated DeltaType = "Updated"
	DeltaRemoved DeltaType = "Removed"
)

type Delta struct {
	IssueID string
	Type    DeltaType
	Payload interface{} // e.g., the actual issue payload
}

type IssueInfo struct {
	ID        string
	Repo      string
	Title     string
	Body      string
	Labels    []string
	URL       string
	UpdatedAt string
}

type GithubPoller struct {
	baseInterval       time.Duration
	maxInterval        time.Duration
	deltas             chan Delta
	forcePoll          chan struct{}
	fetchFn            func(ctx context.Context) ([]string, error)
	fetchDetailsFn     func(ctx context.Context) ([]IssueInfo, error)
	fetchRepoDetailsFn func(ctx context.Context, repo string) ([]IssueInfo, error)
	registry           *fsm.FSMRegistry
}

func NewGithubPoller(base, max time.Duration, registry *fsm.FSMRegistry, fetchFn func(ctx context.Context) ([]string, error)) *GithubPoller {
	return &GithubPoller{
		baseInterval: base,
		maxInterval:  max,
		deltas:       make(chan Delta, 100),
		forcePoll:    make(chan struct{}, 1),
		fetchFn:      fetchFn,
		registry:     registry,
	}
}

func NewGithubPollerWithDetails(base, max time.Duration, registry *fsm.FSMRegistry, fetchDetailsFn func(ctx context.Context) ([]IssueInfo, error)) *GithubPoller {
	return &GithubPoller{
		baseInterval:   base,
		maxInterval:    max,
		deltas:         make(chan Delta, 100),
		forcePoll:      make(chan struct{}, 1),
		fetchDetailsFn: fetchDetailsFn,
		registry:       registry,
	}
}

func NewMultiRepoGithubPoller(base, max time.Duration, registry *fsm.FSMRegistry, fetchRepoDetailsFn func(ctx context.Context, repo string) ([]IssueInfo, error)) *GithubPoller {
	return &GithubPoller{
		baseInterval:       base,
		maxInterval:        max,
		deltas:             make(chan Delta, 100),
		forcePoll:          make(chan struct{}, 1),
		fetchRepoDetailsFn: fetchRepoDetailsFn,
		registry:           registry,
	}
}

func (p *GithubPoller) Deltas() <-chan Delta {
	return p.deltas
}

func (p *GithubPoller) ForcePoll() {
	select {
	case p.forcePoll <- struct{}{}:
	default:
	}
}

func (p *GithubPoller) calculateBackoff(attempts int) time.Duration {
	if attempts <= 0 {
		return p.baseInterval
	}

	if attempts > 30 {
		attempts = 30 // Prevent overflow
	}

	// Exponential backoff
	backoff := p.baseInterval * time.Duration(1<<attempts)
	if backoff <= 0 || backoff > p.maxInterval {
		backoff = p.maxInterval
	}

	// Add jitter +/- 20%
	jitter := float64(backoff) * 0.2
	jitterDuration := time.Duration((rand.Float64()*2 - 1) * jitter)
	return backoff + jitterDuration
}

// Start runs the polling loop (mocked for RED tests)
func (p *GithubPoller) Start(ctx context.Context) {
	go func() {
		attempts := 0
		for {
			interval := p.calculateBackoff(attempts)
			timer := time.NewTimer(interval)

			select {
			case <-ctx.Done():
				timer.Stop()
				return
			case <-p.forcePoll:
				timer.Stop()
				attempts = 0
				if err := p.fetchAndDiff(ctx); err != nil {
					attempts++
				}
			case <-timer.C:
				if err := p.fetchAndDiff(ctx); err != nil {
					attempts++
				} else {
					attempts = 0
				}
			}
		}
	}()
}

func (p *GithubPoller) fetchAndDiff(ctx context.Context) error {
	if (p.fetchFn == nil && p.fetchDetailsFn == nil && p.fetchRepoDetailsFn == nil) || p.registry == nil {
		return nil
	}

	if p.fetchRepoDetailsFn != nil {
		trackedRepos := p.registry.GetTrackedRepos()
		var lastErr error
		for _, repo := range trackedRepos {
			if err := p.fetchAndDiffRepo(ctx, repo); err != nil {
				lastErr = err
			}
		}
		return lastErr
	}

	return p.fetchAndDiffSingle(ctx)
}

func (p *GithubPoller) fetchAndDiffRepo(ctx context.Context, repo string) error {
	fetchedList, err := p.fetchRepoDetailsFn(ctx, repo)
	if err != nil {
		return err
	}

	fetchedMap := make(map[string]IssueInfo)
	for _, item := range fetchedList {
		item.Repo = repo
		key := repo + "#" + item.ID
		fetchedMap[key] = item
	}

	localStates := p.registry.GetStates()

	// Check for removed/closed issues belonging to this repo
	for key, issue := range localStates {
		isThisRepo := (issue.Repo == repo) || strings.HasPrefix(key, repo+"#")
		if !isThisRepo {
			continue
		}

		issueKey := key
		if !strings.Contains(issueKey, "#") {
			issueKey = repo + "#" + issue.ID
		}

		if _, exists := fetchedMap[issueKey]; !exists {
			if issue.State == fsm.PENDING || issue.State == fsm.DONE {
				_ = p.registry.Delete(key)
				p.deltas <- Delta{IssueID: issue.ID, Type: DeltaRemoved}
			} else if !issue.GithubClosed {
				issue.GithubClosed = true
				if err := p.registry.Save(issue); err != nil {
					return err
				}
				p.deltas <- Delta{IssueID: issue.ID, Type: DeltaRemoved}
			}
		}
	}

	// Check for added or updated issues
	for key, item := range fetchedMap {
		existing, exists := localStates[key]
		if !exists {
			existing, exists = localStates[item.ID]
		}

		if !exists {
			newIssue := &fsm.IssueFSM{
				ID:        item.ID,
				Repo:      repo,
				Title:     item.Title,
				Body:      item.Body,
				Labels:    item.Labels,
				URL:       item.URL,
				UpdatedAt: item.UpdatedAt,
				State:     fsm.PENDING,
			}
			if err := p.registry.Save(newIssue); err != nil {
				return err
			}
			p.deltas <- Delta{IssueID: item.ID, Type: DeltaAdded, Payload: item}
		} else {
			if item.Title != "" && (existing.Title != item.Title || existing.Body != item.Body || existing.Repo != repo) {
				existing.Repo = repo
				existing.Title = item.Title
				existing.Body = item.Body
				existing.Labels = item.Labels
				existing.URL = item.URL
				existing.UpdatedAt = item.UpdatedAt
				if err := p.registry.Save(existing); err != nil {
					return err
				}
				p.deltas <- Delta{IssueID: item.ID, Type: DeltaUpdated, Payload: item}
			}
		}
	}

	return nil
}

func (p *GithubPoller) fetchAndDiffSingle(ctx context.Context) error {
	var fetchedList []IssueInfo
	if p.fetchDetailsFn != nil {
		var err error
		fetchedList, err = p.fetchDetailsFn(ctx)
		if err != nil {
			return err
		}
	} else if p.fetchFn != nil {
		ids, err := p.fetchFn(ctx)
		if err != nil {
			return err
		}
		for _, id := range ids {
			fetchedList = append(fetchedList, IssueInfo{ID: id})
		}
	}

	fetchedMap := make(map[string]IssueInfo)
	for _, item := range fetchedList {
		fetchedMap[item.ID] = item
	}

	localStates := p.registry.GetStates()

	// Check for removed/closed issues
	for id, issue := range localStates {
		if _, exists := fetchedMap[id]; !exists {
			if issue.State == fsm.PENDING || issue.State == fsm.DONE {
				_ = p.registry.Delete(id)
				p.deltas <- Delta{IssueID: id, Type: DeltaRemoved}
			} else if !issue.GithubClosed {
				issue.GithubClosed = true
				if err := p.registry.Save(issue); err != nil {
					return err
				}
				p.deltas <- Delta{IssueID: id, Type: DeltaRemoved}
			}
		}
	}

	// Check for added or updated issues
	for _, item := range fetchedList {
		if existing, exists := localStates[item.ID]; !exists {
			newIssue := &fsm.IssueFSM{
				ID:        item.ID,
				Title:     item.Title,
				Body:      item.Body,
				Labels:    item.Labels,
				URL:       item.URL,
				UpdatedAt: item.UpdatedAt,
				State:     fsm.PENDING,
			}
			if err := p.registry.Save(newIssue); err != nil {
				return err
			}
			p.deltas <- Delta{IssueID: item.ID, Type: DeltaAdded, Payload: item}
		} else {
			if item.Title != "" && (existing.Title != item.Title || existing.Body != item.Body) {
				existing.Title = item.Title
				existing.Body = item.Body
				existing.Labels = item.Labels
				existing.URL = item.URL
				existing.UpdatedAt = item.UpdatedAt
				if err := p.registry.Save(existing); err != nil {
					return err
				}
				p.deltas <- Delta{IssueID: item.ID, Type: DeltaUpdated, Payload: item}
			}
		}
	}

	return nil
}
