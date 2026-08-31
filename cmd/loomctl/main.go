package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/joho/godotenv"
	loomExec "github.com/mmarcoschambi/loom/internal/exec"
	"github.com/mmarcoschambi/loom/internal/fsm"
	"github.com/mmarcoschambi/loom/internal/github"
	"github.com/mmarcoschambi/loom/internal/judge"
)

type CliResult struct {
	Status       string              `json:"status"`
	ErrorCode    string              `json:"error_code,omitempty"`
	ErrorMessage string              `json:"error_message,omitempty"`
	IssueID      string              `json:"issue_id,omitempty"`
	Data         interface{}         `json:"data,omitempty"`
	Plan         []loomExec.PlanItem `json:"plan,omitempty"`
}

var exitFunc = os.Exit

func outputResult(res CliResult, asJSON bool) {
	if asJSON {
		enc, _ := json.MarshalIndent(res, "", "  ")
		fmt.Println(string(enc))
	} else {
		if res.Status == "ok" {
			fmt.Printf("✅ [%s] Issue #%s: %v\n", res.Status, res.IssueID, res.Data)
		} else {
			fmt.Fprintf(os.Stderr, "❌ [%s] %s: %s\n", res.ErrorCode, res.IssueID, res.ErrorMessage)
		}
	}

	if res.Status != "ok" {
		if res.ErrorCode == "E_USAGE" || res.ErrorCode == "E_INVALID_ARGS" {
			exitFunc(2)
			return
		}
		exitFunc(1)
	}
}

func main() {
	_ = godotenv.Load()

	jsonMode := true
	dryRun := false
	strictMode := false
	directMode := false
	forceMode := false
	stateDir := ""
	lockTimeout := 10 * time.Second
	linesCount := 25
	agentChoice := "opencode"
	judgeMode := ""
	judgeAgentA := ""
	judgeAgentB := ""
	judgeMerge := false

	var positional []string
	for i := 1; i < len(os.Args); i++ {
		arg := os.Args[i]
		if arg == "--json" {
			jsonMode = true
		} else if arg == "--no-json" {
			jsonMode = false
		} else if arg == "--dry-run" {
			dryRun = true
		} else if arg == "--strict" {
			strictMode = true
		} else if arg == "--direct" {
			directMode = true
		} else if arg == "--force" {
			forceMode = true
		} else if strings.HasPrefix(arg, "--lines=") {
			n, _ := strconv.Atoi(strings.TrimPrefix(arg, "--lines="))
			if n > 0 {
				linesCount = n
			}
		} else if arg == "--lines" && i+1 < len(os.Args) {
			i++
			n, _ := strconv.Atoi(os.Args[i])
			if n > 0 {
				linesCount = n
			}
		} else if strings.HasPrefix(arg, "--agent=") {
			agentChoice = strings.TrimPrefix(arg, "--agent=")
		} else if arg == "--agent" && i+1 < len(os.Args) {
			i++
			agentChoice = os.Args[i]
		} else if strings.HasPrefix(arg, "--state-dir=") {
			stateDir = strings.TrimPrefix(arg, "--state-dir=")
		} else if arg == "--state-dir" && i+1 < len(os.Args) {
			i++
			stateDir = os.Args[i]
		} else if strings.HasPrefix(arg, "--lock-timeout=") {
			d, err := time.ParseDuration(strings.TrimPrefix(arg, "--lock-timeout="))
			if err == nil {
				lockTimeout = d
			}
		} else if arg == "--lock-timeout" && i+1 < len(os.Args) {
			i++
			d, err := time.ParseDuration(os.Args[i])
			if err == nil {
				lockTimeout = d
			}
		} else if strings.HasPrefix(arg, "--mode=") {
			judgeMode = strings.TrimPrefix(arg, "--mode=")
		} else if arg == "--mode" && i+1 < len(os.Args) {
			i++
			judgeMode = os.Args[i]
		} else if strings.HasPrefix(arg, "--agent-a=") {
			judgeAgentA = strings.TrimPrefix(arg, "--agent-a=")
		} else if arg == "--agent-a" && i+1 < len(os.Args) {
			i++
			judgeAgentA = os.Args[i]
		} else if strings.HasPrefix(arg, "--agent-b=") {
			judgeAgentB = strings.TrimPrefix(arg, "--agent-b=")
		} else if arg == "--agent-b" && i+1 < len(os.Args) {
			i++
			judgeAgentB = os.Args[i]
		} else if arg == "--merge" {
			judgeMerge = true
		} else if strings.HasPrefix(arg, "-") {
			outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: fmt.Sprintf("Unknown flag: %s", arg)}, jsonMode)
			return
		} else {
			positional = append(positional, arg)
		}
	}

	if len(positional) == 0 {
		printUsage()
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: "No command specified"}, jsonMode)
		return
	}

	cmd := positional[0]
	issueID := ""
	if len(positional) > 1 {
		issueID = positional[1]
	}

	if stateDir == "" {
		homeDir, err := os.UserHomeDir()
		if err != nil {
			outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: err.Error()}, jsonMode)
			return
		}
		stateDir = filepath.Join(homeDir, ".loom", "state")
	}

	reg := fsm.NewFSMRegistry(stateDir)
	reg.LockTimeout = lockTimeout

	if err := reg.HydrateState(); err != nil {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: fmt.Sprintf("Failed to hydrate state: %v", err)}, jsonMode)
		return
	}

	ctx := loomExec.ExecContext{
		Ctx: context.Background(),
	}

	switch cmd {
	case "status":
		handleStatus(reg, issueID, jsonMode)
	case "poll", "fetch", "poll-once":
		handlePoll(reg, jsonMode)
	case "start":
		handleStart(reg, ctx, issueID, agentChoice, directMode, forceMode, dryRun, jsonMode)
	case "plan":
		handlePlan(reg, ctx, issueID, agentChoice, dryRun, jsonMode)
	case "apply":
		handleApply(reg, ctx, issueID, agentChoice, dryRun, jsonMode)
	case "review":
		handleReview(reg, ctx, issueID, agentChoice, dryRun, jsonMode)
	case "fix":
		handleFix(reg, ctx, issueID, agentChoice, dryRun, jsonMode)
	case "validate":
		handleValidate(reg, ctx, issueID, dryRun, jsonMode)
	case "seal":
		handleSeal(reg, ctx, issueID, strictMode, dryRun, jsonMode)
	case "clean":
		handleClean(reg, ctx, issueID, dryRun, jsonMode)
	case "reset":
		handleReset(reg, ctx, issueID, dryRun, jsonMode)
	case "logs":
		handleLogs(reg, issueID, linesCount, jsonMode)
	case "judge":
		handleJudge(reg, ctx, issueID, judgeMode, judgeAgentA, judgeAgentB, judgeMerge, dryRun, jsonMode)
	case "repo":
		handleRepo(reg, positional[1:], jsonMode)
	case "help":
		printUsage()
	default:
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: fmt.Sprintf("Unknown command: %s", cmd)}, jsonMode)
	}
}

