package poller

import (
	"testing"
)

func TestParseGitRemoteURL(t *testing.T) {
	tests := []struct {
		name        string
		rawURL      string
		expected    string
		expectError bool
	}{
		{
			name:        "Standard HTTPS with .git",
			rawURL:      "https://github.com/mmarcoschambi/loom.git",
			expected:    "mmarcoschambi/loom",
			expectError: false,
		},
		{
			name:        "Standard HTTPS without .git",
			rawURL:      "https://github.com/mmarcoschambi/loom",
			expected:    "mmarcoschambi/loom",
			expectError: false,
		},
		{
			name:        "HTTPS with credentials and .git",
			rawURL:      "https://x-access-token:ghp_secret123@github.com/mmarcoschambi/loom.git",
			expected:    "mmarcoschambi/loom",
			expectError: false,
		},
		{
			name:        "Standard SSH SCP-style",
			rawURL:      "git@github.com:mmarcoschambi/loom.git",
			expected:    "mmarcoschambi/loom",
			expectError: false,
		},
		{
			name:        "SSH with host alias",
			rawURL:      "git@github.com-personal:mmarcoschambi/swing-momentum-v1.git",
			expected:    "mmarcoschambi/swing-momentum-v1",
			expectError: false,
		},
		{
			name:        "SSH protocol URI",
			rawURL:      "ssh://git@github.com/mmarcoschambi/loom.git",
			expected:    "mmarcoschambi/loom",
			expectError: false,
		},
		{
			name:        "URL with trailing slash and whitespace",
			rawURL:      "   https://github.com/mmarcoschambi/loom/   ",
			expected:    "mmarcoschambi/loom",
			expectError: false,
		},
		{
			name:        "Empty URL",
			rawURL:      "",
			expected:    "",
			expectError: true,
		},
		{
			name:        "Invalid random string",
			rawURL:      "not-a-valid-remote-url",
			expected:    "",
			expectError: true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			actual, err := ParseGitRemoteURL(tc.rawURL)
			if tc.expectError {
				if err == nil {
					t.Fatalf("expected error for %q, got nil (slug=%q)", tc.rawURL, actual)
				}
			} else {
				if err != nil {
					t.Fatalf("unexpected error for %q: %v", tc.rawURL, err)
				}
				if actual != tc.expected {
					t.Fatalf("expected %q, got %q", tc.expected, actual)
				}
			}
		})
	}
}
