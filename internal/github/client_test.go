package github

import (
	"context"
	"errors"
	"net/http"
	"testing"
)

// MockRoundTripper intercepts HTTP requests for tests
type MockRoundTripper struct {
	RoundTripFunc func(req *http.Request) (*http.Response, error)
}

func (m *MockRoundTripper) RoundTrip(req *http.Request) (*http.Response, error) {
	return m.RoundTripFunc(req)
}

// 3.6 RED TEST: Network drops in HTTP Client
func TestFetchIssues_NetworkError(t *testing.T) {
	mockClient := &http.Client{
		Transport: &MockRoundTripper{
			RoundTripFunc: func(req *http.Request) (*http.Response, error) {
				return nil, errors.New("simulated network drop")
			},
		},
	}

	client := NewClient(mockClient, "token", "owner/repo")
	_, err := client.FetchIssueIDs(context.Background())
	if err == nil {
		t.Fatal("Expected network drop error, got nil")
	}
}