func printUsage() {
	fmt.Println(`loomctl - Headless CLI for Loom AI Orchestrator

Usage:
  loomctl <command> [issue_id] [flags]

Commands:
  status   [issue_id]          Query status of all issues or a single issue (read-only)
  poll                         Poll open issues from GitHub and ingest into state.json
  start    <issue_id>          Provision worktree and start agent session (use --direct for fast-path)
  plan     <issue_id>          Start PLAN phase session (Architect, Given/When/Then BDD)
  apply    <issue_id>          Start APPLY phase session (Strict TDD Red -> Green)
  review   <issue_id>          Start REVIEW phase session (Auditor 4 lenses)
  fix      <issue_id>          Start FIX phase session (Circuit Breaker max 2 retries)
  validate <issue_id>          Run pre-flight validation and risk review without mutating state
  seal     <issue_id>          Transition working issue through REVIEWING to SEALING
  clean    <issue_id>          Remove worktree, close Herdr tab, and transition to DONE
  reset    <issue_id>          Revert issue back to PENDING and wipe worktree
  logs     <issue_id>          Read recent execution logs from worktree
  judge    <issue_id>          Advisory phase-judgment gate (freeze + dual blind judges + merge). ADVISORY: never mutates the FSM.

Flags:
  --direct                     Fast-path mode (single direct session, skips phase loop)
  --json                       Output result in JSON format (default true)
  --no-json                    Output human-readable text
  --dry-run                    Simulate execution without modifying OS/disk
  --agent <agy|opencode|zcode|fx> Selected agent engine (default opencode)
  --lines <N>                  Number of log lines to read (default 25)
  --state-dir <path>           Override state storage directory
  --lock-timeout <duration>    Maximum wait time for state lock (default 10s)

Judge flags (only with the judge subcommand):
  --mode <plan|apply|pr>       Phase frontier to judge (required)
  --agent-a <engine>           Engine for judge A (default opencode)
  --agent-b <engine>           Engine for judge B (default agy)
  --merge                      Run J2: collect results, classify, write ledger, print verdict`)
}

func findIssueInStates(states map[string]*fsm.IssueFSM, issueID string) (*fsm.IssueFSM, bool) {
	if iss, ok := states[issueID]; ok {
		return iss, true
	}
	targetSuffix := "#" + issueID
	for k, v := range states {
		if strings.HasSuffix(k, targetSuffix) || v.ID == issueID {
			return v, true
		}
	}
	return nil, false
}

func handleRepo(reg *fsm.FSMRegistry, args []string, asJSON bool) {
	action := "list"
	if len(args) > 0 {
		action = args[0]
	}

	switch action {
	case "list":
		repos := reg.GetTrackedRepos()
		if asJSON {
			outputResult(CliResult{
				Status: "ok",
				Data: map[string]interface{}{
					"tracked_repos": repos,
				},
			}, asJSON)
		} else {
			fmt.Println("Tracked Repositories:")
			for _, r := range repos {
				fmt.Printf("  • %s\n", r)
			}
		}
	case "add":
		if len(args) < 2 {
			outputResult(CliResult{
				Status:       "error",
				ErrorCode:    "E_USAGE",
				ErrorMessage: "Missing repository slug. Usage: loomctl repo add <owner/repo>",
			}, asJSON)
			return
		}
		slug := strings.TrimSpace(args[1])
		parts := strings.Split(slug, "/")
		if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
			outputResult(CliResult{
				Status:       "error",
				ErrorCode:    "E_INVALID_ARGS",
				ErrorMessage: fmt.Sprintf("Invalid repo format: %s. Expected owner/repo", slug),
			}, asJSON)
			return
		}

		added, err := reg.AddTrackedRepo(slug)
		if err != nil {
			outputResult(CliResult{
				Status:       "error",
				ErrorCode:    "E_INTERNAL",
				ErrorMessage: err.Error(),
			}, asJSON)
			return
		}

		msg := fmt.Sprintf("Added repository %s to tracked registry", slug)
		if !added {
			msg = fmt.Sprintf("Repository %s already in tracked registry", slug)
		}
		outputResult(CliResult{
			Status: "ok",
			Data:   msg,
		}, asJSON)
	case "remove", "rm":
		if len(args) < 2 {
			outputResult(CliResult{
				Status:       "error",
				ErrorCode:    "E_USAGE",
				ErrorMessage: "Missing repository slug. Usage: loomctl repo remove <owner/repo>",
			}, asJSON)
			return
		}
		slug := strings.TrimSpace(args[1])
		removed, err := reg.RemoveTrackedRepo(slug)
		if err != nil {
			outputResult(CliResult{
				Status:       "error",
				ErrorCode:    "E_INTERNAL",
				ErrorMessage: err.Error(),
			}, asJSON)
			return
		}
		msg := fmt.Sprintf("Removed repository %s from tracked registry", slug)
		if !removed {
			msg = fmt.Sprintf("Repository %s was not found in tracked registry", slug)
		}
		outputResult(CliResult{
			Status: "ok",
			Data:   msg,
		}, asJSON)
	default:
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    "E_USAGE",
			ErrorMessage: fmt.Sprintf("Unknown repo action: %s. Usage: loomctl repo [list|add|remove] [owner/repo]", action),
		}, asJSON)
	}
}

