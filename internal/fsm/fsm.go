package fsm

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"
)

type State string

const (
	PENDING    State = "PENDING"
	ISOLATING  State = "ISOLATING"
	DELEGATING State = "DELEGATING"
	WORKING    State = "WORKING"
	REVIEWING  State = "REVIEWING"
	SEALING    State = "SEALING"
	CLEANING   State = "CLEANING"
	DONE       State = "DONE"
	FAILED     State = "FAILED"
	ORPHAN     State = "ORPHAN"
	STALE      State = "STALE"
)

// MaxConcurrentAgents caps how many issues can be in flight (from [s] until
// their teardown via [d]/[r]) to bound concurrent agent token spend.
const (
	MaxConcurrentAgents = 3
	MaxFixRetries       = 2
)

type SubPhase string

const (
	PhasePlan   SubPhase = "PLAN"
	PhaseApply  SubPhase = "APPLY"
	PhaseReview SubPhase = "REVIEW"
	PhaseFix    SubPhase = "FIX"
	PhaseDirect SubPhase = "DIRECT"
	PhaseNone   SubPhase = ""
)

// GateDenial persiste el último rechazo del gate para inyectarlo
// quirúrgicamente (denial.code exacto) en el prompt de la fase FIX.
type GateDenial struct {
	Code   string `json:"code,omitempty"`
	Result string `json:"result,omitempty"`
	Reason string `json:"reason,omitempty"`
}

type IssueFSM struct {
	ID                  string
	Repo                string   `json:"repo,omitempty"`
	Title               string   `json:"title,omitempty"`
	Body                string   `json:"body,omitempty"`
	Labels              []string `json:"labels,omitempty"`
	URL                 string   `json:"url,omitempty"`
	UpdatedAt           string   `json:"updated_at,omitempty"`
	State               State
	Unmanaged           bool
	GithubClosed        bool
	PID                 int
	WorktreePath        string
	AgentTabID          string `json:"agent_tab_id,omitempty"`
	AgentPaneID         string `json:"agent_pane_id,omitempty"`
	ProcessCreationTime int64
	LastReason          string
	ActivePhase         SubPhase           `json:"active_phase,omitempty"`    // PLAN, APPLY, REVIEW, FIX, DIRECT, ""
	FixRetryCount       int                `json:"fix_retry_count,omitempty"` // 0..MaxFixRetries
	ReviewSeverity      string             `json:"review_severity,omitempty"` // CLEAN, BLOCKER, ""
	DirectMode          bool               `json:"direct_mode,omitempty"`     // true = fast-path
	BlockedBy           []string           `json:"blocked_by,omitempty"`      // Issue IDs that block this issue
	LastGateDenial      *GateDenial        `json:"last_gate_denial,omitempty"`
	Cancel              context.CancelFunc `json:"-"`
}

var (
	depRegex      = regexp.MustCompile(`(?i)(?:bloquead[oa]\s+(?:por|hasta(?:\s+mergear)?)|blocked\s+by|depends\s+on|dependencia[s]?)\s*[:\s-]*([^\r\n]+)`)
	issueNumRegex = regexp.MustCompile(`#(\d+)`)
)

// ExtractBlockedBy inspects issue markdown description to extract blocking issue IDs.
func ExtractBlockedBy(body string) []string {
	if body == "" {
		return nil
	}
	var blockedBy []string
	seen := make(map[string]bool)

	lines := strings.Split(body, "\n")
	for _, line := range lines {
		trimmed := strings.TrimSpace(line)
		if depRegex.MatchString(trimmed) {
			matches := issueNumRegex.FindAllStringSubmatch(trimmed, -1)
			for _, m := range matches {
				if len(m) > 1 {
					id := m[1]
					if !seen[id] {
						seen[id] = true
						blockedBy = append(blockedBy, id)
					}
				}
			}
		}
	}
	return blockedBy
}

func (iss *IssueFSM) GetBlockedBy() []string {
	if len(iss.BlockedBy) > 0 {
		return iss.BlockedBy
	}
	if iss.Body != "" {
		return ExtractBlockedBy(iss.Body)
	}
	return nil
}

