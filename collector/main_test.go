package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"sync/atomic"
	"testing"
	"time"
)

func TestFetchJSONPreservesSourceAndBody(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("User-Agent"); got == "" {
			t.Fatal("collector did not send a User-Agent")
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`[{"token":"DEMO"}]`))
	}))
	defer server.Close()

	record, err := fetchJSON(&http.Client{Timeout: time.Second}, server.URL)
	if err != nil {
		t.Fatalf("fetchJSON returned an error: %v", err)
	}
	if record.StatusCode != http.StatusOK {
		t.Fatalf("expected status 200, got %d", record.StatusCode)
	}
	if record.SourceURL != server.URL {
		t.Fatalf("expected source URL %q, got %q", server.URL, record.SourceURL)
	}
	if !json.Valid(record.Body) {
		t.Fatal("stored body is not valid JSON")
	}
}

func TestFetchJSONRejectsNonJSON(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("not-json"))
	}))
	defer server.Close()

	_, err := fetchJSON(&http.Client{Timeout: time.Second}, server.URL)
	if err == nil {
		t.Fatal("expected invalid JSON to return an error")
	}
}

func TestFetchJSONWithRetryRecoversFromTemporaryFailure(t *testing.T) {
	var requests int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		attempt := atomic.AddInt32(&requests, 1)
		if attempt < 3 {
			_, _ = w.Write([]byte("temporary failure"))
			return
		}
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	defer server.Close()

	record, err := fetchJSONWithRetry(
		&http.Client{Timeout: time.Second},
		server.URL,
		3,
		time.Millisecond,
	)
	if err != nil {
		t.Fatalf("expected retry to recover, got %v", err)
	}
	if record.StatusCode != http.StatusOK {
		t.Fatalf("expected status 200, got %d", record.StatusCode)
	}
	if requests != 3 {
		t.Fatalf("expected 3 requests, got %d", requests)
	}
}

func TestSaveRecordWritesReusableJSON(t *testing.T) {
	path := filepath.Join(t.TempDir(), "record.json")
	record := RawRecord{
		SourceURL:   "https://example.test/data",
		CollectedAt: time.Date(2026, 11, 9, 0, 0, 0, 0, time.UTC),
		StatusCode:  http.StatusOK,
		Body:        json.RawMessage(`{"ok":true}`),
	}

	if err := saveRecord(path, record); err != nil {
		t.Fatalf("saveRecord returned an error: %v", err)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("could not read saved record: %v", err)
	}
	if !json.Valid(data) {
		t.Fatal("saved file is not valid JSON")
	}
}