func handlePoll(reg *fsm.FSMRegistry, asJSON bool) {
	ghToken := os.Getenv("GITHUB_TOKEN")
	trackedRepos := reg.GetTrackedRepos()
	if len(trackedRepos) == 0 {
		ghRepo := os.Getenv("GITHUB_REPO")
		if ghRepo == "" {
			ghRepo = "mmarcoschambi/swing-momentum-v1"
		}
		trackedRepos = []string{ghRepo}
	}

	totalPolled := 0
	allActive := make([]string, 0)
	var pollErrors []string

	for _, repo := range trackedRepos {
		client := github.NewClient(nil, ghToken, repo)
		issues, err := client.FetchIssueDetails(context.Background())
		if err != nil {
			pollErrors = append(pollErrors, fmt.Sprintf("%s: %v", repo, err))
			continue
		}
		totalPolled += len(issues)

		states := reg.GetStates()
		fetchedMap := make(map[string]bool)

		for _, iss := range issues {
			id := strconv.Itoa(iss.Number)
			key := repo + "#" + id
			fetchedMap[key] = true
			existing, exists := states[key]
			if !exists {
				existing, exists = states[id]
			}
			var labelNames []string
			for _, l := range iss.Labels {
				labelNames = append(labelNames, l.Name)
			}

			if !exists {
				newIss := &fsm.IssueFSM{
					ID:        id,
					Repo:      repo,
					Title:     iss.Title,
					Body:      iss.Body,
					URL:       iss.HTMLURL,
					Labels:    labelNames,
					UpdatedAt: iss.UpdatedAt,
					State:     fsm.PENDING,
				}
				_ = reg.Save(newIss)
				allActive = append(allActive, key)
			} else {
				existing.Repo = repo
				existing.Title = iss.Title
				existing.Body = iss.Body
				existing.URL = iss.HTMLURL
				existing.Labels = labelNames
				existing.UpdatedAt = iss.UpdatedAt
				_ = reg.Save(existing)
				allActive = append(allActive, key)
			}
		}

		// Reconcile removed/closed issues for this repo
		for key, existing := range states {
			isThisRepo := (existing.Repo == repo) || strings.HasPrefix(key, repo+"#")
			if !isThisRepo {
				continue
			}
			issueKey := key
			if !strings.Contains(issueKey, "#") {
				issueKey = repo + "#" + existing.ID
			}
			if !fetchedMap[issueKey] {
				if existing.State == fsm.PENDING || existing.State == fsm.DONE {
					_ = reg.Delete(key)
				} else if !existing.GithubClosed {
					existing.GithubClosed = true
					_ = reg.Save(existing)
				}
			}
		}
	}

	if len(pollErrors) > 0 && totalPolled == 0 {
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    "E_NOT_FOUND",
			ErrorMessage: fmt.Sprintf("Failed to poll GitHub: %s", strings.Join(pollErrors, "; ")),
		}, asJSON)
		return
	}

	outputResult(CliResult{
		Status: "ok",
		Data: map[string]interface{}{
			"tracked_repos": trackedRepos,
			"polled_count":  totalPolled,
			"active_issues": allActive,
			"revision":      reg.Revision,
		},
	}, asJSON)
}

func handleStatus(reg *fsm.FSMRegistry, issueID string, asJSON bool) {
	states := reg.GetStates()
	if issueID != "" {
		iss, ok := findIssueInStates(states, issueID)
		if !ok {
			outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: fmt.Sprintf("Issue #%s not found in registry", issueID), IssueID: issueID}, asJSON)
			return
		}
		outputResult(CliResult{
			Status:  "ok",
			IssueID: issueID,
			Data: map[string]interface{}{
				"revision": reg.Revision,
				"issue":    iss,
			},
		}, asJSON)
		return
	}
	outputResult(CliResult{
		Status: "ok",
		Data: map[string]interface{}{
			"revision": reg.Revision,
			"issues":   states,
		},
	}, asJSON)
}

func handleStart(reg *fsm.FSMRegistry, ctx loomExec.ExecContext, issueID string, agentKind string, directMode bool, forceMode bool, dryRun bool, asJSON bool) {
	if issueID == "" {
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: "start command requires an issue_id"}, asJSON)
		return
	}

	states := reg.GetStates()
	iss, ok := findIssueInStates(states, issueID)
	if !ok {
		// Auto-fetch from GitHub on demand before giving up
		ghToken := os.Getenv("GITHUB_TOKEN")
		ghRepo := os.Getenv("GITHUB_REPO")
		if ghRepo == "" {
			ghRepo = "mmarcoschambi/swing-momentum-v1"
		}
		client := github.NewClient(nil, ghToken, ghRepo)
		issues, err := client.FetchIssueDetails(ctx.Ctx)
		if err == nil {
			for _, item := range issues {
				if strconv.Itoa(item.Number) == issueID {
					var labelNames []string
					for _, l := range item.Labels {
						labelNames = append(labelNames, l.Name)
					}
					iss = &fsm.IssueFSM{
						ID:        issueID,
						Title:     item.Title,
						Body:      item.Body,
						URL:       item.HTMLURL,
						Labels:    labelNames,
						UpdatedAt: item.UpdatedAt,
						State:     fsm.PENDING,
					}
					_ = reg.Save(iss)
					ok = true
					break
				}
			}
		}
	}

	if !ok {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: fmt.Sprintf("Issue #%s does not exist in backlog or remote repository", issueID), IssueID: issueID}, asJSON)
		return
	}

	// Dependency check: block if prerequisites are not yet completed
	unresolved := reg.UnresolvedDependencies(iss)
	if len(unresolved) > 0 && !forceMode {
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    "E_BLOCKED_DEPENDENCY",
			ErrorMessage: fmt.Sprintf("Cannot start issue #%s: blocked by unresolved issue(s) #%s. Merge/close dependencies first or use --force to override.", issueID, strings.Join(unresolved, ", #")),
			IssueID:      issueID,
		}, asJSON)
		return
	}

	// Validate allowed initial states
	if iss.State != fsm.PENDING && iss.State != fsm.STALE && iss.State != fsm.FAILED && iss.State != fsm.ORPHAN {
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    "E_INVALID_TRANSITION",
			ErrorMessage: fmt.Sprintf("Cannot start issue in state %s (must be PENDING, STALE, FAILED, or ORPHAN)", iss.State),
			IssueID:      issueID,
		}, asJSON)
		return
	}

	homeDir, _ := os.UserHomeDir()
	worktreePath := filepath.Join(homeDir, ".loom", "worktrees", issueID)
	if iss.Repo != "" {
		sanitizedRepo := strings.ReplaceAll(iss.Repo, "/", "__")
		worktreePath = filepath.Join(homeDir, ".loom", "worktrees", sanitizedRepo, issueID)
	}

	if dryRun {
		plan := []loomExec.PlanItem{
			{Action: "mkdir", Target: worktreePath, Detail: "Create worktree folder"},
			{Action: "git worktree add", Target: worktreePath, Detail: fmt.Sprintf("branch issue-%s", issueID)},
			{Action: "write_scaffold", Target: filepath.Join(worktreePath, "tasks.md"), Detail: "Write OpenSpec / tasks.md suite"},
			{Action: "herdr agent start", Target: "loom-" + issueID, Detail: fmt.Sprintf("Agent %s in new tab", agentKind)},
		}
		outputResult(CliResult{Status: "ok", IssueID: issueID, Plan: plan, Data: "Dry-run start plan validated"}, asJSON)
		return
	}

	if !reg.TryAcquire(issueID) {
		outputResult(CliResult{Status: "error", ErrorCode: "E_STATE_CONFLICT", ErrorMessage: "Concurrency limit reached (3 active agents). Release an issue first.", IssueID: issueID}, asJSON)
		return
	}

	if err := reg.TransitionTo(iss, fsm.ISOLATING, "loomctl start"); err != nil {
		reg.Release(issueID)
		outputResult(CliResult{Status: "error", ErrorCode: "E_INVALID_TRANSITION", ErrorMessage: err.Error(), IssueID: issueID}, asJSON)
		return
	}

	ctx.Cwd = worktreePath
	_ = os.MkdirAll(worktreePath, 0755)

	if err := loomExec.RunOrcaCreate(ctx, issueID); err != nil {
		_ = reg.TransitionTo(iss, fsm.FAILED, err.Error())
		reg.Release(issueID)
		errCode := "E_WORKTREE_LOCKED"
		if strings.Contains(err.Error(), "path traversal") {
			errCode = "E_PATH_TRAVERSAL"
		}
		outputResult(CliResult{Status: "error", ErrorCode: errCode, ErrorMessage: err.Error(), IssueID: issueID}, asJSON)
		return
	}

	iss.WorktreePath = worktreePath
	_ = reg.Save(iss)

	_ = reg.TransitionTo(iss, fsm.DELEGATING, "Worktree created")

	payload := loomExec.IssuePayload{
		Title:  iss.Title,
		Body:   iss.Body,
		URL:    iss.URL,
		Labels: iss.Labels,
	}
	_ = loomExec.WriteOpenSpecScaffold(ctx, issueID, payload)

	_ = reg.TransitionTo(iss, fsm.WORKING, "Launching agent session")

	iss.DirectMode = directMode
	var promptText string
	if directMode {
		iss.ActivePhase = fsm.PhaseDirect
		promptText = loomExec.BuildDirectPrompt(issueID, payload, worktreePath)
	} else {
		iss.ActivePhase = fsm.PhasePlan
		promptText = loomExec.BuildPlanPrompt(issueID, payload)
	}
	_ = reg.Save(iss)

	if loomExec.IsHerdrRunning() {
		tabID, paneID, err := loomExec.RunHerdrTabCreate(ctx, "issue-"+issueID)
		if err == nil {
			iss.AgentTabID = tabID
			iss.AgentPaneID = paneID
			_ = reg.Save(iss)
			_ = loomExec.RunHerdrAgentStart(ctx, "loom-"+issueID, agentKind, paneID, promptText)
		}
	}

	outputResult(CliResult{
		Status:  "ok",
		IssueID: issueID,
		Data: map[string]interface{}{
			"state":        iss.State,
			"active_phase": iss.ActivePhase,
			"direct_mode":  iss.DirectMode,
			"worktree":     iss.WorktreePath,
			"agent":        agentKind,
			"agent_tab_id": iss.AgentTabID,
		},
	}, asJSON)
}