// RecordGateDenial persiste el último rechazo del gate (código, resultado y
// causa) para que el dispatch de FIX lo inyecte en el prompt de remediación.
func (iss *IssueFSM) RecordGateDenial(code, result, reason string) {
	iss.LastGateDenial = &GateDenial{Code: code, Result: result, Reason: reason}
}

func (iss *IssueFSM) CanRetryFix() bool  { return iss.FixRetryCount < MaxFixRetries }
func (iss *IssueFSM) IncrementFixRetry() { iss.FixRetryCount++ }

func (iss *IssueFSM) ResetPhaseState() {
	iss.ActivePhase = PhaseNone
	iss.FixRetryCount = 0
	iss.ReviewSeverity = ""
	iss.DirectMode = false
	iss.LastGateDenial = nil
}

func (iss *IssueFSM) Clone() *IssueFSM {
	if iss == nil {
		return nil
	}
	cloned := *iss
	if iss.Labels != nil {
		cloned.Labels = make([]string, len(iss.Labels))
		copy(cloned.Labels, iss.Labels)
	}
	if iss.BlockedBy != nil {
		cloned.BlockedBy = make([]string, len(iss.BlockedBy))
		copy(cloned.BlockedBy, iss.BlockedBy)
	}
	if iss.LastGateDenial != nil {
		denialCopy := *iss.LastGateDenial
		cloned.LastGateDenial = &denialCopy
	}
	return &cloned
}

// UnresolvedDependencies returns a slice of blocking issue IDs that are still active/open.
func (r *FSMRegistry) UnresolvedDependencies(iss *IssueFSM) []string {
	if iss == nil {
		return nil
	}
	deps := iss.GetBlockedBy()
	if len(deps) == 0 {
		return nil
	}

	r.mu.RLock()
	defer r.mu.RUnlock()

	var unresolved []string
	for _, depID := range deps {
		if depID == iss.ID {
			continue // avoid self-blockers
		}
		dep, ok := r.states[depID]
		if ok && dep.State != DONE && !dep.GithubClosed {
			unresolved = append(unresolved, depID)
		}
	}
	return unresolved
}

var TransitionMatrix = map[State][]State{
	PENDING:    {ISOLATING},
	ISOLATING:  {DELEGATING, FAILED, STALE},
	DELEGATING: {WORKING, FAILED, STALE},
	WORKING:    {REVIEWING, FAILED, STALE},
	REVIEWING:  {SEALING, STALE},
	SEALING:    {CLEANING, STALE},
	CLEANING:   {DONE, ORPHAN, STALE},
	ORPHAN:     {CLEANING, STALE},
	FAILED:     {ISOLATING},
	STALE:      {ISOLATING, REVIEWING, CLEANING},
}

type StateEnvelope struct {
	Revision     int64                `json:"revision"`
	TrackedRepos []string             `json:"tracked_repos,omitempty"`
	Issues       map[string]*IssueFSM `json:"issues"`
}

type FSMRegistry struct {
	StateDir     string
	LockTimeout  time.Duration
	Revision     int64
	trackedRepos []string
	mu           sync.RWMutex
	holders      map[string]struct{}
	states       map[string]*IssueFSM
}

func NewFSMRegistry(stateDir string) *FSMRegistry {
	return &FSMRegistry{
		StateDir:    stateDir,
		LockTimeout: 10 * time.Second,
		holders:     make(map[string]struct{}),
		states:      make(map[string]*IssueFSM),
	}
}

// GetStates returns a deep copy of the state map.
func (r *FSMRegistry) GetStates() map[string]*IssueFSM {
	r.mu.RLock()
	defer r.mu.RUnlock()
	copyMap := make(map[string]*IssueFSM, len(r.states))
	for k, v := range r.states {
		copyMap[k] = v.Clone()
	}
	return copyMap
}

func isActiveAgentState(st State) bool {
	return st == ISOLATING || st == DELEGATING || st == WORKING || st == REVIEWING || st == SEALING || st == CLEANING
}

// ActiveAgents returns the total number of active agent slots occupied across processes.
func (r *FSMRegistry) ActiveAgents() int {
	_ = r.HydrateState()
	r.mu.RLock()
	defer r.mu.RUnlock()

	activeSet := make(map[string]struct{})
	for id, iss := range r.states {
		if isActiveAgentState(iss.State) {
			activeSet[id] = struct{}{}
		}
	}
	for id := range r.holders {
		activeSet[id] = struct{}{}
	}
	return len(activeSet)
}

