package tui

import (
	"fmt"
	"strings"
	"time"

	tea "github.com/charmbracelet/bubbletea"
	"github.com/charmbracelet/lipgloss"
)

type StepStatus int

const (
	StepPending StepStatus = iota
	StepRunning
	StepPassed
	StepFailed
	StepSkipped
)

type ValidationStep struct {
	Name        string
	Description string
	Status      StepStatus
	Duration    time.Duration
	Output      string
	Err         error
}

type ValidationModalModel struct {
	IssueID         string
	Visible         bool
	IsExecuting     bool
	Steps           []ValidationStep
	SelectedStepIdx int
	ScrollOffset    int
	ViewportH       int
	Width           int
	Height          int
}

func NewValidationModal(issueID string) *ValidationModalModel {
	m := &ValidationModalModel{
		IssueID:      issueID,
		Visible:      true,
		IsExecuting:  true,
		ViewportH:    8,
		Width:        80,
		Height:       24,
	}
	m.Reset(issueID)
	return m
}

func (m *ValidationModalModel) Reset(issueID string) {
	m.IssueID = issueID
	m.Visible = true
	m.IsExecuting = true
	m.SelectedStepIdx = 0
	m.ScrollOffset = 0
	m.Steps = []ValidationStep{
		{
			Name:        "Git Staging",
			Description: "Stage workspace modifications excluding review.log",
			Status:      StepRunning,
		},
		{
			Name:        "Executable Test Evidence",
			Description: "Execute discovered test suite (go test / pytest)",
			Status:      StepPending,
		},
		{
			Name:        "Governance Review Gate",
			Description: "Run Gentle Review Gate & verify risk receipts",
			Status:      StepPending,
		},
	}
}

func (m *ValidationModalModel) UpdateStep(stepIdx int, status StepStatus, dur time.Duration, output string, err error) {
	if stepIdx < 0 || stepIdx >= len(m.Steps) {
		return
	}
	m.Steps[stepIdx].Status = status
	m.Steps[stepIdx].Duration = dur
	m.Steps[stepIdx].Output = output
	m.Steps[stepIdx].Err = err

	if status == StepFailed {
		m.IsExecuting = false
		m.SelectedStepIdx = stepIdx
		// Skip remaining steps
		for i := stepIdx + 1; i < len(m.Steps); i++ {
			if m.Steps[i].Status == StepPending {
				m.Steps[i].Status = StepSkipped
			}
		}
	} else if status == StepPassed {
		if stepIdx+1 < len(m.Steps) {
			m.Steps[stepIdx+1].Status = StepRunning
			m.SelectedStepIdx = stepIdx + 1
		} else {
			m.IsExecuting = false
		}
	}
}

func (m *ValidationModalModel) HandleKey(msg tea.KeyMsg) (bool, tea.Cmd) {
	if !m.Visible {
		return false, nil
	}

	switch msg.String() {
	case "esc", "q", "enter":
		m.Visible = false
		return true, nil
	case "j", "down":
		m.ScrollOffset++
		return true, nil
	case "k", "up":
		if m.ScrollOffset > 0 {
			m.ScrollOffset--
		}
		return true, nil
	case "pgdown":
		m.ScrollOffset += 5
		return true, nil
	case "pgup":
		if m.ScrollOffset > 5 {
			m.ScrollOffset -= 5
		} else {
			m.ScrollOffset = 0
		}
		return true, nil
	case "1", "2", "3":
		idx := int(msg.Runes[0] - '1')
		if idx >= 0 && idx < len(m.Steps) {
			m.SelectedStepIdx = idx
			m.ScrollOffset = 0
		}
		return true, nil
	}
	return false, nil
}