func handlePlan(reg *fsm.FSMRegistry, ctx loomExec.ExecContext, issueID string, agentKind string, dryRun bool, asJSON bool) {
	if issueID == "" {
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: "plan command requires an issue_id"}, asJSON)
		return
	}
	states := reg.GetStates()
	iss, ok := findIssueInStates(states, issueID)
	if !ok {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: fmt.Sprintf("Issue #%s not found", issueID), IssueID: issueID}, asJSON)
		return
	}
	if iss.State != fsm.WORKING {
		outputResult(CliResult{Status: "error", ErrorCode: "E_INVALID_STATE", ErrorMessage: fmt.Sprintf("cannot plan issue in state %s (must be WORKING)", iss.State), IssueID: issueID}, asJSON)
		return
	}

	iss.ActivePhase = fsm.PhasePlan
	_ = reg.Save(iss)

	payload := loomExec.IssuePayload{Title: iss.Title, Body: iss.Body, URL: iss.URL, Labels: iss.Labels}
	promptText := loomExec.BuildPlanPrompt(issueID, payload)

	if !dryRun && loomExec.IsHerdrRunning() {
		ctx.Cwd = iss.WorktreePath
		tabID, paneID, err := loomExec.RunHerdrTabCreate(ctx, "plan-"+issueID)
		if err == nil {
			iss.AgentTabID = tabID
			iss.AgentPaneID = paneID
			_ = reg.Save(iss)
			_ = loomExec.RunHerdrAgentStart(ctx, "plan-"+issueID, agentKind, paneID, promptText)
		}
	}

	outputResult(CliResult{
		Status:  "ok",
		IssueID: issueID,
		Data: map[string]interface{}{
			"active_phase": iss.ActivePhase,
			"state":        iss.State,
		},
	}, asJSON)
}

func handleApply(reg *fsm.FSMRegistry, ctx loomExec.ExecContext, issueID string, agentKind string, dryRun bool, asJSON bool) {
	if issueID == "" {
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: "apply command requires an issue_id"}, asJSON)
		return
	}
	states := reg.GetStates()
	iss, ok := findIssueInStates(states, issueID)
	if !ok {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: fmt.Sprintf("Issue #%s not found", issueID), IssueID: issueID}, asJSON)
		return
	}
	if iss.State != fsm.WORKING {
		outputResult(CliResult{Status: "error", ErrorCode: "E_INVALID_STATE", ErrorMessage: fmt.Sprintf("cannot apply issue in state %s (must be WORKING)", iss.State), IssueID: issueID}, asJSON)
		return
	}

	iss.ActivePhase = fsm.PhaseApply
	_ = reg.Save(iss)

	payload := loomExec.IssuePayload{Title: iss.Title, Body: iss.Body, URL: iss.URL, Labels: iss.Labels}
	promptText := loomExec.BuildApplyPrompt(issueID, payload, iss.WorktreePath)

	if !dryRun && loomExec.IsHerdrRunning() {
		ctx.Cwd = iss.WorktreePath
		tabID, paneID, err := loomExec.RunHerdrTabCreate(ctx, "apply-"+issueID)
		if err == nil {
			iss.AgentTabID = tabID
			iss.AgentPaneID = paneID
			_ = reg.Save(iss)
			_ = loomExec.RunHerdrAgentStart(ctx, "apply-"+issueID, agentKind, paneID, promptText)
		}
	}

	outputResult(CliResult{
		Status:  "ok",
		IssueID: issueID,
		Data: map[string]interface{}{
			"active_phase": iss.ActivePhase,
			"state":        iss.State,
		},
	}, asJSON)
}

