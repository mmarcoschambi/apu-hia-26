package tui

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
	"github.com/mmarcoschambi/loom/internal/exec"
	"github.com/mmarcoschambi/loom/internal/fsm"
	"github.com/mmarcoschambi/loom/internal/judge"
	"github.com/mmarcoschambi/loom/internal/poller"
)

type agentWaitMsg struct {
	issueID string
	status  string
	err     error
}

type judgeEventMsg struct {
	kind string // "j1_ok" | "error"
	text string
}

type ViewMode int

const (
	ViewModeSplit ViewMode = iota
	ViewModeBacklogOnly
	ViewModeInspectorOnly
)

type LoomModel struct {
	Registry       *fsm.FSMRegistry
	Poller         *poller.GithubPoller
	Issues         []*fsm.IssueFSM
	Cursor         int
	SelectedIssue  *fsm.IssueFSM
	Width          int
	Height         int
	ViewMode       ViewMode
	ToastMsg       string
	IsBusy         bool
	BusyIssueID    string
	IsValidating   bool
	SelectedAgent  string
	CollapsedRepos map[string]bool
}

func getRepoName(iss *fsm.IssueFSM) string {
	if iss != nil && iss.Repo != "" {
		return iss.Repo
	}
	defaultRepo := os.Getenv("GITHUB_REPO")
	if defaultRepo == "" {
		defaultRepo = "mmarcoschambi/swing-momentum-v1"
	}
	return defaultRepo
}

func (m *LoomModel) getVisibleIssues() []*fsm.IssueFSM {
	if m.CollapsedRepos == nil {
		m.CollapsedRepos = make(map[string]bool)
	}
	var visible []*fsm.IssueFSM
	for _, iss := range m.Issues {
		r := getRepoName(iss)
		if !m.CollapsedRepos[r] {
			visible = append(visible, iss)
		}
	}
	return visible
}

func copyToWindowsClipboard(text string) error {
	cmd := exec.DefaultCommandRunner(context.Background(), "clip.exe")
	cmd.Stdin = strings.NewReader(text)
	return cmd.Run()
}

func fetchSortedIssues(reg *fsm.FSMRegistry, prevSelectedID string) ([]*fsm.IssueFSM, int, *fsm.IssueFSM) {
	var list []*fsm.IssueFSM
	for _, v := range reg.GetStates() {
		issueCopy := *v
		list = append(list, &issueCopy)
	}

	// Sort by Repo ASC, then Issue Number DESC
	sort.Slice(list, func(i, j int) bool {
		repoI := getRepoName(list[i])
		repoJ := getRepoName(list[j])
		if repoI != repoJ {
			return repoI < repoJ
		}
		numI, errI := strconv.Atoi(list[i].ID)
		numJ, errJ := strconv.Atoi(list[j].ID)
		if errI == nil && errJ == nil {
			return numI > numJ
		}
		return list[i].ID > list[j].ID
	})

	if len(list) == 0 {
		return list, 0, nil
	}

	cursor := 0
	if prevSelectedID != "" {
		for i, iss := range list {
			if iss.ID == prevSelectedID {
				cursor = i
				break
			}
		}
	}

	return list, cursor, list[cursor]
}

func isDesktopAgent(agent string) bool {
	a := strings.ToLower(agent)
	return a == "zcode" || a == "code" || a == "cursor"
}

// buildPhasePrompt construye el prompt de dispatch con el reintento REAL del
// issue y el denial persistido del último rechazo del gate (inyección
// quirúrgica del denial.code en la fase FIX).
func buildPhasePrompt(iss *fsm.IssueFSM, payload exec.IssuePayload) string {
	var gateForResult []exec.GentleGateResult
	if d := iss.LastGateDenial; d != nil {
		gateForResult = append(gateForResult, exec.GateResultFromDenial(d.Code, d.Result, d.Reason))
	}
	return exec.BuildPromptForIssue(iss.ID, payload, iss.WorktreePath, iss.FixRetryCount, gateForResult...)
}

func formatAgentBadge(agent string) string {
	name := strings.ToUpper(agent)
	if isDesktopAgent(agent) {
		return fmt.Sprintf("[🖥️ %s (DESKTOP)]", name)
	}
	return fmt.Sprintf("[🤖 %s (CLI)]", name)
}

func NewLoomModel(reg *fsm.FSMRegistry, p *poller.GithubPoller) *LoomModel {
	issues, cursor, selected := fetchSortedIssues(reg, "")
	agent := strings.ToLower(strings.TrimSpace(os.Getenv("LOOM_AGENT")))
	if agent == "" {
		agent = "agy"
	}
	return &LoomModel{
		Registry:       reg,
		Poller:         p,
		Issues:         issues,
		Cursor:         cursor,
		SelectedIssue:  selected,
		Width:          80,
		Height:         24,
		ViewMode:       ViewModeSplit,
		SelectedAgent:  agent,
		CollapsedRepos: make(map[string]bool),
	}
}

type pollerDeltaMsg poller.Delta

func waitForDelta(sub <-chan poller.Delta) tea.Cmd {
	return func() tea.Msg {
		delta := <-sub
		return pollerDeltaMsg(delta)
	}
}

func (m *LoomModel) Init() tea.Cmd {
	if m.Poller != nil {
		return waitForDelta(m.Poller.Deltas())
	}
	return nil
}

type hardRemoveMsg struct {
	err error
}

