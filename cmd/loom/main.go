package main

import (
	"context"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"strconv"
	"syscall"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/joho/godotenv"
	"github.com/mmarcoschambi/loom/internal/exec"
	"github.com/mmarcoschambi/loom/internal/fsm"
	"github.com/mmarcoschambi/loom/internal/github"
	"github.com/mmarcoschambi/loom/internal/poller"
	"github.com/mmarcoschambi/loom/internal/tui"
)

func main() {
	if len(os.Args) > 1 && os.Args[1] == "test-exec" {
		fmt.Println("Test exec subcommand")
		return
	}

	homeDir, err := os.UserHomeDir()
	if err != nil {
		fmt.Printf("Error getting home directory: %v\n", err)
		os.Exit(1)
	}
	stateDir := filepath.Join(homeDir, ".loom", "state")
	reg := fsm.NewFSMRegistry(stateDir)
	if err := reg.RecoverState(); err != nil {
		// Non-fatal: corrupt files are quarantined inside LoadState, so this is a real I/O problem.
		fmt.Fprintf(os.Stderr, "warn: loading persisted state: %v\n", err)
	}

	// Load .env (ignore error if not present)
	_ = godotenv.Load()

	// Auto-detect repository in CWD and register in tracked_repos
	if cwd, err := os.Getwd(); err == nil {
		if detectedRepo, err := poller.DetectCurrentRepo(cwd); err == nil && detectedRepo != "" {
			_, _ = reg.AddTrackedRepo(detectedRepo)
		}
	}

	ghToken := os.Getenv("GITHUB_TOKEN")

	if len(os.Args) > 1 && (os.Args[1] == "poll-once" || os.Args[1] == "poll") {
		ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
		defer cancel()
		trackedRepos := reg.GetTrackedRepos()
		totalPolled := 0
		for _, repo := range trackedRepos {
			client := github.NewClient(nil, ghToken, repo)
			issues, err := client.FetchIssueDetails(ctx)
			if err != nil {
				fmt.Fprintf(os.Stderr, "poll-once failed for %s: %v\n", repo, err)
				continue
			}
			totalPolled += len(issues)
			for _, iss := range issues {
				id := strconv.Itoa(iss.Number)
				var labels []string
				for _, l := range iss.Labels {
					labels = append(labels, l.Name)
				}
				newIss := &fsm.IssueFSM{
					ID:        id,
					Repo:      repo,
					Title:     iss.Title,
					Body:      iss.Body,
					URL:       iss.HTMLURL,
					Labels:    labels,
					UpdatedAt: iss.UpdatedAt,
					State:     fsm.PENDING,
				}
				_ = reg.Save(newIss)
			}
		}
		fmt.Printf("✅ Successfully polled %d issues across %d repositories (revision %d)\n", totalPolled, len(trackedRepos), reg.Revision)
		return
	}

	// Create multi-repo poller (base: 30s, max: 5m) with full issue details
	fetchDetailsRepoFn := func(ctx context.Context, repo string) ([]poller.IssueInfo, error) {
		client := github.NewClient(nil, ghToken, repo)
		issues, err := client.FetchIssueDetails(ctx)
		if err != nil {
			return nil, err
		}
		var result []poller.IssueInfo
		for _, iss := range issues {
			var labels []string
			for _, l := range iss.Labels {
				labels = append(labels, l.Name)
			}
			result = append(result, poller.IssueInfo{
				ID:        strconv.Itoa(iss.Number),
				Repo:      repo,
				Title:     iss.Title,
				Body:      iss.Body,
				Labels:    labels,
				URL:       iss.HTMLURL,
				UpdatedAt: iss.UpdatedAt,
			})
		}
		return result, nil
	}

	importPoller := poller.NewMultiRepoGithubPoller(30*time.Second, 5*time.Minute, reg, fetchDetailsRepoFn)
	importPoller.Start(context.Background())
	// trigger initial force poll
	importPoller.ForcePoll()

	model := tui.NewLoomModel(reg, importPoller)
	p := tea.NewProgram(model, tea.WithAltScreen(), tea.WithMouseCellMotion())

	// SIGINT Interceptor
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	go func() {
		<-sigChan
		// Clean up on exit
		states := reg.GetStates()
		for _, issue := range states {
			if issue.PID > 0 {
				if err := exec.KillProcessTree(issue.PID); err != nil {
					fmt.Fprintf(os.Stderr, "warn: killing process tree for issue %s: %v\n", issue.ID, err)
				}
			}
		}
		// FSMRegistry PersistState is automatically called on TransitionTo,
		// but we can ensure states are saved if needed.
		p.Quit()
	}()

	if _, err := p.Run(); err != nil {
		fmt.Printf("Error running program: %v\n", err)
		os.Exit(1)
	}
}