// TryAcquire attempts to reserve one concurrency slot for the given issue.
// Checks both in-memory holders and persisted state.json across processes under file lock.
func (r *FSMRegistry) TryAcquire(issueID string) bool {
	acquired := false
	_ = r.withLock(func() error {
		_ = r.hydrateStateLocked()
		r.mu.Lock()
		defer r.mu.Unlock()

		activeSet := make(map[string]struct{})
		for id, iss := range r.states {
			if id != issueID && isActiveAgentState(iss.State) {
				activeSet[id] = struct{}{}
			}
		}
		for id := range r.holders {
			if id != issueID {
				activeSet[id] = struct{}{}
			}
		}

		if len(activeSet) < MaxConcurrentAgents {
			r.holders[issueID] = struct{}{}
			acquired = true
		}
		return nil
	})
	return acquired
}

// Release frees the slot owned by the given issue.
func (r *FSMRegistry) Release(issueID string) {
	r.mu.Lock()
	defer r.mu.Unlock()
	delete(r.holders, issueID)
}

func (r *FSMRegistry) withLock(fn func() error) error {
	timeout := r.LockTimeout
	if timeout <= 0 {
		timeout = 10 * time.Second
	}
	unlock, err := AcquireFileLock(r.StateDir, timeout)
	if err != nil {
		return err
	}
	defer unlock()
	return fn()
}

func (r *FSMRegistry) findIssueLocked(id string) (*IssueFSM, string, bool) {
	if iss, exists := r.states[id]; exists {
		return iss, id, true
	}
	var matchedIss *IssueFSM
	var matchedKey string
	matchCount := 0
	targetSuffix := "#" + id
	for k, iss := range r.states {
		if strings.HasSuffix(k, targetSuffix) || (iss.ID == id) {
			matchedIss = iss
			matchedKey = k
			matchCount++
		}
	}
	if matchCount == 1 {
		return matchedIss, matchedKey, true
	}
	return nil, "", false
}

func (r *FSMRegistry) Save(issue *IssueFSM) error {
	if issue == nil {
		return nil
	}
	return r.withLock(func() error {
		_ = r.hydrateStateLocked()
		r.mu.Lock()
		key := issue.ID
		if issue.Repo != "" && !strings.Contains(issue.ID, "#") {
			key = issue.Repo + "#" + issue.ID
		}
		r.states[key] = issue.Clone()
		r.mu.Unlock()
		return r.persistStateLocked()
	})
}

func (r *FSMRegistry) UpdateIssue(id string, fn func(iss *IssueFSM) error) error {
	return r.withLock(func() error {
		_ = r.hydrateStateLocked()
		r.mu.Lock()
		iss, key, exists := r.findIssueLocked(id)
		if !exists {
			r.mu.Unlock()
			return fmt.Errorf("issue #%s not found", id)
		}
		if err := fn(iss); err != nil {
			r.mu.Unlock()
			return err
		}
		r.states[key] = iss
		r.mu.Unlock()
		return r.persistStateLocked()
	})
}

func (r *FSMRegistry) Delete(issueID string) error {
	return r.withLock(func() error {
		_ = r.hydrateStateLocked()
		r.mu.Lock()
		_, key, found := r.findIssueLocked(issueID)
		if found {
			delete(r.states, key)
			delete(r.holders, key)
		} else {
			delete(r.states, issueID)
			delete(r.holders, issueID)
		}
		r.mu.Unlock()
		return r.persistStateLocked()
	})
}

func (r *FSMRegistry) PersistState() error {
	return r.withLock(func() error {
		return r.persistStateLocked()
	})
}

func (r *FSMRegistry) GetTrackedRepos() []string {
	r.mu.RLock()
	defer r.mu.RUnlock()
	if len(r.trackedRepos) == 0 {
		defaultRepo := os.Getenv("GITHUB_REPO")
		if defaultRepo == "" {
			defaultRepo = "mmarcoschambi/swing-momentum-v1"
		}
		return []string{defaultRepo}
	}
	repos := make([]string, len(r.trackedRepos))
	copy(repos, r.trackedRepos)
	return repos
}

