package github

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"strconv"
	"strings"
)

type Client struct {
	httpClient *http.Client
	token      string
	repo       string
}

func ResolveToken(explicitToken string) string {
	if explicitToken != "" {
		return explicitToken
	}
	if envToken := os.Getenv("GITHUB_TOKEN"); envToken != "" {
		return envToken
	}
	if ghToken := os.Getenv("GH_TOKEN"); ghToken != "" {
		return ghToken
	}
	// Fallback to gh auth token CLI if installed
	cmd := exec.Command("gh", "auth", "token")
	out, err := cmd.Output()
	if err == nil {
		return strings.TrimSpace(string(out))
	}
	return ""
}

func NewClient(httpClient *http.Client, token, repo string) *Client {
	if httpClient == nil {
		httpClient = http.DefaultClient
	}
	return &Client{
		httpClient: httpClient,
		token:      ResolveToken(token),
		repo:       repo,
	}
}

type LabelResponse struct {
	Name string `json:"name"`
}

type IssueDetails struct {
	Number    int             `json:"number"`
	Title     string          `json:"title"`
	Body      string          `json:"body"`
	HTMLURL   string          `json:"html_url"`
	UpdatedAt string          `json:"updated_at"`
	Labels    []LabelResponse `json:"labels"`
}

// FetchIssueDetails hits the GitHub API to fetch rich issue data for open issues.
func (c *Client) FetchIssueDetails(ctx context.Context) ([]IssueDetails, error) {
	url := fmt.Sprintf("https://api.github.com/repos/%s/issues?state=open", c.repo)

	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, err
	}

	if c.token != "" {
		req.Header.Set("Authorization", "Bearer "+c.token)
	}
	req.Header.Set("Accept", "application/vnd.github.v3+json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("github api error: %d - %s", resp.StatusCode, string(body))
	}

	var issues []IssueDetails
	if err := json.NewDecoder(resp.Body).Decode(&issues); err != nil {
		return nil, err
	}

	return issues, nil
}

// FetchIssueIDs hits the GitHub API to fetch open issue IDs for the configured repo.
func (c *Client) FetchIssueIDs(ctx context.Context) ([]string, error) {
	issues, err := c.FetchIssueDetails(ctx)
	if err != nil {
		return nil, err
	}

	ids := make([]string, len(issues))
	for i, issue := range issues {
		ids[i] = strconv.Itoa(issue.Number)
	}

	return ids, nil
}