func handleReview(reg *fsm.FSMRegistry, ctx loomExec.ExecContext, issueID string, agentKind string, dryRun bool, asJSON bool) {
	if issueID == "" {
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: "review command requires an issue_id"}, asJSON)
		return
	}
	states := reg.GetStates()
	iss, ok := findIssueInStates(states, issueID)
	if !ok {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: fmt.Sprintf("Issue #%s not found", issueID), IssueID: issueID}, asJSON)
		return
	}
	if iss.State != fsm.WORKING {
		outputResult(CliResult{Status: "error", ErrorCode: "E_INVALID_STATE", ErrorMessage: fmt.Sprintf("cannot review issue in state %s (must be WORKING)", iss.State), IssueID: issueID}, asJSON)
		return
	}

	if dryRun {
		plan := []loomExec.PlanItem{
			{Action: "stage", Target: iss.WorktreePath, Detail: "Run git add -A -- :!review.log"},
			{Action: "pytest_evidence", Target: iss.WorktreePath, Detail: "Run pytest evidence via ResolvePythonPath"},
			{Action: "gentle_review", Target: iss.WorktreePath, Detail: "Run gentle-ai review validate --gate pre-pr"},
		}
		outputResult(CliResult{Status: "ok", IssueID: issueID, Plan: plan, Data: "Dry-run review plan validated"}, asJSON)
		return
	}

	iss.ActivePhase = fsm.PhaseReview
	_ = reg.Save(iss)

	reviewExecCtx := ctx
	reviewExecCtx.Cwd = iss.WorktreePath

	// 1. Staging limpio (excluye review.log)
	_ = loomExec.RunGitStageAll(reviewExecCtx)

	// 2. Evidencia ejecutable [JD-4]: -m pytest con el intérprete resuelto por
	// discovery. Fail-closed: sin intérprete o con tests rojos no se procede al gate.
	if evidenceErr := loomExec.RunPytestEvidence(reviewExecCtx); evidenceErr != nil {
		iss.ReviewSeverity = "BLOCKER"
		iss.ActivePhase = fsm.PhaseFix
		_ = reg.Save(iss)
		errCode := "E_EVIDENCE_FAILED"
		if errors.Is(evidenceErr, loomExec.ErrPythonEnvMissing) {
			errCode = "E_PYTHON_ENV_MISSING"
		}
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    errCode,
			ErrorMessage: fmt.Sprintf("Executable evidence (pytest) failed: %v", evidenceErr),
			IssueID:      issueID,
		}, asJSON)
		return
	}

	// 3. Gate estricto fail-closed
	gateRes, gateErr := loomExec.RunGentleReviewMode(reviewExecCtx)
	iss.ReviewSeverity = loomExec.DeriveReviewSeverity(gateRes)
	// Per the gentle-ai review-integration contract, delivery "disabled/unmanaged"
	// is a pass-through to ordinary repository policy, not a blocked gate.
	// Skip the fail-closed path so administrative operations (seal/clean) work
	// when the kill switch is off.
	if gateErr != nil || (!gateRes.Allowed && gateRes.Delivery != "disabled/unmanaged") {
		// JD-3: un rechazo descansa en WORKING con ActivePhase=FIX.
		iss.ActivePhase = fsm.PhaseFix
		iss.RecordGateDenial(loomExec.GateDenialInfo(gateRes))
		_ = reg.Save(iss)
		errCode := "E_REVIEW_FAILED"
		if errors.Is(gateErr, loomExec.ErrGentleAINotInstalled) {
			errCode = "E_GENTLE_AI_MISSING"
		}
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    errCode,
			ErrorMessage: fmt.Sprintf("Governance review gate not satisfied: %v", gateErr),
			IssueID:      issueID,
			Data:         gateRes,
		}, asJSON)
		return
	}

	_ = reg.Save(iss)

	outputResult(CliResult{
		Status:  "ok",
		IssueID: issueID,
		Data: map[string]interface{}{
			"active_phase":    iss.ActivePhase,
			"review_severity": iss.ReviewSeverity,
			"gate_result":     gateRes,
		},
	}, asJSON)
}

func handleFix(reg *fsm.FSMRegistry, ctx loomExec.ExecContext, issueID string, agentKind string, dryRun bool, asJSON bool) {
	if issueID == "" {
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: "fix command requires an issue_id"}, asJSON)
		return
	}
	states := reg.GetStates()
	iss, ok := findIssueInStates(states, issueID)
	if !ok {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: fmt.Sprintf("Issue #%s not found", issueID), IssueID: issueID}, asJSON)
		return
	}
	if iss.State != fsm.WORKING {
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    "E_INVALID_STATE",
			ErrorMessage: fmt.Sprintf("cannot fix issue in state %s (must be WORKING)", iss.State),
			IssueID:      issueID,
		}, asJSON)
		return
	}

	if !iss.CanRetryFix() {
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    "E_CIRCUIT_BREAKER",
			ErrorMessage: "Circuit Breaker Tripped: 2 failed review cycles. Human intervention required.",
			IssueID:      issueID,
		}, asJSON)
		return
	}

	iss.IncrementFixRetry()
	iss.ActivePhase = fsm.PhaseFix
	_ = reg.Save(iss)

	payload := loomExec.IssuePayload{Title: iss.Title, Body: iss.Body, URL: iss.URL, Labels: iss.Labels}

	// Inyección quirúrgica: el denial persistido del último rechazo entra al
	// prompt de FIX con su código exacto y el reintento real.
	var gateForResult []loomExec.GentleGateResult
	if iss.LastGateDenial != nil {
		gateForResult = append(gateForResult, loomExec.GateResultFromDenial(
			iss.LastGateDenial.Code, iss.LastGateDenial.Result, iss.LastGateDenial.Reason))
	}
	promptText := loomExec.BuildFixPrompt(issueID, payload, iss.WorktreePath, iss.FixRetryCount, gateForResult...)

	if !dryRun && loomExec.IsHerdrRunning() {
		ctx.Cwd = iss.WorktreePath
		tabID, paneID, err := loomExec.RunHerdrTabCreate(ctx, "fix-"+issueID)
		if err == nil {
			iss.AgentTabID = tabID
			iss.AgentPaneID = paneID
			_ = reg.Save(iss)
			_ = loomExec.RunHerdrAgentStart(ctx, "fix-"+issueID, agentKind, paneID, promptText)
		}
	}

	outputResult(CliResult{
		Status:  "ok",
		IssueID: issueID,
		Data: map[string]interface{}{
			"active_phase":    iss.ActivePhase,
			"fix_retry_count": iss.FixRetryCount,
		},
	}, asJSON)
}