func (m *LoomModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case judgeEventMsg:
		m.IsBusy = false
		m.BusyIssueID = ""
		m.ToastMsg = msg.text
		return m, nil
	case tea.WindowSizeMsg:
		m.Width = msg.Width
		m.Height = msg.Height
		return m, nil
	case transitionOkMsg:
		m.IsBusy = false
		m.BusyIssueID = ""
		m.IsValidating = false
		prevID := ""
		if m.SelectedIssue != nil {
			prevID = m.SelectedIssue.ID
		}
		m.Issues, m.Cursor, m.SelectedIssue = fetchSortedIssues(m.Registry, prevID)
		if m.SelectedIssue != nil {
			if m.SelectedIssue.State == fsm.SEALING {
				m.ToastMsg = "✅ Issue validated & sealed! Press [p] for PR or [d] to clean & finish."
			} else if m.SelectedIssue.State == fsm.DONE {
				m.ToastMsg = "🎉 Issue completed and worktree cleaned successfully!"
			} else {
				m.ToastMsg = "✅ Agent finished! Inspect files & press [v] to Validate & Seal."
			}
		}
		return m, nil
	case agentWaitMsg:
		m.IsBusy = false
		m.BusyIssueID = ""
		m.IsValidating = false
		if msg.status == "blocked" {
			m.ToastMsg = fmt.Sprintf("⚠️ Issue #%s agent needs your input! Press [f] to focus tab", msg.issueID)
		} else if msg.status == "done" || msg.status == "idle" {
			m.ToastMsg = fmt.Sprintf("✅ Issue #%s agent completed tasks! Ready to [v] Validate & Seal", msg.issueID)
		} else if msg.err != nil {
			m.ToastMsg = fmt.Sprintf("⚠️ Issue #%s: %s", msg.issueID, msg.err.Error())
		}
		prevID := ""
		if m.SelectedIssue != nil {
			prevID = m.SelectedIssue.ID
		}
		m.Issues, m.Cursor, m.SelectedIssue = fetchSortedIssues(m.Registry, prevID)
		return m, nil
	case hardRemoveMsg:
		m.IsBusy = false
		m.BusyIssueID = ""
		m.IsValidating = false
		if msg.err != nil {
			m.ToastMsg = fmt.Sprintf("⚠️ %s", msg.err.Error())
		}
		prevID := ""
		if m.SelectedIssue != nil {
			prevID = m.SelectedIssue.ID
		}
		m.Issues, m.Cursor, m.SelectedIssue = fetchSortedIssues(m.Registry, prevID)
		return m, nil
	case pollerDeltaMsg:
		// We received a new delta! Deterministically refresh backlog and preserve selected issue
		prevID := ""
		if m.SelectedIssue != nil {
			prevID = m.SelectedIssue.ID
		}
		m.Issues, m.Cursor, m.SelectedIssue = fetchSortedIssues(m.Registry, prevID)

		if m.Poller != nil {
			return m, waitForDelta(m.Poller.Deltas())
		}
		return m, nil
	case tea.KeyMsg:
		switch msg.String() {
		case "q", "ctrl+c":
			return m, tea.Quit
		case "tab", "m":
			m.ViewMode = (m.ViewMode + 1) % 3
			return m, nil
		case "y":
			if m.SelectedIssue != nil {
				var b strings.Builder
				iss := m.SelectedIssue
				b.WriteString(fmt.Sprintf("#%s: %s\n", iss.ID, iss.Title))
				if iss.UpdatedAt != "" {
					b.WriteString(fmt.Sprintf("Updated: %s\n", iss.UpdatedAt))
				}
				if iss.URL != "" {
					b.WriteString(fmt.Sprintf("URL: %s\n", iss.URL))
				}
				b.WriteString(fmt.Sprintf("FSM State: [%s]\n", iss.State))
				if iss.WorktreePath != "" {
					b.WriteString(fmt.Sprintf("Worktree: %s\n", iss.WorktreePath))
				}
				if len(iss.Labels) > 0 {
					b.WriteString(fmt.Sprintf("Labels: %s\n", strings.Join(iss.Labels, ", ")))
				}
				if iss.Body != "" {
					b.WriteString(fmt.Sprintf("\nDescription:\n%s\n", iss.Body))
				}

				// Step-by-Step Action
				b.WriteString("\nStep-by-Step Action:\n")
				switch iss.State {
				case fsm.PENDING, fsm.STALE, fsm.FAILED:
					b.WriteString("Press [s] to isolate worktree and start working\n")
				case fsm.WORKING:
					b.WriteString("Worktree active! Inspect files, then press [v] to Validate & Seal\n")
				case fsm.SEALING:
					b.WriteString("Changes sealed! Press [d] to clean worktree & mark [DONE]\n")
				case fsm.DONE:
					b.WriteString("Issue completed and worktree cleaned successfully.\n")
				default:
					b.WriteString("Manage issue with [s], [v], [d], [x]\n")
				}

				// Live Agent Output
				if iss.WorktreePath != "" {
					recentLogs := exec.ReadRecentLogs(iss.WorktreePath, 10)
					if recentLogs != "" {
						b.WriteString(fmt.Sprintf("\nLive Agent Output:\n%s\n", recentLogs))
					}
				}

				_ = copyToWindowsClipboard(b.String())
				m.ToastMsg = fmt.Sprintf("📋 Copied complete Issue #%s report to clipboard!", iss.ID)
				return m, nil
			}
		case "Y", "c":
			var b strings.Builder
			b.WriteString("=== LOOM BACKLOG PIPELINE ===\n")
			for _, iss := range m.Issues {
				b.WriteString(fmt.Sprintf("[%s] #%s %s\n", iss.State, iss.ID, iss.Title))
			}
			_ = copyToWindowsClipboard(b.String())
			m.ToastMsg = "📋 Copied Backlog list to clipboard!"
			return m, nil
		case "left", "h":
			if m.SelectedIssue != nil {
				repo := getRepoName(m.SelectedIssue)
				if m.CollapsedRepos == nil {
					m.CollapsedRepos = make(map[string]bool)
				}
				m.CollapsedRepos[repo] = true
				visible := m.getVisibleIssues()
				if len(visible) > 0 {
					if m.Cursor >= len(visible) {
						m.Cursor = len(visible) - 1
					}
					m.SelectedIssue = visible[m.Cursor]
				} else {
					m.Cursor = 0
					m.SelectedIssue = nil
				}
				m.ToastMsg = fmt.Sprintf("📁 Collapsed repository %s", repo)
				return m, nil
			}
		case "right", "l":
			if m.CollapsedRepos == nil {
				m.CollapsedRepos = make(map[string]bool)
			}
			if m.SelectedIssue != nil {
				repo := getRepoName(m.SelectedIssue)
				m.CollapsedRepos[repo] = false
				m.ToastMsg = fmt.Sprintf("📂 Expanded repository %s", repo)
			} else {
				for r := range m.CollapsedRepos {
					m.CollapsedRepos[r] = false
				}
				m.ToastMsg = "📂 Expanded repositories"
			}
			visible := m.getVisibleIssues()
			if len(visible) > 0 {
				if m.Cursor >= len(visible) {
					m.Cursor = len(visible) - 1
				}
				m.SelectedIssue = visible[m.Cursor]
			}
			return m, nil
		case "up", "k":
			m.ToastMsg = ""
			visible := m.getVisibleIssues()
			if len(visible) > 0 && m.Cursor > 0 {
				m.Cursor--
				m.SelectedIssue = visible[m.Cursor]
			}
		case "down", "j":
			m.ToastMsg = ""
			visible := m.getVisibleIssues()
			if len(visible) > 0 && m.Cursor < len(visible)-1 {
				m.Cursor++
				m.SelectedIssue = visible[m.Cursor]
			}
		case "s":
			if m.IsBusy {
				m.ToastMsg = fmt.Sprintf("⏳ Agent is busy on Issue #%s. Please wait for completion.", m.BusyIssueID)
				return m, nil
			}
			if m.SelectedIssue != nil && m.SelectedIssue.State == fsm.WORKING {
				if m.SelectedIssue.ActivePhase == fsm.PhaseFix {
					if !m.SelectedIssue.CanRetryFix() {
						m.ToastMsg = "🛑 Circuit Breaker Tripped: 2 reintentos de corrección alcanzados. Intervención manual requerida."
						return m, nil
					}
					m.SelectedIssue.IncrementFixRetry()
					_ = m.Registry.Save(m.SelectedIssue)
				}
				m.IsBusy = true
				m.BusyIssueID = m.SelectedIssue.ID
				payload := exec.IssuePayload{
					Title:  m.SelectedIssue.Title,
					Body:   m.SelectedIssue.Body,
					URL:    m.SelectedIssue.URL,
					Labels: m.SelectedIssue.Labels,
				}
				promptText := buildPhasePrompt(m.SelectedIssue, payload)
				dispatched := false
				if exec.IsHerdrRunning() {
					ctx := exec.ExecContext{Cwd: m.SelectedIssue.WorktreePath}
					tabLabel := fmt.Sprintf("%s-%s", strings.ToLower(string(m.SelectedIssue.ActivePhase)), m.SelectedIssue.ID)
					tabID, paneID, err := exec.RunHerdrTabCreate(ctx, tabLabel)
					if err == nil {
						m.SelectedIssue.AgentTabID = tabID
						m.SelectedIssue.AgentPaneID = paneID
						_ = m.Registry.Save(m.SelectedIssue)
						_ = exec.RunHerdrAgentStart(ctx, tabLabel, m.SelectedAgent, paneID, promptText)
						dispatched = true
					}
				}
				m.IsBusy = false
				m.BusyIssueID = ""
				if dispatched {
					m.ToastMsg = fmt.Sprintf("🚀 Dispatched %s session in Herdr for Issue #%s", m.SelectedIssue.ActivePhase, m.SelectedIssue.ID)
				} else {
					// Sin Herdr no se lanzó nada: error visible, jamás un toast de éxito fantasma.
					m.ToastMsg = fmt.Sprintf("⚠️ Herdr no está corriendo: no se dispatchó la sesión %s del Issue #%s. Iniciá Herdr y presioná [s] de nuevo.", m.SelectedIssue.ActivePhase, m.SelectedIssue.ID)
				}
				return m, nil
			}
			if m.SelectedIssue != nil && (m.SelectedIssue.State == fsm.PENDING || m.SelectedIssue.State == fsm.STALE || m.SelectedIssue.State == fsm.FAILED || m.SelectedIssue.State == fsm.ORPHAN) {
				unresolved := m.Registry.UnresolvedDependencies(m.SelectedIssue)
				if len(unresolved) > 0 {
					m.ToastMsg = fmt.Sprintf("⛔ Bloqueado: Depende de issue(s) #%s sin resolver. Mergear/cerrar antes de empezar.", strings.Join(unresolved, ", #"))
					return m, nil
				}
				if !m.Registry.TryAcquire(m.SelectedIssue.ID) {
					m.ToastMsg = fmt.Sprintf("🚦 Límite alcanzado: Máximo %d agentes en paralelo. Liberá uno con [d] o [r].", fsm.MaxConcurrentAgents)
					return m, nil
				}
				m.IsBusy = true
				m.BusyIssueID = m.SelectedIssue.ID
				m.ToastMsg = fmt.Sprintf("🚀 Starting interactive Agent session for Issue #%s...", m.SelectedIssue.ID)

				// 1. ISOLATING
				if err := m.Registry.TransitionTo(m.SelectedIssue, fsm.ISOLATING, "Start requested"); err != nil {
					m.Registry.Release(m.SelectedIssue.ID)
					m.IsBusy = false
					m.BusyIssueID = ""
					m.ToastMsg = fmt.Sprintf("⚠️ %s", err.Error())
					return m, nil
				}

				homeDir, _ := os.UserHomeDir()
				worktreePath := filepath.Join(homeDir, ".loom", "worktrees", m.SelectedIssue.ID)
				_ = os.MkdirAll(worktreePath, 0755)

				ctx := exec.ExecContext{Cwd: worktreePath}
				if err := exec.RunOrcaCreate(ctx, m.SelectedIssue.ID); err != nil {
					// Best-effort transition: the original error is what the user needs to see.
					_ = m.Registry.TransitionTo(m.SelectedIssue, fsm.FAILED, err.Error())
					m.Registry.Release(m.SelectedIssue.ID)
					m.IsBusy = false
					m.BusyIssueID = ""
					m.ToastMsg = fmt.Sprintf("⚠️ %s", err.Error())
					return m, nil
				}

				m.SelectedIssue.WorktreePath = worktreePath
				m.SelectedIssue.PID = 0
				_ = m.Registry.Save(m.SelectedIssue)

				// 2. DELEGATING
				if err := m.Registry.TransitionTo(m.SelectedIssue, fsm.DELEGATING, "Worktree created"); err != nil {
					m.Registry.Release(m.SelectedIssue.ID)
					m.IsBusy = false
					m.BusyIssueID = ""
					m.ToastMsg = fmt.Sprintf("⚠️ %s", err.Error())
					return m, nil
				}

				payload := exec.IssuePayload{
					Title:  m.SelectedIssue.Title,
					Body:   m.SelectedIssue.Body,
					URL:    m.SelectedIssue.URL,
					Labels: m.SelectedIssue.Labels,
				}
				if payload.Title == "" {
					payload.Title = "Issue " + m.SelectedIssue.ID
				}
				if err := exec.WriteOpenSpecScaffold(ctx, m.SelectedIssue.ID, payload); err != nil {
					// Best-effort transition: the original error is what the user needs to see.
					_ = m.Registry.TransitionTo(m.SelectedIssue, fsm.FAILED, err.Error())
					m.Registry.Release(m.SelectedIssue.ID)
					m.IsBusy = false
					m.BusyIssueID = ""
					m.ToastMsg = fmt.Sprintf("⚠️ %s", err.Error())
					return m, nil
				}

				// 3. WORKING: delegación exitosa (scaffold OpenSpec escrito),
				// la sesión del agente arranca en la sub-fase PLAN.
				if err := m.Registry.TransitionTo(m.SelectedIssue, fsm.WORKING, "Launching agent session"); err != nil {
					m.Registry.Release(m.SelectedIssue.ID)
					m.IsBusy = false
					m.BusyIssueID = ""
					m.ToastMsg = fmt.Sprintf("⚠️ %s", err.Error())
					return m, nil
				}

				m.SelectedIssue.ActivePhase = fsm.PhasePlan
				_ = m.Registry.Save(m.SelectedIssue)

				promptText := exec.BuildPlanPrompt(m.SelectedIssue.ID, payload)

				dispatched := false
				if exec.IsHerdrRunning() {
					tabID, paneID, err := exec.RunHerdrTabCreate(ctx, "issue-"+m.SelectedIssue.ID)
					if err == nil {
						m.SelectedIssue.AgentTabID = tabID
						m.SelectedIssue.AgentPaneID = paneID
						_ = m.Registry.Save(m.SelectedIssue)
						_ = exec.RunHerdrAgentStart(ctx, "loom-"+m.SelectedIssue.ID, m.SelectedAgent, paneID, promptText)
						dispatched = true
					}
				}

				m.IsBusy = false
				m.BusyIssueID = ""
				if dispatched {
					m.ToastMsg = fmt.Sprintf("✨ Agent attached to Issue #%s in Herdr! Press [f] to view", m.SelectedIssue.ID)
				} else {
					// Sin Herdr no se lanzó nada: error visible, jamás un toast de éxito fantasma.
					m.ToastMsg = fmt.Sprintf("⚠️ Herdr no está corriendo: no se lanzó ninguna sesión para el Issue #%s (worktree listo, fase %s). Iniciá Herdr y presioná [s] para despachar.", m.SelectedIssue.ID, m.SelectedIssue.ActivePhase)
				}
				return m, nil
			}
			return m, nil
		case "f":
			if m.SelectedIssue != nil {
				targetName := "loom-" + m.SelectedIssue.ID
				_ = exec.RunHerdrAgentFocus(targetName)
				m.ToastMsg = fmt.Sprintf("🎯 Focused Agent Tab for Issue #%s in Herdr", m.SelectedIssue.ID)
				return m, nil
			}
		case "a":
			if m.SelectedAgent == "agy" {
				m.SelectedAgent = "opencode"
			} else if m.SelectedAgent == "opencode" {
				m.SelectedAgent = "zcode"
			} else if m.SelectedAgent == "zcode" {
				m.SelectedAgent = "fx"
			} else {
				m.SelectedAgent = "agy"
			}
			if isDesktopAgent(m.SelectedAgent) {
				m.ToastMsg = fmt.Sprintf("🖥️ Switched to Desktop App: %s (GUI Subscription)", strings.ToUpper(m.SelectedAgent))
			} else {
				m.ToastMsg = fmt.Sprintf("🤖 Switched to CLI Agent: %s (Headless Autonomous)", strings.ToUpper(m.SelectedAgent))
			}
			return m, nil
		case "J":
			// Advisory judge gate (J1: freeze + dual judge tabs). ADVISORY
			// por diseño: no muta el FSM, no transiciona, no reemplaza [v].
			// `j` minúscula permanece como navegación vim (paper trail del
			// issue: comentario gh 5389549614 sobre la enmienda del AC2).
			if m.IsBusy {
				m.ToastMsg = "⏳ No se puede juzgar mientras el agente está escribiendo. Esperá a que termine."
				return m, nil
			}
			if m.SelectedIssue == nil || m.SelectedIssue.WorktreePath == "" {
				m.ToastMsg = "⚖️ Seleccioná un issue con worktree activo para lanzar el judge gate."
				return m, nil
			}
			if m.SelectedIssue.State != fsm.WORKING && m.SelectedIssue.State != fsm.SEALING {
				m.ToastMsg = fmt.Sprintf("⚖️ El judge gate requiere WORKING (o SEALING para pr); issue #%s está en %s.", m.SelectedIssue.ID, m.SelectedIssue.State)
				return m, nil
			}
			issueID := m.SelectedIssue.ID
			worktreePath := m.SelectedIssue.WorktreePath
			engineA := m.SelectedAgent
			return m, func() tea.Msg {
				mode := judge.ModePlan
				// Freeze + dual launch en background.
				paths, err := judge.ResolveSkillsPaths(worktreePath, mode)
				if err != nil {
					return judgeEventMsg{kind: "error", text: err.Error()}
				}
				fr, err := judge.Freeze(mode, &fsm.IssueFSM{ID: issueID, WorktreePath: worktreePath, Body: m.SelectedIssue.Body})
				if err != nil {
					return judgeEventMsg{kind: "error", text: fmt.Sprintf("freeze: %v", err)}
				}
				engineB := "agy"
				if engineA == engineB {
					engineB = "opencode"
				}
				if _, err := judge.LaunchDualTabs(&fsm.IssueFSM{ID: issueID, WorktreePath: worktreePath}, mode, fr, paths, engineA, engineB); err != nil {
					return judgeEventMsg{kind: "error", text: err.Error()}
				}
				return judgeEventMsg{
					kind: "j1_ok",
					text: fmt.Sprintf("⚖️ Judge J1 lanzado en Issue #%s — round %d, frozen:%s. Cuando ambos jueces terminen, corré: loomctl judge %s --merge",
						issueID, fr.Round, fr.Path, issueID),
				}
			}
		case "v":
			if m.IsBusy {
				m.ToastMsg = fmt.Sprintf("⏳ Cannot validate while agent is actively working on Issue #%s.", m.BusyIssueID)
				return m, nil
			}
			if m.SelectedIssue != nil && (m.SelectedIssue.State == fsm.WORKING || m.SelectedIssue.State == fsm.STALE) && m.SelectedIssue.WorktreePath != "" {
				issueID := m.SelectedIssue.ID
				worktreePath := m.SelectedIssue.WorktreePath
				m.IsBusy = true
				m.BusyIssueID = issueID
				m.IsValidating = true
				return m, func() tea.Msg {
					reviewCtx, reviewCancel := context.WithTimeout(context.Background(), 3*time.Minute)
					defer reviewCancel()
					ctx := exec.ExecContext{
						Ctx: reviewCtx,
						Cwd: worktreePath,
					}

					// 1. Stage changes (excluding review.log)
					_ = exec.RunGitStageAll(ctx)

					// 2. Evidencia ejecutable [JD-4]: -m pytest con el intérprete
					// resuelto por discovery. Fail-closed: sin intérprete o con
					// tests rojos NO se procede al gate ni al sello.
					if err := exec.RunPytestEvidence(ctx); err != nil {
						_ = m.Registry.UpdateIssue(issueID, func(iss *fsm.IssueFSM) error {
							iss.ReviewSeverity = "BLOCKER"
							iss.ActivePhase = fsm.PhaseFix
							return nil
						})
						return hardRemoveMsg{err: fmt.Errorf("pytest evidence failed: %w", err)}
					}

					// 3. Run Gentle Review Gate
					gateRes, err := exec.RunGentleReviewMode(ctx)
					sev := exec.DeriveReviewSeverity(gateRes)

					if err != nil || (!gateRes.Allowed && gateRes.Delivery != "disabled/unmanaged") {
						_ = m.Registry.UpdateIssue(issueID, func(iss *fsm.IssueFSM) error {
							iss.ReviewSeverity = sev
							iss.ActivePhase = fsm.PhaseFix
							iss.RecordGateDenial(exec.GateDenialInfo(gateRes))
							return nil
						})
						return hardRemoveMsg{err: fmt.Errorf("governance review gate rejected: %v", err)}
					}

					// 4. REVIEWING -> SEALING on Allowed == true
					issTarget := &fsm.IssueFSM{ID: issueID}
					if err := m.Registry.TransitionTo(issTarget, fsm.REVIEWING, "Gate approved"); err != nil {
						return hardRemoveMsg{err: err}
					}

					if err := m.Registry.TransitionTo(issTarget, fsm.SEALING, "Review mode passed"); err != nil {
						return hardRemoveMsg{err: err}
					}

					return transitionOkMsg{}
				}
			}
		case "d":
			if m.IsBusy {
				m.ToastMsg = fmt.Sprintf("⏳ Cannot clean while agent is actively working on Issue #%s.", m.BusyIssueID)
				return m, nil
			}
			if m.SelectedIssue != nil && m.SelectedIssue.State == fsm.SEALING {
				issueID := m.SelectedIssue.ID
				worktreePath := m.SelectedIssue.WorktreePath
				agentTabID := m.SelectedIssue.AgentTabID
				return m, func() tea.Msg {
					cleanCtx, cleanCancel := context.WithTimeout(context.Background(), 45*time.Second)
					defer cleanCancel()
					ctx := exec.ExecContext{
						Ctx: cleanCtx,
						Cwd: worktreePath,
					}

					issTarget := &fsm.IssueFSM{ID: issueID}
					// 6. CLEANING
					if err := m.Registry.TransitionTo(issTarget, fsm.CLEANING, "Closing worktree"); err != nil {
						return hardRemoveMsg{err: err}
					}
					m.Registry.Release(issueID)

					if agentTabID != "" {
						_ = exec.RunHerdrTabClose(agentTabID)
						_ = m.Registry.UpdateIssue(issueID, func(iss *fsm.IssueFSM) error {
							iss.AgentTabID = ""
							return nil
						})
					}

					if err := exec.RunOrcaRemove(ctx); err != nil {
						// Best-effort transition: the original error is what the user needs to see.
						_ = m.Registry.TransitionTo(issTarget, fsm.ORPHAN, err.Error())
						return hardRemoveMsg{err: err}
					}

					// 7. DONE
					if err := m.Registry.TransitionTo(issTarget, fsm.DONE, "Task completed and cleaned"); err != nil {
						return hardRemoveMsg{err: err}
					}

					return transitionOkMsg{}
				}
			}
		case "x":
			if m.SelectedIssue != nil {
				issueID := m.SelectedIssue.ID
				worktreePath := m.SelectedIssue.WorktreePath
				issTarget := &fsm.IssueFSM{ID: issueID}
				if m.SelectedIssue.State == fsm.ORPHAN {
					return m, func() tea.Msg {
						ctx := exec.ExecContext{Cwd: worktreePath}
						err := exec.RunOrcaRemove(ctx)
						_ = m.Registry.ResetIssue(issTarget)
						m.ToastMsg = fmt.Sprintf("🧹 Purged & reset Issue #%s", issueID)
						return hardRemoveMsg{err: err}
					}
				} else if m.SelectedIssue.State == fsm.STALE {
					return m, func() tea.Msg {
						err := m.Registry.TransitionTo(issTarget, fsm.CLEANING, "User pressed x")
						if err != nil {
							return hardRemoveMsg{err: err}
						}
						return transitionOkMsg{}
					}
				} else if m.SelectedIssue.State == fsm.FAILED {
					return m, func() tea.Msg {
						if worktreePath != "" {
							ctx := exec.ExecContext{Cwd: worktreePath}
							_ = exec.RunOrcaRemove(ctx)
						}
						_ = m.Registry.ResetIssue(issTarget)
						m.ToastMsg = fmt.Sprintf("🧹 Cleaned & reset Issue #%s", issueID)
						return transitionOkMsg{}
					}
				}
			}
		case "o":
			if m.SelectedIssue != nil && m.SelectedIssue.WorktreePath != "" {
				_ = exec.OpenInExplorer(m.SelectedIssue.WorktreePath)
				m.ToastMsg = fmt.Sprintf("📂 Opened worktree for Issue #%s in Explorer", m.SelectedIssue.ID)
				return m, nil
			}
		case "i":
			if m.SelectedIssue != nil && m.SelectedIssue.WorktreePath != "" {
				ctx := exec.ExecContext{Cwd: m.SelectedIssue.WorktreePath}
				payload := exec.IssuePayload{
					Title:  m.SelectedIssue.Title,
					Body:   m.SelectedIssue.Body,
					URL:    m.SelectedIssue.URL,
					Labels: m.SelectedIssue.Labels,
				}
				promptText := buildPhasePrompt(m.SelectedIssue, payload)
				exec.RunHerdrVisualWorktree(ctx, m.SelectedIssue.ID, promptText)
				m.ToastMsg = fmt.Sprintf("🤖 Launched interactive OpenCode in Herdr for Issue #%s", m.SelectedIssue.ID)
				return m, nil
			}
		case "p":
			if m.SelectedIssue != nil && (m.SelectedIssue.State == fsm.SEALING && !m.SelectedIssue.Unmanaged) {
				issueID := m.SelectedIssue.ID
				worktreePath := m.SelectedIssue.WorktreePath
				title := m.SelectedIssue.Title
				return m, func() tea.Msg {
					ctx := exec.ExecContext{Cwd: worktreePath}
					repo := os.Getenv("GITHUB_REPO")
					prURL, err := exec.RunCreatePR(ctx, issueID, title, repo)
					if err != nil {
						return hardRemoveMsg{err: fmt.Errorf("PR: %w", err)}
					}
					_ = m.Registry.UpdateIssue(issueID, func(iss *fsm.IssueFSM) error {
						iss.URL = prURL
						return nil
					})
					return transitionOkMsg{}
				}
			}
		case "r":
			if m.IsBusy {
				m.ToastMsg = fmt.Sprintf("⏳ Cannot reset while agent is actively working on Issue #%s.", m.BusyIssueID)
				return m, nil
			}
			if m.SelectedIssue != nil && m.SelectedIssue.State != fsm.PENDING {
				issueID := m.SelectedIssue.ID
				worktreePath := m.SelectedIssue.WorktreePath
				agentTabID := m.SelectedIssue.AgentTabID
				issTarget := &fsm.IssueFSM{ID: issueID}
				return m, func() tea.Msg {
					if agentTabID != "" {
						_ = exec.RunHerdrTabClose(agentTabID)
					}
					if worktreePath != "" {
						ctx := exec.ExecContext{Cwd: worktreePath}
						_ = exec.RunOrcaRemove(ctx)
					}
					if err := m.Registry.ResetIssue(issTarget); err != nil {
						return hardRemoveMsg{err: err}
					}
					m.Registry.Release(issueID)
					return transitionOkMsg{}
				}
			}
		}
	}
	return m, nil
}

