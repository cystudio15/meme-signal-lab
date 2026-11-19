// Command collector fetches one permitted JSON endpoint and stores the raw
// response with collection metadata. It is intentionally small so a beginner
// can explain every step. Tests cover valid JSON, invalid responses, retries,
// and saving the immutable raw record.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

type RawRecord struct {
	SourceURL   string          `json:"source_url"`
	CollectedAt time.Time       `json:"collected_at_utc"`
	StatusCode  int             `json:"status_code"`
	Body        json.RawMessage `json:"body"`
}

func main() {
	url := flag.String("url", "", "permitted JSON endpoint to fetch")
	out := flag.String("out", "../data/raw/response.json", "output file")
	xQuery := flag.String("x-query", "", "X recent-search query (uses X_BEARER_TOKEN)")
	xQueryID := flag.String("x-query-id", "", "stable label for this X query track")
	xStartTime := flag.String("x-start-time", "", "optional RFC3339 lower bound for X recent search")
	xEndTime := flag.String("x-end-time", "", "optional RFC3339 upper bound for X search")
	xUserIDsFile := flag.String("x-user-ids-file", "", "file containing one X user ID per line")
	xUserLimit := flag.Int("x-user-limit", 150, "maximum X user profiles to read")
	xUserBatchSize := flag.Int("x-user-batch-size", 100, "X user IDs requested per API batch")
	xQuoteSeedsFile := flag.String("x-quote-seeds-file", "", "file containing root post IDs for quote expansion")
	xQuoteLimit := flag.Int("x-quote-limit", 200, "maximum quote posts to read across all seeds")
	xQuotePageSize := flag.Int("x-quote-page-size", 100, "quote posts requested per API page")
	xLimit := flag.Int("x-limit", 10, "maximum X posts to save")
	xPageSize := flag.Int("x-page-size", 10, "X posts requested per API page (10-100)")
	xEndpoint := flag.String(
		"x-endpoint",
		"https://api.x.com/2/tweets/search/recent",
		"X recent-search endpoint; override only for testing",
	)
	envFile := flag.String("env-file", "../.env", "optional local environment file")
	flag.Parse()

	if *xQuoteSeedsFile != "" {
		if err := loadEnvFile(*envFile); err != nil && !os.IsNotExist(err) {
			fail(fmt.Errorf("load environment file: %w", err))
		}
		token := os.Getenv("X_BEARER_TOKEN")
		if token == "" {
			fail(fmt.Errorf("X_BEARER_TOKEN is missing; set it in the environment or %s", *envFile))
		}
		seedIDs, err := loadIDs(*xQuoteSeedsFile, 200)
		if err != nil {
			fail(err)
		}
		collection, err := collectXQuotes(
			context.Background(),
			&http.Client{Timeout: 30 * time.Second},
			"https://api.x.com/2/tweets/{id}/quote_tweets",
			seedIDs,
			*xQuoteLimit,
			*xQuotePageSize,
			token,
		)
		if err != nil {
			fail(err)
		}
		if err := saveJSON(*out, collection); err != nil {
			fail(err)
		}
		fmt.Printf(
			"saved %d quote posts for %d seed posts to %s (truncated: %t)\n",
			collection.QuotePostCount, collection.SeedCount, *out, collection.Truncated,
		)
		return
	}

	if *xUserIDsFile != "" {
		if err := loadEnvFile(*envFile); err != nil && !os.IsNotExist(err) {
			fail(fmt.Errorf("load environment file: %w", err))
		}
		token := os.Getenv("X_BEARER_TOKEN")
		if token == "" {
			fail(fmt.Errorf("X_BEARER_TOKEN is missing; set it in the environment or %s", *envFile))
		}
		ids, err := loadIDs(*xUserIDsFile, *xUserLimit)
		if err != nil {
			fail(err)
		}
		collection, err := collectXUsers(
			context.Background(),
			&http.Client{Timeout: 30 * time.Second},
			"https://api.x.com/2/users",
			ids,
			*xUserBatchSize,
			token,
		)
		if err != nil {
			fail(err)
		}
		if err := saveJSON(*out, collection); err != nil {
			fail(err)
		}
		fmt.Printf(
			"saved %d X user profiles from %d batch(es) to %s\n",
			collection.UserCount, len(collection.Batches), *out,
		)
		return
	}

	if *xQuery != "" {
		if err := loadEnvFile(*envFile); err != nil && !os.IsNotExist(err) {
			fail(fmt.Errorf("load environment file: %w", err))
		}
		token := os.Getenv("X_BEARER_TOKEN")
		if token == "" {
			fail(fmt.Errorf("X_BEARER_TOKEN is missing; set it in the environment or %s", *envFile))
		}

		client := &http.Client{Timeout: 30 * time.Second}
		collection, err := collectXSearch(
			context.Background(),
			client,
			XSearchConfig{
				Endpoint:   *xEndpoint,
				QueryID:    *xQueryID,
				Query:      *xQuery,
				StartTime:  *xStartTime,
				EndTime:    *xEndTime,
				Limit:      *xLimit,
				PageSize:   *xPageSize,
				MaxRetries: 3,
				Backoff:    time.Second,
			},
			token,
		)
		if err != nil {
			fail(err)
		}
		if err := saveJSON(*out, collection); err != nil {
			fail(err)
		}
		fmt.Printf(
			"saved %d X posts from %d page(s) to %s (more pages available: %t)\n",
			collection.PostCount,
			len(collection.Pages),
			*out,
			collection.MorePagesAvailable,
		)
		return
	}

	if *url == "" {
		fmt.Fprintln(os.Stderr, "missing required -url or -x-query")
		os.Exit(2)
	}

	client := &http.Client{Timeout: 30 * time.Second}
	record, err := fetchJSONWithRetry(client, *url, 3, time.Second)
	if err != nil {
		fail(err)
	}
	if err := saveRecord(*out, record); err != nil {
		fail(err)
	}

	fmt.Printf("saved status %d from %s to %s\n", record.StatusCode, *url, *out)
}

func fetchJSONWithRetry(
	client *http.Client,
	url string,
	attempts int,
	backoff time.Duration,
) (RawRecord, error) {
	var lastErr error
	for attempt := 1; attempt <= attempts; attempt++ {
		record, err := fetchJSON(client, url)
		if err == nil {
			return record, nil
		}
		lastErr = err
		if attempt < attempts {
			time.Sleep(backoff * time.Duration(attempt))
		}
	}
	return RawRecord{}, fmt.Errorf("request failed after %d attempts: %w", attempts, lastErr)
}

func fetchJSON(client *http.Client, url string) (RawRecord, error) {
	req, err := http.NewRequest(http.MethodGet, url, nil)
	if err != nil {
		return RawRecord{}, err
	}
	req.Header.Set("User-Agent", "Meme-Signal-Lab/0.1 educational-project")

	resp, err := client.Do(req)
	if err != nil {
		return RawRecord{}, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return RawRecord{}, err
	}
	if !json.Valid(body) {
		return RawRecord{}, fmt.Errorf("endpoint did not return valid JSON")
	}

	return RawRecord{
		SourceURL:   url,
		CollectedAt: time.Now().UTC(),
		StatusCode:  resp.StatusCode,
		Body:        body,
	}, nil
}

func saveRecord(path string, record RawRecord) error {
	return saveJSON(path, record)
}

func saveJSON(path string, value any) error {
	encoded, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return err
	}
	return os.WriteFile(path, encoded, 0o644)
}

func fail(err error) {
	fmt.Fprintln(os.Stderr, "collector error:", err)
	os.Exit(1)
}
