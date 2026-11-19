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
	"strings"
	"time"
)

type XUserCollection struct {
	Source         string       `json:"source"`
	Endpoint       string       `json:"endpoint"`
	CollectedAt    time.Time    `json:"collected_at_utc"`
	RequestedLimit int          `json:"requested_limit"`
	UserCount      int          `json:"user_count"`
	Batches        []XUserBatch `json:"batches"`
}

type XUserBatch struct {
	BatchNumber    int             `json:"batch_number"`
	CollectedAt    time.Time       `json:"collected_at_utc"`
	StatusCode     int             `json:"status_code"`
	RequestedIDs   int             `json:"requested_ids"`
	ResultCount    int             `json:"result_count"`
	RateLimitLimit string          `json:"rate_limit_limit,omitempty"`
	RateRemaining  string          `json:"rate_limit_remaining,omitempty"`
	RateReset      string          `json:"rate_limit_reset,omitempty"`
	Body           json.RawMessage `json:"body"`
}

type xUsersEnvelope struct {
	Data []json.RawMessage `json:"data"`
}

func loadIDs(path string, limit int) ([]string, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	seen := make(map[string]bool)
	ids := make([]string, 0, limit)
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		id := strings.TrimSpace(scanner.Text())
		if id == "" || seen[id] {
			continue
		}
		seen[id] = true
		ids = append(ids, id)
		if len(ids) == limit {
			break
		}
	}
	return ids, scanner.Err()
}

func collectXUsers(
	ctx context.Context,
	client *http.Client,
	endpoint string,
	ids []string,
	batchSize int,
	bearerToken string,
) (XUserCollection, error) {
	if len(ids) == 0 {
		return XUserCollection{}, fmt.Errorf("X user ID list cannot be empty")
	}
	if batchSize < 1 || batchSize > 100 {
		return XUserCollection{}, fmt.Errorf("X user batch size must be between 1 and 100")
	}
	if bearerToken == "" {
		return XUserCollection{}, fmt.Errorf("X bearer token cannot be empty")
	}

	collection := XUserCollection{
		Source:         "x_api_user_lookup",
		Endpoint:       endpoint,
		CollectedAt:    time.Now().UTC(),
		RequestedLimit: len(ids),
		Batches:        make([]XUserBatch, 0),
	}
	for start := 0; start < len(ids); start += batchSize {
		end := minInt(start+batchSize, len(ids))
		batch, count, err := fetchXUserBatch(
			ctx, client, endpoint, ids[start:end], bearerToken,
		)
		if err != nil {
			return XUserCollection{}, err
		}
		batch.BatchNumber = len(collection.Batches) + 1
		collection.Batches = append(collection.Batches, batch)
		collection.UserCount += count
	}
	return collection, nil
}

func fetchXUserBatch(
	ctx context.Context,
	client *http.Client,
	endpoint string,
	ids []string,
	bearerToken string,
) (XUserBatch, int, error) {
	parsed, err := url.Parse(endpoint)
	if err != nil {
		return XUserBatch{}, 0, err
	}
	params := parsed.Query()
	params.Set("ids", strings.Join(ids, ","))
	params.Set(
		"user.fields",
		"id,name,username,created_at,description,location,verified,verified_type,public_metrics,protected,url,entities,profile_image_url",
	)
	parsed.RawQuery = params.Encode()

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, parsed.String(), nil)
	if err != nil {
		return XUserBatch{}, 0, err
	}
	req.Header.Set("Authorization", "Bearer "+bearerToken)
	req.Header.Set("User-Agent", "Meme-Signal-Lab/0.2 educational-project")
	req.Header.Set("Accept", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return XUserBatch{}, 0, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return XUserBatch{}, 0, err
	}
	if !json.Valid(body) {
		return XUserBatch{}, 0, fmt.Errorf("X user API returned non-JSON status %d", resp.StatusCode)
	}

	batch := XUserBatch{
		CollectedAt:    time.Now().UTC(),
		StatusCode:     resp.StatusCode,
		RequestedIDs:   len(ids),
		RateLimitLimit: resp.Header.Get("x-rate-limit-limit"),
		RateRemaining:  resp.Header.Get("x-rate-limit-remaining"),
		RateReset:      resp.Header.Get("x-rate-limit-reset"),
		Body:           bytes.Clone(body),
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return batch, 0, fmt.Errorf(
			"X user API returned status %d: %s", resp.StatusCode, compactAPIError(body),
		)
	}
	var envelope xUsersEnvelope
	if err := json.Unmarshal(body, &envelope); err != nil {
		return batch, 0, err
	}
	batch.ResultCount = len(envelope.Data)
	return batch, len(envelope.Data), nil
}