type transitionOkMsg struct{}

// Lipgloss Styles
var (
	// Colors
	accentColor   = lipgloss.Color("#7AA2F7") // Soft Purple-Blue
	activeColor   = lipgloss.Color("#73DACA") // Neon Emerald
	pendingColor  = lipgloss.Color("#E0AF68") // Amber
	staleColor    = lipgloss.Color("#FF9E64") // Coral
	failedColor   = lipgloss.Color("#F7768E") // Soft Red
	subtleColor   = lipgloss.Color("#565F89") // Muted Slate
	bgHeaderColor = lipgloss.Color("#1F2335")

	// Header
	headerStyle = lipgloss.NewStyle().
			Bold(true).
			Foreground(lipgloss.Color("#FFFFFF")).
			Background(bgHeaderColor).
			Padding(0, 1).
			MarginBottom(1)

	// Panels
	leftPanelStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(accentColor).
			Padding(0, 1)

	rightPanelStyle = lipgloss.NewStyle().
			Border(lipgloss.RoundedBorder()).
			BorderForeground(subtleColor).
			Padding(0, 1)

	// Badges
	badgePending = lipgloss.NewStyle().Foreground(pendingColor).Bold(true)
	badgeWorking = lipgloss.NewStyle().Foreground(activeColor).Bold(true)
	badgeStale   = lipgloss.NewStyle().Foreground(staleColor).Bold(true)
	badgeFailed  = lipgloss.NewStyle().Foreground(failedColor).Bold(true)
	badgeDefault = lipgloss.NewStyle().Foreground(subtleColor)

	// Status Bar
	statusBarStyle = lipgloss.NewStyle().
			Foreground(lipgloss.Color("#C0CAF5")).
			Background(bgHeaderColor).
			Padding(0, 1).
			MarginTop(1)

	keyStyle = lipgloss.NewStyle().Foreground(accentColor).Bold(true)
)