func handleValidate(reg *fsm.FSMRegistry, ctx loomExec.ExecContext, issueID string, dryRun bool, asJSON bool) {
	if issueID == "" {
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: "validate command requires an issue_id"}, asJSON)
		return
	}

	states := reg.GetStates()
	iss, ok := findIssueInStates(states, issueID)
	if !ok {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: fmt.Sprintf("Issue #%s not found", issueID), IssueID: issueID}, asJSON)
		return
	}

	if iss.State != fsm.WORKING && iss.State != fsm.STALE && iss.State != fsm.REVIEWING && iss.State != fsm.SEALING {
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    "E_INVALID_TRANSITION",
			ErrorMessage: fmt.Sprintf("Cannot validate issue in state %s (must be WORKING, STALE, REVIEWING, or SEALING)", iss.State),
			IssueID:      issueID,
		}, asJSON)
		return
	}

	if dryRun {
		plan := []loomExec.PlanItem{
			{Action: "check_worktree", Target: iss.WorktreePath, Detail: "Validate directory existence and modified files"},
			{Action: "gentle_review", Target: iss.WorktreePath, Detail: "Run gentle-ai review validate --gate pre-pr"},
		}
		outputResult(CliResult{Status: "ok", IssueID: issueID, Plan: plan, Data: "Pre-conditions validated"}, asJSON)
		return
	}

	// Check gentle-ai availability
	if _, lookErr := exec.LookPath("gentle-ai"); lookErr != nil {
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    "E_GENTLE_AI_MISSING",
			ErrorMessage: "gentle-ai binary not found in PATH: review cannot run",
			IssueID:      issueID,
		}, asJSON)
		return
	}

	validateCtx, validateCancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer validateCancel()
	validateExecCtx := ctx
	validateExecCtx.Ctx = validateCtx
	validateExecCtx.Cwd = iss.WorktreePath

	gateRes, err := loomExec.RunGentleReviewMode(validateExecCtx)

	if err != nil || !gateRes.Allowed {
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    "E_REVIEW_FAILED",
			ErrorMessage: fmt.Sprintf("Review validation failed: %v", err),
			IssueID:      issueID,
			Data:         gateRes,
		}, asJSON)
		return
	}

	outputResult(CliResult{Status: "ok", IssueID: issueID, Data: "Review passed cleanly"}, asJSON)
}

func handleSeal(reg *fsm.FSMRegistry, ctx loomExec.ExecContext, issueID string, strict bool, dryRun bool, asJSON bool) {
	if issueID == "" {
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: "seal command requires an issue_id"}, asJSON)
		return
	}

	states := reg.GetStates()
	iss, ok := findIssueInStates(states, issueID)
	if !ok {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: fmt.Sprintf("Issue #%s not found", issueID), IssueID: issueID}, asJSON)
		return
	}

	if iss.State != fsm.WORKING && iss.State != fsm.STALE && iss.State != fsm.REVIEWING {
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    "E_INVALID_TRANSITION",
			ErrorMessage: fmt.Sprintf("Cannot seal issue in state %s (must be WORKING, STALE, or REVIEWING)", iss.State),
			IssueID:      issueID,
		}, asJSON)
		return
	}

	if dryRun {
		plan := []loomExec.PlanItem{
			{Action: "transition", Target: issueID, Detail: "WORKING -> REVIEWING -> SEALING"},
		}
		outputResult(CliResult{Status: "ok", IssueID: issueID, Plan: plan, Data: "Dry-run seal plan validated"}, asJSON)
		return
	}

	reviewCtx, reviewCancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer reviewCancel()
	reviewExecCtx := ctx
	reviewExecCtx.Ctx = reviewCtx
	reviewExecCtx.Cwd = iss.WorktreePath

	gateRes, err := loomExec.RunGentleReviewMode(reviewExecCtx)
	iss.ReviewSeverity = loomExec.DeriveReviewSeverity(gateRes)
	// Per the gentle-ai review-integration contract, delivery "disabled/unmanaged"
	// is a pass-through to ordinary repository policy, not a blocked gate.
	// Skip the fail-closed path so administrative operations (seal/clean) work
	// when the kill switch is off.
	if err != nil || (!gateRes.Allowed && gateRes.Delivery != "disabled/unmanaged") {
		// JD-3: un rechazo descansa en WORKING con ActivePhase=FIX; se persiste
		// el denial para la inyección quirúrgica en el prompt de FIX.
		iss.ActivePhase = fsm.PhaseFix
		iss.RecordGateDenial(loomExec.GateDenialInfo(gateRes))
		_ = reg.Save(iss)
		// E_GENTLE_AI_MISSING queda reservado para el binario ausente; un
		// rechazo legítimo del gate es E_REVIEW_FAILED (contrato de handleValidate).
		errCode := "E_REVIEW_FAILED"
		errMsg := fmt.Sprintf("Governance review gate not satisfied: %v", err)
		if errors.Is(err, loomExec.ErrGentleAINotInstalled) {
			errCode = "E_GENTLE_AI_MISSING"
			errMsg = "gentle-ai binary not found in PATH: review cannot run"
		}
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    errCode,
			ErrorMessage: errMsg,
			IssueID:      issueID,
			Data:         gateRes,
		}, asJSON)
		return
	}

	if iss.State != fsm.REVIEWING {
		if err := reg.TransitionTo(iss, fsm.REVIEWING, "Gate approved"); err != nil {
			outputResult(CliResult{Status: "error", ErrorCode: "E_INVALID_TRANSITION", ErrorMessage: err.Error(), IssueID: issueID}, asJSON)
			return
		}
	}

	if err := reg.TransitionTo(iss, fsm.SEALING, "Sealed via loomctl"); err != nil {
		outputResult(CliResult{Status: "error", ErrorCode: "E_INVALID_TRANSITION", ErrorMessage: err.Error(), IssueID: issueID}, asJSON)
		return
	}

	_ = reg.Save(iss)
	outputResult(CliResult{Status: "ok", IssueID: issueID, Data: iss}, asJSON)
}

