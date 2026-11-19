package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

// XSearchConfig describes one bounded, read-only recent-search collection.
// Limit controls how many posts are retained; PageSize controls each API call.
type XSearchConfig struct {
	Endpoint   string
	QueryID    string
	Query      string
	StartTime  string
	EndTime    string
	Limit      int
	PageSize   int
	MaxRetries int
	Backoff    time.Duration
}

// XSearchCollection is an auditable raw artifact. Each page preserves the
// original X JSON response, collection time, status, and non-secret rate-limit
// headers. Authorization headers are never written to disk.
type XSearchCollection struct {
	Source             string        `json:"source"`
	Endpoint           string        `json:"endpoint"`
	QueryID            string        `json:"query_id,omitempty"`
	Query              string        `json:"query"`
	CollectedAt        time.Time     `json:"collected_at_utc"`
	RequestedLimit     int           `json:"requested_limit"`
	PostCount          int           `json:"post_count"`
	MorePagesAvailable bool          `json:"more_pages_available"`
	Pages              []XSearchPage `json:"pages"`
}

type XSearchPage struct {
	PageNumber     int             `json:"page_number"`
	CollectedAt    time.Time       `json:"collected_at_utc"`
	StatusCode     int             `json:"status_code"`
	ResultCount    int             `json:"result_count"`
	RateLimitLimit string          `json:"rate_limit_limit,omitempty"`
	RateRemaining  string          `json:"rate_limit_remaining,omitempty"`
	RateReset      string          `json:"rate_limit_reset,omitempty"`
	Body           json.RawMessage `json:"body"`
}

type xSearchEnvelope struct {
	Data []json.RawMessage `json:"data"`
	Meta struct {
		ResultCount int    `json:"result_count"`
		NextToken   string `json:"next_token"`
	} `json:"meta"`
}

func collectXSearch(
	ctx context.Context,
	client *http.Client,
	config XSearchConfig,
	bearerToken string,
) (XSearchCollection, error) {
	if strings.TrimSpace(config.Query) == "" {
		return XSearchCollection{}, fmt.Errorf("X search query cannot be empty")
	}
	if config.Limit < 1 {
		return XSearchCollection{}, fmt.Errorf("X search limit must be positive")
	}
	if config.PageSize < 1 || config.PageSize > 100 {
		return XSearchCollection{}, fmt.Errorf("X page size must be between 1 and 100")
	}
	if bearerToken == "" {
		return XSearchCollection{}, fmt.Errorf("X bearer token cannot be empty")
	}
	if config.StartTime != "" {
		if _, err := time.Parse(time.RFC3339, config.StartTime); err != nil {
			return XSearchCollection{}, fmt.Errorf("X start time must be RFC3339: %w", err)
		}
	}
	if config.EndTime != "" {
		if _, err := time.Parse(time.RFC3339, config.EndTime); err != nil {
			return XSearchCollection{}, fmt.Errorf("X end time must be RFC3339: %w", err)
		}
	}
	if config.MaxRetries < 1 {
		config.MaxRetries = 1
	}

	source := "x_api_recent_search"
	if strings.Contains(config.Endpoint, "/search/all") {
		source = "x_api_full_archive_search"
	}
	collection := XSearchCollection{
		Source:         source,
		Endpoint:       config.Endpoint,
		QueryID:        config.QueryID,
		Query:          config.Query,
		CollectedAt:    time.Now().UTC(),
		RequestedLimit: config.Limit,
		Pages:          make([]XSearchPage, 0),
	}

	nextToken := ""
	for collection.PostCount < config.Limit {
		remaining := config.Limit - collection.PostCount
		pageSize := minInt(config.PageSize, remaining)
		// X search endpoints require max_results >= 10. The final page can
		// therefore return up to nine posts beyond the requested soft limit.
		if pageSize < 10 {
			pageSize = 10
		}
		page, envelope, err := fetchXSearchPageWithRetry(
			ctx,
			client,
			config,
			bearerToken,
			nextToken,
			pageSize,
		)
		if err != nil {
			return XSearchCollection{}, err
		}

		page.PageNumber = len(collection.Pages) + 1
		collection.Pages = append(collection.Pages, page)
		collection.PostCount += len(envelope.Data)
		nextToken = envelope.Meta.NextToken
		if nextToken == "" {
			break
		}
		// Do not request another page when fewer than ten posts remain: X
		// enforces a ten-result minimum and that request could exceed a hard
		// Keep collection bounded even when a response includes many results.
		if config.PageSize >= 10 && config.Limit-collection.PostCount < 10 {
			break
		}
	}

	collection.MorePagesAvailable = nextToken != ""
	return collection, nil
}