func (r *FSMRegistry) AddTrackedRepo(repo string) (bool, error) {
	repo = strings.TrimSpace(repo)
	if repo == "" {
		return false, fmt.Errorf("invalid repository: empty")
	}
	var added bool
	err := r.withLock(func() error {
		_ = r.hydrateStateLocked()
		r.mu.Lock()
		for _, existing := range r.trackedRepos {
			if strings.EqualFold(existing, repo) {
				r.mu.Unlock()
				return nil
			}
		}
		r.trackedRepos = append(r.trackedRepos, repo)
		added = true
		r.mu.Unlock()
		return r.persistStateLocked()
	})
	return added, err
}

func (r *FSMRegistry) RemoveTrackedRepo(repo string) (bool, error) {
	repo = strings.TrimSpace(repo)
	if repo == "" {
		return false, fmt.Errorf("invalid repository: empty")
	}
	var removed bool
	err := r.withLock(func() error {
		_ = r.hydrateStateLocked()
		r.mu.Lock()
		var updated []string
		for _, existing := range r.trackedRepos {
			if strings.EqualFold(existing, repo) {
				removed = true
			} else {
				updated = append(updated, existing)
			}
		}
		r.trackedRepos = updated
		r.mu.Unlock()
		if removed {
			return r.persistStateLocked()
		}
		return nil
	})
	return removed, err
}

func (r *FSMRegistry) persistStateLocked() error {
	r.mu.Lock()
	r.Revision++
	envelope := StateEnvelope{
		Revision:     r.Revision,
		TrackedRepos: r.trackedRepos,
		Issues:       r.states,
	}
	data, err := json.MarshalIndent(envelope, "", "  ")
	r.mu.Unlock()
	if err != nil {
		return err
	}

	if err := os.MkdirAll(r.StateDir, 0755); err != nil {
		return err
	}

	tempFile := filepath.Join(r.StateDir, "state.tmp.json")
	finalFile := filepath.Join(r.StateDir, "state.json")

	f, err := os.OpenFile(tempFile, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0644)
	if err != nil {
		return err
	}

	if _, err := f.Write(data); err != nil {
		_ = f.Close()
		return err
	}

	if err := f.Sync(); err != nil {
		_ = f.Close()
		return err
	}

	if err := f.Close(); err != nil {
		return err
	}

	return os.Rename(tempFile, finalFile)
}

// HydrateState reads state.json without modifying states (safe for CLI / read-only)
func (r *FSMRegistry) HydrateState() error {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.hydrateStateLocked()
}

func (r *FSMRegistry) hydrateStateLocked() error {
	finalFile := filepath.Join(r.StateDir, "state.json")
	data, err := os.ReadFile(finalFile)
	if err != nil {
		if os.IsNotExist(err) {
			if len(r.trackedRepos) == 0 {
				defaultRepo := os.Getenv("GITHUB_REPO")
				if defaultRepo == "" {
					defaultRepo = "mmarcoschambi/swing-momentum-v1"
				}
				r.trackedRepos = []string{defaultRepo}
			}
			return nil
		}
		return err
	}

	// Try unmarshaling new envelope format first
	var env StateEnvelope
	if err := json.Unmarshal(data, &env); err == nil && env.Issues != nil {
		r.Revision = env.Revision
		r.states = env.Issues
		r.trackedRepos = env.TrackedRepos
		if len(r.trackedRepos) == 0 {
			defaultRepo := os.Getenv("GITHUB_REPO")
			if defaultRepo == "" {
				defaultRepo = "mmarcoschambi/swing-momentum-v1"
			}
			r.trackedRepos = []string{defaultRepo}
		}
		return nil
	}

	// Backward compatibility: raw map of issues
	var rawMap map[string]*IssueFSM
	if err := json.Unmarshal(data, &rawMap); err == nil {
		r.Revision = 0
		r.states = rawMap
		defaultRepo := os.Getenv("GITHUB_REPO")
		if defaultRepo == "" {
			defaultRepo = "mmarcoschambi/swing-momentum-v1"
		}
		r.trackedRepos = []string{defaultRepo}
		return nil
	}

	// Graceful corruption handling
	corruptFile := filepath.Join(r.StateDir, "state.corrupt.json")
	_ = os.Rename(finalFile, corruptFile)
	return nil
}