func handleClean(reg *fsm.FSMRegistry, ctx loomExec.ExecContext, issueID string, dryRun bool, asJSON bool) {
	if issueID == "" {
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: "clean command requires an issue_id"}, asJSON)
		return
	}

	states := reg.GetStates()
	iss, ok := findIssueInStates(states, issueID)
	if !ok {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: fmt.Sprintf("Issue #%s not found", issueID), IssueID: issueID}, asJSON)
		return
	}

	if iss.State != fsm.SEALING && iss.State != fsm.ORPHAN {
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    "E_INVALID_TRANSITION",
			ErrorMessage: fmt.Sprintf("Cannot clean issue in state %s (must be in SEALING or ORPHAN)", iss.State),
			IssueID:      issueID,
		}, asJSON)
		return
	}

	if dryRun {
		plan := []loomExec.PlanItem{
			{Action: "close_tab", Target: iss.AgentTabID, Detail: "Close Herdr agent tab"},
			{Action: "remove_worktree", Target: iss.WorktreePath, Detail: "Purge worktree directory"},
			{Action: "transition", Target: issueID, Detail: "SEALING -> CLEANING -> DONE"},
		}
		outputResult(CliResult{Status: "ok", IssueID: issueID, Plan: plan, Data: "Dry-run clean plan validated"}, asJSON)
		return
	}

	if iss.AgentTabID != "" {
		_ = loomExec.RunHerdrTabClose(iss.AgentTabID)
		iss.AgentTabID = ""
	}

	if err := reg.TransitionTo(iss, fsm.CLEANING, "loomctl clean"); err != nil {
		outputResult(CliResult{Status: "error", ErrorCode: "E_INVALID_TRANSITION", ErrorMessage: err.Error(), IssueID: issueID}, asJSON)
		return
	}

	cleanCtx, cleanCancel := context.WithTimeout(context.Background(), 45*time.Second)
	defer cleanCancel()
	cleanExecCtx := ctx
	cleanExecCtx.Ctx = cleanCtx
	cleanExecCtx.Cwd = iss.WorktreePath

	removeErr := loomExec.RunOrcaRemove(cleanExecCtx)
	reg.Release(issueID)

	if removeErr != nil {
		_ = reg.TransitionTo(iss, fsm.ORPHAN, "Worktree removal failed: "+removeErr.Error())
		_ = reg.Save(iss)
		outputResult(CliResult{
			Status:       "error",
			ErrorCode:    "E_WORKTREE_LOCKED",
			ErrorMessage: removeErr.Error(),
			IssueID:      issueID,
			Data:         iss,
		}, asJSON)
		return
	}

	if err := reg.TransitionTo(iss, fsm.DONE, "Cleaned via loomctl"); err != nil {
		outputResult(CliResult{Status: "error", ErrorCode: "E_INVALID_TRANSITION", ErrorMessage: err.Error(), IssueID: issueID}, asJSON)
		return
	}

	_ = reg.Save(iss)
	outputResult(CliResult{Status: "ok", IssueID: issueID, Data: iss}, asJSON)
}

func handleReset(reg *fsm.FSMRegistry, ctx loomExec.ExecContext, issueID string, dryRun bool, asJSON bool) {
	if issueID == "" {
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: "reset command requires an issue_id"}, asJSON)
		return
	}

	states := reg.GetStates()
	iss, ok := findIssueInStates(states, issueID)
	if !ok {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: fmt.Sprintf("Issue #%s not found", issueID), IssueID: issueID}, asJSON)
		return
	}

	if dryRun {
		plan := []loomExec.PlanItem{
			{Action: "close_tab", Target: iss.AgentTabID, Detail: "Close Herdr agent tab"},
			{Action: "remove_worktree", Target: iss.WorktreePath, Detail: "Purge worktree directory"},
			{Action: "reset_fsm", Target: issueID, Detail: "Revert state to PENDING and release slot"},
		}
		outputResult(CliResult{Status: "ok", IssueID: issueID, Plan: plan, Data: "Dry-run reset plan validated"}, asJSON)
		return
	}

	if iss.AgentTabID != "" {
		_ = loomExec.RunHerdrTabClose(iss.AgentTabID)
		iss.AgentTabID = ""
	}

	if iss.WorktreePath != "" {
		ctx.Cwd = iss.WorktreePath
		_ = loomExec.RunOrcaRemove(ctx)
	}

	reg.Release(issueID)
	_ = reg.ResetIssue(iss)

	outputResult(CliResult{Status: "ok", IssueID: issueID, Data: iss}, asJSON)
}

func handleLogs(reg *fsm.FSMRegistry, issueID string, lines int, asJSON bool) {
	if issueID == "" {
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: "logs command requires an issue_id"}, asJSON)
		return
	}

	states := reg.GetStates()
	iss, ok := findIssueInStates(states, issueID)
	if !ok {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: fmt.Sprintf("Issue #%s not found", issueID), IssueID: issueID}, asJSON)
		return
	}

	recentLogs := ""
	if loomExec.IsHerdrRunning() {
		recentLogs = loomExec.RunHerdrAgentRead("loom-"+issueID, lines)
	}
	if recentLogs == "" && iss.WorktreePath != "" {
		recentLogs = loomExec.ReadRecentLogs(iss.WorktreePath, lines)
	}

	outputResult(CliResult{
		Status:  "ok",
		IssueID: issueID,
		Data: map[string]interface{}{
			"logs":  recentLogs,
			"lines": strconv.Itoa(lines),
		},
	}, asJSON)
}