func fetchXSearchPageWithRetry(
	ctx context.Context,
	client *http.Client,
	config XSearchConfig,
	bearerToken string,
	nextToken string,
	pageSize int,
) (XSearchPage, xSearchEnvelope, error) {
	var lastErr error
	for attempt := 1; attempt <= config.MaxRetries; attempt++ {
		page, envelope, retryable, err := fetchXSearchPage(
			ctx,
			client,
			config.Endpoint,
			config.Query,
			config.StartTime,
			config.EndTime,
			bearerToken,
			nextToken,
			pageSize,
		)
		if err == nil {
			return page, envelope, nil
		}
		lastErr = err
		if !retryable || attempt == config.MaxRetries {
			break
		}
		delay := config.Backoff * time.Duration(attempt)
		if delay > 0 {
			timer := time.NewTimer(delay)
			select {
			case <-ctx.Done():
				timer.Stop()
				return XSearchPage{}, xSearchEnvelope{}, ctx.Err()
			case <-timer.C:
			}
		}
	}
	return XSearchPage{}, xSearchEnvelope{}, fmt.Errorf(
		"X search request failed after %d attempt(s): %w",
		config.MaxRetries,
		lastErr,
	)
}

func fetchXSearchPage(
	ctx context.Context,
	client *http.Client,
	endpoint string,
	query string,
	startTime string,
	endTime string,
	bearerToken string,
	nextToken string,
	pageSize int,
) (XSearchPage, xSearchEnvelope, bool, error) {
	parsed, err := url.Parse(endpoint)
	if err != nil {
		return XSearchPage{}, xSearchEnvelope{}, false, fmt.Errorf("parse X endpoint: %w", err)
	}
	params := parsed.Query()
	params.Set("query", query)
	if startTime != "" {
		params.Set("start_time", startTime)
	}
	if endTime != "" {
		params.Set("end_time", endTime)
	}
	params.Set("max_results", strconv.Itoa(pageSize))
	params.Set(
		"tweet.fields",
		"id,text,created_at,author_id,lang,public_metrics,referenced_tweets,entities,conversation_id,possibly_sensitive",
	)
	if nextToken != "" {
		params.Set("next_token", nextToken)
	}
	parsed.RawQuery = params.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, parsed.String(), nil)
	if err != nil {
		return XSearchPage{}, xSearchEnvelope{}, false, err
	}
	req.Header.Set("Authorization", "Bearer "+bearerToken)
	req.Header.Set("User-Agent", "Meme-Signal-Lab/0.2 educational-project")
	req.Header.Set("Accept", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return XSearchPage{}, xSearchEnvelope{}, true, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return XSearchPage{}, xSearchEnvelope{}, true, err
	}
	if !json.Valid(body) {
		return XSearchPage{}, xSearchEnvelope{}, resp.StatusCode >= 500,
			fmt.Errorf("X API returned non-JSON status %d", resp.StatusCode)
	}

	page := XSearchPage{
		CollectedAt:    time.Now().UTC(),
		StatusCode:     resp.StatusCode,
		RateLimitLimit: resp.Header.Get("x-rate-limit-limit"),
		RateRemaining:  resp.Header.Get("x-rate-limit-remaining"),
		RateReset:      resp.Header.Get("x-rate-limit-reset"),
		Body:           bytes.Clone(body),
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		retryable := resp.StatusCode == http.StatusTooManyRequests || resp.StatusCode >= 500
		return page, xSearchEnvelope{}, retryable,
			fmt.Errorf("X API returned status %d: %s", resp.StatusCode, compactAPIError(body))
	}

	var envelope xSearchEnvelope
	if err := json.Unmarshal(body, &envelope); err != nil {
		return page, xSearchEnvelope{}, false, fmt.Errorf("decode X response: %w", err)
	}
	page.ResultCount = envelope.Meta.ResultCount
	return page, envelope, false, nil
}

func compactAPIError(body []byte) string {
	const maxLength = 500
	text := strings.TrimSpace(string(body))
	if len(text) > maxLength {
		return text[:maxLength] + "..."
	}
	return text
}

func minInt(left, right int) int {
	if left < right {
		return left
	}
	return right
}

// loadEnvFile provides the one feature needed from a dotenv package while
// keeping the beginner project dependency-free. Existing environment values
// win, so CI or a shell export is never overwritten by the local file.
func loadEnvFile(path string) error {
	file, err := os.Open(path)
	if err != nil {
		return err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, value, found := strings.Cut(line, "=")
		if !found {
			continue
		}
		key = strings.TrimSpace(key)
		value = strings.Trim(strings.TrimSpace(value), "\"'")
		if key != "" && os.Getenv(key) == "" {
			if err := os.Setenv(key, value); err != nil {
				return err
			}
		}
	}
	return scanner.Err()
}
