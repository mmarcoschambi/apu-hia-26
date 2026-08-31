package tui

import (
	"errors"
	"strings"
	"testing"
	"time"

	tea "github.com/charmbracelet/bubbletea"
)

func TestValidationModal_InitAndReset(t *testing.T) {
	modal := NewValidationModal("issue-123")
	if !modal.Visible {
		t.Fatal("Expected modal to be visible initially")
	}
	if modal.IssueID != "issue-123" {
		t.Fatalf("Expected issue-123, got %s", modal.IssueID)
	}
	if len(modal.Steps) != 3 {
		t.Fatalf("Expected 3 validation steps, got %d", len(modal.Steps))
	}
	if modal.Steps[0].Name != "Git Staging" {
		t.Fatalf("Expected step 1 Git Staging, got %s", modal.Steps[0].Name)
	}
	if modal.Steps[1].Name != "Executable Test Evidence" {
		t.Fatalf("Expected step 2 Executable Test Evidence, got %s", modal.Steps[1].Name)
	}
	if modal.Steps[2].Name != "Governance Review Gate" {
		t.Fatalf("Expected step 3 Governance Review Gate, got %s", modal.Steps[2].Name)
	}
}

func TestValidationModal_StepTransitions(t *testing.T) {
	modal := NewValidationModal("issue-456")
	modal.UpdateStep(0, StepPassed, 50*time.Millisecond, "3 files staged", nil)

	if modal.Steps[0].Status != StepPassed {
		t.Fatalf("Expected StepPassed, got %v", modal.Steps[0].Status)
	}
	if modal.Steps[0].Output != "3 files staged" {
		t.Fatalf("Expected output '3 files staged', got %s", modal.Steps[0].Output)
	}

	testErr := errors.New("tests failed: 2 broken")
	modal.UpdateStep(1, StepFailed, 1200*time.Millisecond, "FAIL: test_x\nFAIL: test_y", testErr)

	if modal.Steps[1].Status != StepFailed {
		t.Fatalf("Expected StepFailed, got %v", modal.Steps[1].Status)
	}
	if modal.Steps[2].Status != StepSkipped {
		t.Fatalf("Expected StepSkipped for step 3 on step 2 failure, got %v", modal.Steps[2].Status)
	}
}

func TestValidationModal_KeyDismissalAndScrolling(t *testing.T) {
	modal := NewValidationModal("issue-789")
	modal.Width = 80
	modal.Height = 24
	modal.UpdateStep(1, StepFailed, time.Second, "line 1\nline 2\nline 3\nline 4\nline 5\nline 6\nline 7\nline 8\nline 9\nline 10", errors.New("failed"))

	// Scroll down with 'j'
	modal.HandleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'j'}})
	if modal.ScrollOffset != 1 {
		t.Fatalf("Expected ScrollOffset 1, got %d", modal.ScrollOffset)
	}

	// Scroll up with 'k'
	modal.HandleKey(tea.KeyMsg{Type: tea.KeyRunes, Runes: []rune{'k'}})
	if modal.ScrollOffset != 0 {
		t.Fatalf("Expected ScrollOffset 0, got %d", modal.ScrollOffset)
	}

	// Dismiss with Esc
	modal.HandleKey(tea.KeyMsg{Type: tea.KeyEsc})
	if modal.Visible {
		t.Fatal("Expected modal to be dismissed on Esc")
	}
}

func TestValidationModal_ViewRendering(t *testing.T) {
	modal := NewValidationModal("issue-999")
	modal.Width = 80
	modal.Height = 24
	modal.UpdateStep(0, StepPassed, 10*time.Millisecond, "staged", nil)
	modal.UpdateStep(1, StepFailed, 500*time.Millisecond, "syntax error in foo.go", errors.New("syntax error"))

	out := modal.View()
	if !strings.Contains(out, "Validation Telemetry") {
		t.Fatalf("Expected 'Validation Telemetry' header, got:\n%s", out)
	}
	if !strings.Contains(out, "Git Staging") {
		t.Fatalf("Expected 'Git Staging' in view, got:\n%s", out)
	}
	if !strings.Contains(out, "syntax error in foo.go") {
		t.Fatalf("Expected error output in view, got:\n%s", out)
	}
}