// handleJudge es el gate advisory de juicio de fases. ADVISORY por diseño:
// nunca muta el FSM, nunca llama a TransitionTo, nunca escribe state.json.
// Subcomando J1 (sin --merge): freeze + lanzamiento dual de jueces.
// Subcomando J2 (con --merge): recoge result-A.md y result-B.md, ejecuta el
// merge mecánico centralizado y emite el veredicto del contrato.
func handleJudge(reg *fsm.FSMRegistry, ctx loomExec.ExecContext, issueID, modeStr, agentA, agentB string, mergeMode, dryRun, asJSON bool) {
	if issueID == "" {
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: "judge command requires an issue_id"}, asJSON)
		return
	}
	if modeStr == "" {
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: "judge command requires --mode <plan|apply|pr>"}, asJSON)
		return
	}
	mode := judge.Mode(strings.ToLower(modeStr))
	if mode != judge.ModePlan && mode != judge.ModeApply && mode != judge.ModePR {
		outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: fmt.Sprintf("invalid --mode %q (must be plan|apply|pr)", modeStr)}, asJSON)
		return
	}

	states := reg.GetStates()
	iss, ok := findIssueInStates(states, issueID)
	if !ok {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NOT_FOUND", ErrorMessage: fmt.Sprintf("Issue #%s not found", issueID), IssueID: issueID}, asJSON)
		return
	}
	if iss.WorktreePath == "" {
		outputResult(CliResult{Status: "error", ErrorCode: "E_INVALID_STATE", ErrorMessage: fmt.Sprintf("Issue #%s has no worktree; cannot judge", issueID), IssueID: issueID}, asJSON)
		return
	}

	// Precondición de estado: WORKING para plan/apply; WORKING o SEALING para pr.
	if mode == judge.ModePR {
		if iss.State != fsm.WORKING && iss.State != fsm.SEALING {
			outputResult(CliResult{Status: "error", ErrorCode: "E_INVALID_STATE", ErrorMessage: fmt.Sprintf("cannot judge PR phase in state %s (must be WORKING or SEALING)", iss.State), IssueID: issueID}, asJSON)
			return
		}
	} else {
		if iss.State != fsm.WORKING {
			outputResult(CliResult{Status: "error", ErrorCode: "E_INVALID_STATE", ErrorMessage: fmt.Sprintf("cannot judge %s phase in state %s (must be WORKING)", mode, iss.State), IssueID: issueID}, asJSON)
			return
		}
	}

	if !mergeMode {
		// ----- J1: freeze + dual launch -----
		paths, err := judge.ResolveSkillsPaths(iss.WorktreePath, mode)
		if err != nil {
			outputResult(CliResult{Status: "error", ErrorCode: "E_SKILL_MISSING", ErrorMessage: err.Error(), IssueID: issueID}, asJSON)
			return
		}

		fr, err := judge.Freeze(mode, iss)
		if err != nil {
			code := "E_NO_FREEZE"
			if errors.Is(err, judge.ErrTargetMutated) {
				code = "E_TARGET_MUTATED"
			}
			outputResult(CliResult{Status: "error", ErrorCode: code, ErrorMessage: err.Error(), IssueID: issueID}, asJSON)
			return
		}

		if agentA == "" {
			agentA = "opencode"
		}
		if agentB == "" {
			agentB = "agy"
		}

		// Validar motores antes de tocar Herdr.
		for _, e := range []string{agentA, agentB} {
			if !judge.EngineValid(e) {
				outputResult(CliResult{Status: "error", ErrorCode: "E_USAGE", ErrorMessage: fmt.Sprintf("invalid engine %q; allowed: %v", e, judge.ValidEngines), IssueID: issueID}, asJSON)
				return
			}
		}

		if dryRun {
			plan := []loomExec.PlanItem{
				{Action: "freeze_target", Target: fr.Path, Detail: fmt.Sprintf("sha256:%s round:%d", shortHash(fr.Hash), fr.Round)},
				{Action: "create_tab", Target: "judge-a-" + issueID, Detail: fmt.Sprintf("engine:%s prompt:prompt-A.md", agentA)},
				{Action: "create_tab", Target: "judge-b-" + issueID, Detail: fmt.Sprintf("engine:%s prompt:prompt-B.md", agentB)},
				{Action: "advisory_note", Target: "[next key] (no FSM mutation)", Detail: "manual press after merge"},
			}
			outputResult(CliResult{Status: "ok", IssueID: issueID, Plan: plan, Data: map[string]interface{}{
				"mode":     string(mode),
				"frozen":   fr.Path,
				"hash":     fr.Hash,
				"round":    fr.Round,
				"agent_a":  agentA,
				"agent_b":  agentB,
				"warning":  judge.SameEngineWarn(agentA, agentB),
			}}, asJSON)
			return
		}

		launch, err := judge.LaunchDualTabs(iss, mode, fr, paths, agentA, agentB)
		if err != nil {
			code := "E_HERDR_MISSING"
			if errors.Is(err, judge.ErrInvalidEngine) {
				code = "E_USAGE"
			}
			outputResult(CliResult{Status: "error", ErrorCode: code, ErrorMessage: err.Error(), IssueID: issueID}, asJSON)
			return
		}

		outputResult(CliResult{
			Status:  "ok",
			IssueID: issueID,
			Data: map[string]interface{}{
				"phase":   "J1",
				"mode":    string(mode),
				"frozen":  launch.Path,
				"hash":    launch.Hash,
				"round":   launch.Round,
				"tab_a":   launch.TabA,
				"tab_b":   launch.TabB,
				"agent_a": launch.EngineA,
				"agent_b": launch.EngineB,
				"warning": launch.Warning,
				"next":    "loomctl judge " + issueID + " --merge (after both judges finish)",
			},
		}, asJSON)
		return
	}

	// ----- J2: merge -----
	if err := judge.LoadResultsPending(iss.WorktreePath); err != nil {
		outputResult(CliResult{Status: "error", ErrorCode: "E_RESULTS_PENDING", ErrorMessage: err.Error(), IssueID: issueID}, asJSON)
		return
	}

	// Encontrar la ronda más reciente congelada para verificar mutación.
	latestRound := judge.LatestRound(filepath.Join(iss.WorktreePath, "judgment"), string(mode))
	if latestRound < 1 {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NO_FREEZE", ErrorMessage: "no frozen rounds found; run `loomctl judge` first (no --merge)"}, asJSON)
		return
	}
	if err := judge.VerifyUntouched(mode, iss, latestRound); err != nil {
		outputResult(CliResult{Status: "error", ErrorCode: "E_TARGET_MUTATED", ErrorMessage: err.Error(), IssueID: issueID}, asJSON)
		return
	}

	aPath, bPath := judge.ResultFilePaths(iss.WorktreePath)
	ra, err := judge.LoadJudgeResult(aPath)
	if err != nil {
		outputResult(CliResult{Status: "error", ErrorCode: "E_RESULTS_INVALID", ErrorMessage: fmt.Sprintf("A: %v", err), IssueID: issueID}, asJSON)
		return
	}
	rb, err := judge.LoadJudgeResult(bPath)
	if err != nil {
		outputResult(CliResult{Status: "error", ErrorCode: "E_RESULTS_INVALID", ErrorMessage: fmt.Sprintf("B: %v", err), IssueID: issueID}, asJSON)
		return
	}

	// Re-derivar el hash actual del frozen para el ledger.
	fr2, _ := judge.Freeze(mode, iss)
	hash := ""
	if fr2 != nil {
		hash = fr2.Hash
	}
	report := judge.MergeResults(iss, mode, latestRound, hash, ra, rb)
	ledgerPath, err := judge.WriteLedger(iss.WorktreePath, report)
	if err != nil {
		outputResult(CliResult{Status: "error", ErrorCode: "E_NO_FREEZE", ErrorMessage: fmt.Sprintf("cannot write ledger: %v", err), IssueID: issueID}, asJSON)
		return
	}

	// Emitir el contrato de salida — el path al ledger se incluye aunque
	// el veredicto sea APPROVED (el AC S16 pide la línea de "verdá" con
	// su metadata; APPROVED con ledger sigue siendo informativo).
	outputResult(CliResult{
		Status:  "ok",
		IssueID: issueID,
		Data: map[string]interface{}{
			"phase":   "J2",
			"mode":    string(mode),
			"round":   latestRound,
			"verdict": report.Verdict,
			"reason":  report.Reason,
			"ledger":  ledgerPath,
			"contract": report.VerdictContract(),
		},
	}, asJSON)
}

// shortHash reuso local (8 chars) — evita colisión con un identificador exportado.
func shortHash(s string) string {
	if len(s) >= 8 {
		return s[:8]
	}
	return s
}