// RecoverState hydrates state and flags abandoned active tasks as STALE on cold TUI boot
func (r *FSMRegistry) RecoverState() error {
	if err := r.HydrateState(); err != nil {
		return err
	}

	r.mu.Lock()
	defer r.mu.Unlock()

	for _, issue := range r.states {
		if issue.State == ISOLATING || issue.State == DELEGATING || issue.State == WORKING || issue.State == REVIEWING || issue.State == SEALING || issue.State == CLEANING {
			issue.State = STALE
			issue.LastReason = "Process interrupted on system restart"
		}
	}
	return nil
}

func (r *FSMRegistry) LoadState() error {
	return r.HydrateState()
}

func (r *FSMRegistry) TransitionTo(issue *IssueFSM, next State, reason string) error {
	if issue == nil {
		return fmt.Errorf("cannot transition nil issue")
	}
	return r.withLock(func() error {
		_ = r.hydrateStateLocked()
		r.mu.Lock()

		target, key, exists := r.findIssueLocked(issue.ID)
		if !exists {
			target = issue.Clone()
			key = issue.ID
			if issue.Repo != "" && !strings.Contains(issue.ID, "#") {
				key = issue.Repo + "#" + issue.ID
			}
			r.states[key] = target
		}

		valid := false
		for _, allowed := range TransitionMatrix[target.State] {
			if allowed == next {
				valid = true
				break
			}
		}
		if !valid {
			r.mu.Unlock()
			return fmt.Errorf("invalid transition from %s to %s", target.State, next)
		}

		if target.State == FAILED && next == ISOLATING {
			if target.WorktreePath != "" {
				if err := os.RemoveAll(target.WorktreePath); err != nil {
					r.mu.Unlock()
					return fmt.Errorf("failed to wipe partial worktree %s: %w", target.WorktreePath, err)
				}
				target.WorktreePath = ""
			}
			target.PID = 0
			target.Unmanaged = false
			target.AgentTabID = ""
			target.AgentPaneID = ""
		}

		if next == SEALING || ((target.State == STALE || target.State == FAILED) && next == ISOLATING) {
			target.ResetPhaseState()
			if issue != target {
				issue.ResetPhaseState()
			}
		}

		target.State = next
		target.LastReason = reason
		if issue != target {
			issue.State = next
			issue.LastReason = reason
			target.Title = issue.Title
			target.Body = issue.Body
			target.Labels = issue.Labels
			target.URL = issue.URL
			target.WorktreePath = issue.WorktreePath
			target.Unmanaged = issue.Unmanaged
			target.AgentTabID = issue.AgentTabID
			target.AgentPaneID = issue.AgentPaneID
			target.ActivePhase = issue.ActivePhase
			target.FixRetryCount = issue.FixRetryCount
			target.ReviewSeverity = issue.ReviewSeverity
			target.DirectMode = issue.DirectMode
			target.LastGateDenial = issue.LastGateDenial
		}

		r.mu.Unlock()
		return r.persistStateLocked()
	})
}

func (r *FSMRegistry) ResetIssue(issue *IssueFSM) error {
	if issue == nil {
		return fmt.Errorf("cannot reset nil issue")
	}
	return r.withLock(func() error {
		_ = r.hydrateStateLocked()
		r.mu.Lock()

		target, key, exists := r.findIssueLocked(issue.ID)
		if !exists {
			target = issue.Clone()
			key = issue.ID
			if issue.Repo != "" && !strings.Contains(issue.ID, "#") {
				key = issue.Repo + "#" + issue.ID
			}
			r.states[key] = target
		}

		if target.WorktreePath != "" {
			_ = os.RemoveAll(target.WorktreePath)
			target.WorktreePath = ""
		}

		target.State = PENDING
		target.LastReason = "User reverted changes"
		target.Unmanaged = false
		target.PID = 0
		target.AgentTabID = ""
		target.AgentPaneID = ""
		target.ResetPhaseState()

		if issue != target {
			issue.State = PENDING
			issue.LastReason = target.LastReason
			issue.WorktreePath = ""
			issue.Unmanaged = false
			issue.PID = 0
			issue.AgentTabID = ""
			issue.AgentPaneID = ""
			issue.ResetPhaseState()
		}

		r.mu.Unlock()
		return r.persistStateLocked()
	})
}
