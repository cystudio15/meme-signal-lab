package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

type XQuoteCollection struct {
	Source         string       `json:"source"`
	Endpoint       string       `json:"endpoint"`
	CollectedAt    time.Time    `json:"collected_at_utc"`
	RequestedLimit int          `json:"requested_limit"`
	QuotePostCount int          `json:"quote_post_count"`
	SeedCount      int          `json:"seed_count"`
	Truncated      bool         `json:"truncated"`
	Seeds          []XQuoteSeed `json:"seeds"`
}

type XQuoteSeed struct {
	RootPostID string       `json:"root_post_id"`
	PostCount  int          `json:"post_count"`
	Pages      []XQuotePage `json:"pages"`
}

type XQuotePage struct {
	PageNumber     int             `json:"page_number"`
	CollectedAt    time.Time       `json:"collected_at_utc"`
	StatusCode     int             `json:"status_code"`
	ResultCount    int             `json:"result_count"`
	RateLimitLimit string          `json:"rate_limit_limit,omitempty"`
	RateRemaining  string          `json:"rate_limit_remaining,omitempty"`
	RateReset      string          `json:"rate_limit_reset,omitempty"`
	Body           json.RawMessage `json:"body"`
}

type xQuoteEnvelope struct {
	Data []json.RawMessage `json:"data"`
	Meta struct {
		ResultCount int    `json:"result_count"`
		NextToken   string `json:"next_token"`
	} `json:"meta"`
}

func collectXQuotes(
	ctx context.Context,
	client *http.Client,
	endpointTemplate string,
	seedIDs []string,
	limit int,
	pageSize int,
	bearerToken string,
) (XQuoteCollection, error) {
	if len(seedIDs) == 0 {
		return XQuoteCollection{}, fmt.Errorf("X quote seed list cannot be empty")
	}
	if limit < 1 {
		return XQuoteCollection{}, fmt.Errorf("X quote limit must be positive")
	}
	if pageSize < 10 || pageSize > 100 {
		return XQuoteCollection{}, fmt.Errorf("X quote page size must be between 10 and 100")
	}
	if bearerToken == "" {
		return XQuoteCollection{}, fmt.Errorf("X bearer token cannot be empty")
	}

	collection := XQuoteCollection{
		Source:         "x_api_quote_graph",
		Endpoint:       endpointTemplate,
		CollectedAt:    time.Now().UTC(),
		RequestedLimit: limit,
		Seeds:          make([]XQuoteSeed, 0, len(seedIDs)),
	}
	for _, seedID := range seedIDs {
		if collection.QuotePostCount >= limit {
			collection.Truncated = true
			break
		}
		seed := XQuoteSeed{RootPostID: seedID, Pages: make([]XQuotePage, 0)}
		nextToken := ""
		for {
			remaining := limit - collection.QuotePostCount
			if remaining < 10 {
				collection.Truncated = true
				break
			}
			requestSize := minInt(pageSize, remaining)
			page, envelope, err := fetchXQuotePageWithRetry(
				ctx, client, endpointTemplate, seedID, nextToken,
				requestSize, bearerToken, 3, time.Second,
			)
			if err != nil {
				return XQuoteCollection{}, err
			}
			page.PageNumber = len(seed.Pages) + 1
			seed.Pages = append(seed.Pages, page)
			count := len(envelope.Data)
			seed.PostCount += count
			collection.QuotePostCount += count
			nextToken = envelope.Meta.NextToken
			if nextToken == "" || count == 0 {
				break
			}
		}
		collection.Seeds = append(collection.Seeds, seed)
	}
	collection.SeedCount = len(collection.Seeds)
	return collection, nil
}

func fetchXQuotePageWithRetry(
	ctx context.Context,
	client *http.Client,
	endpointTemplate string,
	seedID string,
	nextToken string,
	pageSize int,
	bearerToken string,
	attempts int,
	backoff time.Duration,
) (XQuotePage, xQuoteEnvelope, error) {
	var lastErr error
	for attempt := 1; attempt <= attempts; attempt++ {
		page, envelope, retryable, err := fetchXQuotePage(
			ctx, client, endpointTemplate, seedID, nextToken, pageSize, bearerToken,
		)
		if err == nil {
			return page, envelope, nil
		}
		lastErr = err
		if !retryable || attempt == attempts {
			break
		}
		time.Sleep(backoff * time.Duration(attempt))
	}
	return XQuotePage{}, xQuoteEnvelope{}, fmt.Errorf(
		"X quote request for %s failed after %d attempt(s): %w", seedID, attempts, lastErr,
	)
}

func fetchXQuotePage(
	ctx context.Context,
	client *http.Client,
	endpointTemplate string,
	seedID string,
	nextToken string,
	pageSize int,
	bearerToken string,
) (XQuotePage, xQuoteEnvelope, bool, error) {
	endpoint := strings.Replace(endpointTemplate, "{id}", url.PathEscape(seedID), 1)
	parsed, err := url.Parse(endpoint)
	if err != nil {
		return XQuotePage{}, xQuoteEnvelope{}, false, err
	}
	params := parsed.Query()
	params.Set("max_results", strconv.Itoa(pageSize))
	params.Set(
		"tweet.fields",
		"id,text,created_at,author_id,lang,public_metrics,referenced_tweets,entities,conversation_id,possibly_sensitive",
	)
	if nextToken != "" {
		params.Set("pagination_token", nextToken)
	}
	parsed.RawQuery = params.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, parsed.String(), nil)
	if err != nil {
		return XQuotePage{}, xQuoteEnvelope{}, false, err
	}
	req.Header.Set("Authorization", "Bearer "+bearerToken)
	req.Header.Set("User-Agent", "Meme-Signal-Lab/0.3 educational-project")
	req.Header.Set("Accept", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return XQuotePage{}, xQuoteEnvelope{}, true, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return XQuotePage{}, xQuoteEnvelope{}, true, err
	}
	if !json.Valid(body) {
		return XQuotePage{}, xQuoteEnvelope{}, resp.StatusCode >= 500,
			fmt.Errorf("X quote API returned non-JSON status %d", resp.StatusCode)
	}

	page := XQuotePage{
		CollectedAt:    time.Now().UTC(),
		StatusCode:     resp.StatusCode,
		RateLimitLimit: resp.Header.Get("x-rate-limit-limit"),
		RateRemaining:  resp.Header.Get("x-rate-limit-remaining"),
		RateReset:      resp.Header.Get("x-rate-limit-reset"),
		Body:           bytes.Clone(body),
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		retryable := resp.StatusCode == http.StatusTooManyRequests || resp.StatusCode >= 500
		return page, xQuoteEnvelope{}, retryable, fmt.Errorf(
			"X quote API returned status %d: %s", resp.StatusCode, compactAPIError(body),
		)
	}
	var envelope xQuoteEnvelope
	if err := json.Unmarshal(body, &envelope); err != nil {
		return page, xQuoteEnvelope{}, false, err
	}
	page.ResultCount = len(envelope.Data)
	return page, envelope, false, nil
}