func (m *ValidationModalModel) View() string {
	if !m.Visible {
		return ""
	}

	modalWidth := m.Width - 10
	if modalWidth < 60 {
		modalWidth = 60
	}
	if modalWidth > 90 {
		modalWidth = 90
	}

	headerStyle := lipgloss.NewStyle().
		Bold(true).
		Foreground(lipgloss.Color("#7AA2F7")).
		Border(lipgloss.NormalBorder(), false, false, true, false).
		BorderForeground(lipgloss.Color("#3B4261")).
		Padding(0, 1)

	boxStyle := lipgloss.NewStyle().
		Border(lipgloss.RoundedBorder()).
		BorderForeground(lipgloss.Color("#7AA2F7")).
		Padding(1, 2).
		Width(modalWidth)

	var sb strings.Builder
	sb.WriteString(headerStyle.Render(fmt.Sprintf("🔍 Validation Telemetry — Issue #%s", m.IssueID)) + "\n\n")

	for i, step := range m.Steps {
		var statusIcon string
		switch step.Status {
		case StepPassed:
			statusIcon = lipgloss.NewStyle().Foreground(lipgloss.Color("#9ECE6A")).Bold(true).Render("[✓]")
		case StepFailed:
			statusIcon = lipgloss.NewStyle().Foreground(lipgloss.Color("#F7768E")).Bold(true).Render("[✗]")
		case StepRunning:
			statusIcon = lipgloss.NewStyle().Foreground(lipgloss.Color("#E0AF68")).Bold(true).Render("[⏳]")
		case StepSkipped:
			statusIcon = lipgloss.NewStyle().Foreground(lipgloss.Color("#565F89")).Render("[-]")
		default:
			statusIcon = lipgloss.NewStyle().Foreground(lipgloss.Color("#565F89")).Render("[ ]")
		}

		stepName := step.Name
		if i == m.SelectedStepIdx {
			stepName = lipgloss.NewStyle().Bold(true).Foreground(lipgloss.Color("#FFFFFF")).Render(stepName)
		} else {
			stepName = lipgloss.NewStyle().Foreground(lipgloss.Color("#A9B1D6")).Render(stepName)
		}

		durStr := ""
		if step.Duration > 0 {
			durStr = lipgloss.NewStyle().Foreground(lipgloss.Color("#565F89")).Render(fmt.Sprintf(" (%s)", step.Duration.Round(time.Millisecond)))
		}

		sb.WriteString(fmt.Sprintf("%s Step %d: %s%s\n", statusIcon, i+1, stepName, durStr))
	}

	sb.WriteString("\n")

	// Viewport for active/selected step output
	var outContent string
	if m.SelectedStepIdx >= 0 && m.SelectedStepIdx < len(m.Steps) {
		selected := m.Steps[m.SelectedStepIdx]
		if selected.Err != nil {
			outContent = fmt.Sprintf("ERROR: %v\n\n%s", selected.Err, selected.Output)
		} else if selected.Output != "" {
			outContent = selected.Output
		} else {
			outContent = "(No output recorded for this step)"
		}
	}

	lines := strings.Split(strings.TrimSpace(outContent), "\n")
	viewportHeight := 6
	if m.Height > 30 {
		viewportHeight = 10
	}

	if m.ScrollOffset > len(lines)-1 && len(lines) > 0 {
		m.ScrollOffset = len(lines) - 1
	}

	start := m.ScrollOffset
	if start < 0 {
		start = 0
	}
	end := start + viewportHeight
	if end > len(lines) {
		end = len(lines)
	}

	visibleLines := lines[start:end]
	viewportBox := lipgloss.NewStyle().
		Border(lipgloss.NormalBorder()).
		BorderForeground(lipgloss.Color("#3B4261")).
		Background(lipgloss.Color("#16161E")).
		Padding(0, 1).
		Width(modalWidth - 6).
		Height(viewportHeight).
		Render(strings.Join(visibleLines, "\n"))

	sb.WriteString(viewportBox + "\n\n")

	hints := lipgloss.NewStyle().Foreground(lipgloss.Color("#565F89")).Render("Press [Esc]/[q]/[Enter] to close  •  [j]/[k] to scroll log  •  [1-3] to select step")
	sb.WriteString(hints)

	return boxStyle.Render(sb.String())
}