func renderBadge(state fsm.State) string {
	switch state {
	case fsm.PENDING:
		return badgePending.Render("[PENDING]")
	case fsm.WORKING, fsm.ISOLATING, fsm.DELEGATING:
		return badgeWorking.Render(fmt.Sprintf("[%s]", state))
	case fsm.STALE:
		return badgeStale.Render("[STALE]")
	case fsm.FAILED, fsm.ORPHAN:
		return badgeFailed.Render(fmt.Sprintf("[%s]", state))
	default:
		return badgeDefault.Render(fmt.Sprintf("[%s]", state))
	}
}

func (m *LoomModel) View() string {
	w := m.Width
	if w <= 0 {
		w = 80
	}
	h := m.Height
	if h <= 0 {
		h = 24
	}

	agentBadge := formatAgentBadge(m.SelectedAgent)
	headerTitle := fmt.Sprintf("🧵 LOOM AI ORCHESTRATOR  │  %s  │  Reactive FSM Telemetry", agentBadge)
	if m.IsBusy {
		if m.IsValidating {
			headerTitle = fmt.Sprintf("🧵 LOOM AI ORCHESTRATOR  │  %s  │  ⏳ VALIDATING & SEALING ISSUE #%s...", agentBadge, m.BusyIssueID)
		} else {
			headerTitle = fmt.Sprintf("🧵 LOOM AI ORCHESTRATOR  │  %s  │  ⏳ AGENT WORKING ON ISSUE #%s...", agentBadge, m.BusyIssueID)
		}
	}
	header := headerStyle.Width(w - 2).Render(headerTitle)

	panelHeight := h - 6
	if panelHeight < 12 {
		panelHeight = 12
	}

	// 1. Build Left Panel (Backlog) Content
	var leftBuilder strings.Builder
	leftBuilder.WriteString(lipgloss.NewStyle().Bold(true).Foreground(accentColor).Render("📋 BACKLOG PIPELINE") + "\n\n")

	if len(m.Issues) == 0 {
		leftBuilder.WriteString(badgeDefault.Render("No issues available.") + "\n")
	} else {
		repoGroups := make(map[string][]*fsm.IssueFSM)
		var repoOrder []string
		for _, iss := range m.Issues {
			r := getRepoName(iss)
			if _, exists := repoGroups[r]; !exists {
				repoOrder = append(repoOrder, r)
			}
			repoGroups[r] = append(repoGroups[r], iss)
		}

		for _, r := range repoOrder {
			groupIssues := repoGroups[r]
			isCollapsed := m.CollapsedRepos[r]
			if isCollapsed {
				headerText := fmt.Sprintf("📁 [▶] %s (%d hidden)", r, len(groupIssues))
				leftBuilder.WriteString(lipgloss.NewStyle().Foreground(lipgloss.Color("#565F89")).Bold(true).Render(headerText) + "\n")
			} else {
				headerText := fmt.Sprintf("📂 [▼] %s", r)
				leftBuilder.WriteString(lipgloss.NewStyle().Foreground(accentColor).Bold(true).Render(headerText) + "\n")
				for _, issue := range groupIssues {
					cursor := "  "
					itemStyle := lipgloss.NewStyle().Foreground(lipgloss.Color("#A9B1D6"))
					if m.SelectedIssue != nil && issue.ID == m.SelectedIssue.ID && getRepoName(issue) == getRepoName(m.SelectedIssue) {
						cursor = "👉"
						itemStyle = itemStyle.Bold(true).Foreground(lipgloss.Color("#FFFFFF"))
					}
					badge := renderBadge(issue.State)
					unresolved := m.Registry.UnresolvedDependencies(issue)
					depTag := ""
					if len(unresolved) > 0 && issue.State == fsm.PENDING {
						depTag = lipgloss.NewStyle().Foreground(lipgloss.Color("#FF9E64")).Bold(true).Render(fmt.Sprintf(" [🔒#%s]", strings.Join(unresolved, ",")))
					}
					titleSnippet := issue.Title
					if titleSnippet == "" {
						titleSnippet = "Issue #" + issue.ID
					} else if len(titleSnippet) > 24 && m.ViewMode == ViewModeSplit {
						titleSnippet = titleSnippet[:21] + "..."
					}
					leftBuilder.WriteString(fmt.Sprintf("  %s %s %s%s\n", cursor, badge, itemStyle.Render("#"+issue.ID+" "+titleSnippet), depTag))
				}
			}
		}
	}

	// 2. Build Right Panel (Inspector) Content
	var rightBuilder strings.Builder
	rightBuilder.WriteString(lipgloss.NewStyle().Bold(true).Foreground(activeColor).Render("🔍 ISSUE TELEMETRY & DETAILS") + "\n\n")

	if m.SelectedIssue == nil {
		rightBuilder.WriteString(badgeDefault.Render("Select an issue from the backlog to inspect state details.") + "\n")
	} else {
		iss := m.SelectedIssue
		unresolved := m.Registry.UnresolvedDependencies(iss)
		if len(unresolved) > 0 {
			warnBanner := lipgloss.NewStyle().
				Background(lipgloss.Color("#F7768E")).
				Foreground(lipgloss.Color("#1A1B26")).
				Bold(true).
				Padding(0, 1).
				Render(fmt.Sprintf("⛔ DEPENDENCY WARNING: Blocked by #%s (must resolve before starting)", strings.Join(unresolved, ", #")))
			rightBuilder.WriteString(warnBanner + "\n\n")
		}

		if iss.State == fsm.SEALING {
			sealBanner := lipgloss.NewStyle().
				Background(lipgloss.Color("#9ECE6A")).
				Foreground(lipgloss.Color("#1A1B26")).
				Bold(true).
				Padding(0, 1).
				Render("✅ SEALED: Validation Passed & Ready for [p] PR or [d] Done")
			rightBuilder.WriteString(sealBanner + "\n\n")
		}

		if m.IsBusy && m.BusyIssueID == iss.ID {
			validatingBanner := lipgloss.NewStyle().
				Background(lipgloss.Color("#E0AF68")).
				Foreground(lipgloss.Color("#1A1B26")).
				Bold(true).
				Padding(0, 1).
				Render("⏳ VALIDATING & SEALING: Executing test suite & Gentle Review Gate...")
			rightBuilder.WriteString(validatingBanner + "\n\n")
		}

		if iss.ReviewSeverity == "BLOCKER" || iss.LastGateDenial != nil {
			denialMsg := ""
			if iss.LastGateDenial != nil {
				denialMsg = fmt.Sprintf(" [%s: %s]", iss.LastGateDenial.Code, iss.LastGateDenial.Reason)
			}
			blockerBanner := lipgloss.NewStyle().
				Background(lipgloss.Color("#F7768E")).
				Foreground(lipgloss.Color("#1A1B26")).
				Bold(true).
				Padding(0, 1).
				Render(fmt.Sprintf("⛔ REVIEW BLOCKER: Gate rejected transition%s", denialMsg))
			rightBuilder.WriteString(blockerBanner + "\n\n")
		}

		titleStr := iss.Title
		if titleStr == "" {
			titleStr = "Issue #" + iss.ID
		}
		rightBuilder.WriteString(fmt.Sprintf("%s %s\n",
			lipgloss.NewStyle().Bold(true).Foreground(accentColor).Render("#"+iss.ID+":"),
			lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#FFFFFF")).Render(titleStr)))

		// Labels Badges
		if len(iss.Labels) > 0 {
			var labelBadges []string
			for _, l := range iss.Labels {
				labelBadges = append(labelBadges, lipgloss.NewStyle().Background(lipgloss.Color("#2AC3DE")).Foreground(lipgloss.Color("#1A1B26")).Padding(0, 1).Bold(true).Render(l))
			}
			rightBuilder.WriteString(fmt.Sprintf("%s %s\n", lipgloss.NewStyle().Bold(true).Render("Labels:"), strings.Join(labelBadges, " ")))
		}

		if iss.UpdatedAt != "" {
			rightBuilder.WriteString(fmt.Sprintf("%s %s\n", lipgloss.NewStyle().Bold(true).Render("Updated:"), lipgloss.NewStyle().Foreground(subtleColor).Render(iss.UpdatedAt)))
		}
		if iss.URL != "" {
			rightBuilder.WriteString(fmt.Sprintf("%s %s\n", lipgloss.NewStyle().Bold(true).Render("URL:"), lipgloss.NewStyle().Foreground(accentColor).Render(iss.URL)))
		}

		rightBuilder.WriteString(fmt.Sprintf("%s %s\n", lipgloss.NewStyle().Bold(true).Render("FSM State:"), renderBadge(iss.State)))

		// Stepper del pipeline: muestra el track feliz con el estado actual
		// resaltado. Para STALE muestra el pipeline con la posición inferida
		// desde ActivePhase y una anotación de pausa. Para FAILED/ORPHAN
		// muestra el branched badge.
		stepperWidth := w/2 - 4
		if stepperWidth < 0 {
			stepperWidth = 0
		}
		rightBuilder.WriteString(renderPipelineStepper(iss.State, iss.ActivePhase, stepperWidth) + "\n")

		if iss.ActivePhase != "" {
			phaseStyle := lipgloss.NewStyle().Background(lipgloss.Color("#7AA2F7")).Foreground(lipgloss.Color("#1A1B26")).Padding(0, 1).Bold(true)
			rightBuilder.WriteString(fmt.Sprintf("%s %s\n", lipgloss.NewStyle().Bold(true).Render("Active Phase:"), phaseStyle.Render(string(iss.ActivePhase))))
		}
		if iss.FixRetryCount > 0 || iss.ActivePhase == fsm.PhaseFix {
			cbColor := lipgloss.Color("#9ECE6A")
			if iss.FixRetryCount == 1 {
				cbColor = lipgloss.Color("#E0AF68")
			} else if iss.FixRetryCount >= fsm.MaxFixRetries {
				cbColor = lipgloss.Color("#F7768E")
			}
			cbBadge := lipgloss.NewStyle().Background(cbColor).Foreground(lipgloss.Color("#1A1B26")).Padding(0, 1).Bold(true).Render(fmt.Sprintf("[%d/%d]", iss.FixRetryCount, fsm.MaxFixRetries))
			rightBuilder.WriteString(fmt.Sprintf("%s %s\n", lipgloss.NewStyle().Bold(true).Render("Fix Retries:"), cbBadge))
		}
		if iss.ReviewSeverity != "" {
			sevColor := lipgloss.Color("#9ECE6A")
			if iss.ReviewSeverity == "BLOCKER" {
				sevColor = lipgloss.Color("#F7768E")
			}
			sevBadge := lipgloss.NewStyle().Background(sevColor).Foreground(lipgloss.Color("#1A1B26")).Padding(0, 1).Bold(true).Render(iss.ReviewSeverity)
			rightBuilder.WriteString(fmt.Sprintf("%s %s\n", lipgloss.NewStyle().Bold(true).Render("Review Severity:"), sevBadge))
		}

		worktreeStr := iss.WorktreePath
		if worktreeStr == "" {
			worktreeStr = "(Not created yet)"
		}
		rightBuilder.WriteString(fmt.Sprintf("%s %s\n", lipgloss.NewStyle().Bold(true).Render("Worktree:"), lipgloss.NewStyle().Foreground(subtleColor).Render(worktreeStr)))

		// Issue Description Body
		rightBuilder.WriteString("\n" + lipgloss.NewStyle().Bold(true).Render("📝 Description:") + "\n")
		if iss.Body != "" {
			bodyLines := strings.Split(strings.TrimSpace(iss.Body), "\n")
			maxLines := 6
			if m.ViewMode == ViewModeInspectorOnly {
				maxLines = 14
			}
			if len(bodyLines) > maxLines {
				bodyLines = append(bodyLines[:maxLines], "...")
			}
			bodySnippet := strings.Join(bodyLines, "\n")
			rightBuilder.WriteString(lipgloss.NewStyle().Foreground(lipgloss.Color("#A9B1D6")).Render(bodySnippet) + "\n")
		} else {
			rightBuilder.WriteString(badgeDefault.Render("(No description provided in GitHub issue)") + "\n")
		}

		// Step-by-Step Action Guidance
		rightBuilder.WriteString("\n" + lipgloss.NewStyle().Bold(true).Render("👉 Step-by-Step Action:") + "\n")
		switch iss.State {
		case fsm.PENDING, fsm.FAILED:
			rightBuilder.WriteString(lipgloss.NewStyle().Foreground(pendingColor).Render("Press [s] to isolate worktree and start working") + "\n")
		case fsm.STALE:
			if iss.WorktreePath != "" {
				rightBuilder.WriteString(lipgloss.NewStyle().Foreground(activeColor).Render("Worktree exists! Press [v] to Validate & Seal finished work, or [s] to restart") + "\n")
			} else {
				rightBuilder.WriteString(lipgloss.NewStyle().Foreground(pendingColor).Render("Press [s] to isolate worktree and start working") + "\n")
			}
		case fsm.WORKING:
			if isDesktopAgent(m.SelectedAgent) {
				rightBuilder.WriteString(lipgloss.NewStyle().Foreground(activeColor).Bold(true).Render(fmt.Sprintf("🖥️ %s Desktop is open on this worktree. Paste prompt with Ctrl+V, then press [v] to Validate & Seal.", strings.ToUpper(m.SelectedAgent))) + "\n")
			} else if m.IsValidating && m.BusyIssueID == iss.ID {
				rightBuilder.WriteString(lipgloss.NewStyle().Foreground(lipgloss.Color("#FF9E64")).Bold(true).Render("⏳ VALIDATING & SEALING: Executing test evidence & governance gate... Please wait.") + "\n")
			} else if m.IsBusy {
				rightBuilder.WriteString(lipgloss.NewStyle().Foreground(lipgloss.Color("#FF9E64")).Bold(true).Render("⏳ AI Agent is actively writing code & running tests... Please wait.") + "\n")
			} else {
				rightBuilder.WriteString(lipgloss.NewStyle().Foreground(activeColor).Render("✅ Agent completed work! Inspect files, then press [v] to Validate & Seal") + "\n")
			}
		case fsm.SEALING:
			rightBuilder.WriteString(lipgloss.NewStyle().Foreground(lipgloss.Color("#9ECE6A")).Bold(true).Render("✅ SEALED: Validation completed! Press [p] for PR or [d] to clean worktree & mark [DONE]") + "\n")
		case fsm.DONE:
			rightBuilder.WriteString(lipgloss.NewStyle().Foreground(accentColor).Render("Issue completed and worktree cleaned successfully.") + "\n")
		case fsm.ORPHAN:
			rightBuilder.WriteString(lipgloss.NewStyle().Foreground(failedColor).Bold(true).Render("⚠️ Worktree folder was locked or orphaned. Press [x] to force-purge.") + "\n")
		default:
			rightBuilder.WriteString(badgeDefault.Render("Manage issue with [s], [v], [d], [x]") + "\n")
		}

		// Live Execution Logs Streaming
		if iss.WorktreePath != "" {
			maxLogLines := 4
			if m.ViewMode == ViewModeInspectorOnly {
				maxLogLines = 10
			}
			recentLogs := ""
			if exec.IsHerdrRunning() && iss != nil {
				recentLogs = exec.RunHerdrAgentRead("loom-"+iss.ID, maxLogLines)
			}
			if recentLogs == "" {
				recentLogs = exec.ReadRecentLogs(iss.WorktreePath, maxLogLines)
			}
			if recentLogs != "" {
				rightBuilder.WriteString("\n" + lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#BB9AF7")).Render("📡 Live Agent Output:") + "\n")
				logBox := lipgloss.NewStyle().
					Foreground(lipgloss.Color("#7AA2F7")).
					Background(lipgloss.Color("#16161E")).
					Padding(0, 1).
					Render(recentLogs)
				rightBuilder.WriteString(logBox + "\n")
			}
		}
	}

	var mainContent string
	switch m.ViewMode {
	case ViewModeBacklogOnly:
		mainContent = leftPanelStyle.
			Width(w - 4).
			Height(panelHeight).
			Render(leftBuilder.String())
	case ViewModeInspectorOnly:
		mainContent = rightPanelStyle.
			Width(w - 4).
			Height(panelHeight).
			Render(rightBuilder.String())
	default: // ViewModeSplit
		leftWidth := int(float64(w) * 0.42)
		if leftWidth < 28 {
			leftWidth = 28
		}
		rightWidth := w - leftWidth - 6
		if rightWidth < 30 {
			rightWidth = 30
		}
		leftPanel := leftPanelStyle.Width(leftWidth).Height(panelHeight).Render(leftBuilder.String())
		rightPanel := rightPanelStyle.Width(rightWidth).Height(panelHeight).Render(rightBuilder.String())
		mainContent = lipgloss.JoinHorizontal(lipgloss.Top, leftPanel, rightPanel)
	}

	// 3. Render Footer / Status Bar
	modeLabel := "Split"
	if m.ViewMode == ViewModeBacklogOnly {
		modeLabel = "Backlog Focus"
	} else if m.ViewMode == ViewModeInspectorOnly {
		modeLabel = "Inspector Focus"
	}

	var footerText string
	if m.ToastMsg != "" {
		footerText = lipgloss.NewStyle().Foreground(lipgloss.Color("#73DACA")).Bold(true).Render(m.ToastMsg) + "  │  " +
			fmt.Sprintf("%s Continue", keyStyle.Render("[Any Key]"))
	} else {
		agentLabel := formatAgentBadge(m.SelectedAgent)
		footerText = fmt.Sprintf("%s Work  │  %s Fold  │  %s Judge  │  %s Focus  │  %s %s  │  %s Valid  │  %s Done  │  %s Open  │  %s PR  │  %s Copy  │  %s Reset  │  %s %s  │  %s Quit",
			keyStyle.Render("[s]"),
			keyStyle.Render("[←/→]"),
			keyStyle.Render("[J]"),
			keyStyle.Render("[f]"),
			keyStyle.Render("[a]"),
			lipgloss.NewStyle().Foreground(lipgloss.Color("#FF9E64")).Bold(true).Render(agentLabel),
			keyStyle.Render("[v]"),
			keyStyle.Render("[d]"),
			keyStyle.Render("[o]"),
			keyStyle.Render("[p]"),
			keyStyle.Render("[y]"),
			keyStyle.Render("[r]"),
			keyStyle.Render("[Tab]"),
			lipgloss.NewStyle().Foreground(activeColor).Bold(true).Render(modeLabel),
			keyStyle.Render("[q]"),
		)
	}
	footer := statusBarStyle.Width(w - 2).Render(footerText)

	return lipgloss.JoinVertical(lipgloss.Left, header, mainContent, footer)
}
