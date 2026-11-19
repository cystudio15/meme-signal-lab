package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"testing"
	"time"
)

func jsonMarshal(value any) ([]byte, error) {
	return json.Marshal(value)
}

func TestCollectXSearchFollowsPaginationAndStopsAtLimit(t *testing.T) {
	var requests int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if got := r.Header.Get("Authorization"); got != "Bearer test-token" {
			t.Fatalf("unexpected authorization header %q", got)
		}
		if got := r.URL.Query().Get("query"); got != "$MEME" {
			t.Fatalf("unexpected query %q", got)
		}

		w.Header().Set("Content-Type", "application/json")
		if requests == 1 {
			if token := r.URL.Query().Get("next_token"); token != "" {
				t.Fatalf("first request unexpectedly had next_token %q", token)
			}
			_, _ = w.Write([]byte(`{
                    "data":[{"id":"1"},{"id":"2"}],
                    "meta":{"result_count":2,"next_token":"page-2"}
                }`))
			return
		}

		if token := r.URL.Query().Get("next_token"); token != "page-2" {
			t.Fatalf("second request had next_token %q", token)
		}
		_, _ = w.Write([]byte(`{
            "data":[{"id":"3"},{"id":"4"}],
            "meta":{"result_count":2,"next_token":"page-3"}
        }`))
	}))
	defer server.Close()

	collection, err := collectXSearch(
		context.Background(),
		server.Client(),
		XSearchConfig{
			Endpoint:   server.URL,
			Query:      "$MEME",
			Limit:      4,
			PageSize:   2,
			MaxRetries: 1,
		},
		"test-token",
	)
	if err != nil {
		t.Fatalf("collectXSearch returned an error: %v", err)
	}
	if requests != 2 {
		t.Fatalf("expected 2 paginated requests, got %d", requests)
	}
	if collection.PostCount != 4 || len(collection.Pages) != 2 {
		t.Fatalf("unexpected collection counts: %+v", collection)
	}
	if !collection.MorePagesAvailable {
		t.Fatal("expected next page availability to be preserved")
	}
}

func TestCollectXSearchDoesNotWriteTokenToArtifact(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"data":[{"id":"1"}],"meta":{"result_count":1}}`))
	}))
	defer server.Close()

	collection, err := collectXSearch(
		context.Background(),
		server.Client(),
		XSearchConfig{
			Endpoint:   server.URL,
			Query:      "NIULAI",
			Limit:      1,
			PageSize:   1,
			MaxRetries: 1,
		},
		"secret-test-token",
	)
	if err != nil {
		t.Fatal(err)
	}
	encoded, err := json.Marshal(collection)
	if err != nil {
		t.Fatal(err)
	}
	if string(encoded) == "" || containsString(string(encoded), "secret-test-token") {
		t.Fatal("saved collection exposed the bearer token")
	}
}

func TestXSearchRetriesTemporaryServerError(t *testing.T) {
	var requests int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		w.Header().Set("Content-Type", "application/json")
		if requests == 1 {
			w.WriteHeader(http.StatusServiceUnavailable)
			_, _ = w.Write([]byte(`{"title":"temporary"}`))
			return
		}
		_, _ = w.Write([]byte(`{"data":[{"id":"1"}],"meta":{"result_count":1}}`))
	}))
	defer server.Close()

	collection, err := collectXSearch(
		context.Background(),
		server.Client(),
		XSearchConfig{
			Endpoint:   server.URL,
			Query:      "MEME",
			Limit:      1,
			PageSize:   1,
			MaxRetries: 2,
			Backoff:    time.Millisecond,
		},
		"test-token",
	)
	if err != nil {
		t.Fatal(err)
	}
	if requests != 2 || collection.PostCount != 1 {
		t.Fatalf("retry did not recover: requests=%d count=%d", requests, collection.PostCount)
	}
}

func TestXSearchEncodesQueryAndPageSize(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		assertQueryValue(t, r.URL.Query(), "query", `("meme coin" OR $MEME) -is:retweet`)
		assertQueryValue(t, r.URL.Query(), "max_results", "10")
		assertQueryValue(t, r.URL.Query(), "start_time", "2026-11-18T05:00:00Z")
		assertQueryValue(t, r.URL.Query(), "end_time", "2026-11-18T06:00:00Z")
		if r.URL.Query().Get("tweet.fields") == "" {
			t.Fatal("tweet.fields was not requested")
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"data":[],"meta":{"result_count":0}}`))
	}))
	defer server.Close()

	_, _, _, err := fetchXSearchPage(
		context.Background(),
		server.Client(),
		server.URL,
		`("meme coin" OR $MEME) -is:retweet`,
		"2026-11-18T05:00:00Z",
		"2026-11-18T06:00:00Z",
		"test-token",
		"",
		10,
	)
	if err != nil {
		t.Fatal(err)
	}
}

func TestLoadEnvFileDoesNotOverwriteExistingValue(t *testing.T) {
	key := "X_TEST_ENV_" + strconv.FormatInt(time.Now().UnixNano(), 10)
	if err := os.Setenv(key, "from-shell"); err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.Unsetenv(key) })

	path := filepath.Join(t.TempDir(), ".env")
	if err := os.WriteFile(path, []byte(fmt.Sprintf("%s=from-file\n", key)), 0o600); err != nil {
		t.Fatal(err)
	}
	if err := loadEnvFile(path); err != nil {
		t.Fatal(err)
	}
	if got := os.Getenv(key); got != "from-shell" {
		t.Fatalf("expected existing value to win, got %q", got)
	}
}

func assertQueryValue(t *testing.T, values url.Values, key, want string) {
	t.Helper()
	if got := values.Get(key); got != want {
		t.Fatalf("query parameter %s: want %q, got %q", key, want, got)
	}
}

func containsString(text, fragment string) bool {
	return len(fragment) > 0 && len(text) >= len(fragment) &&
		findString(text, fragment) >= 0
}

func findString(text, fragment string) int {
	for index := 0; index+len(fragment) <= len(text); index++ {
		if text[index:index+len(fragment)] == fragment {
			return index
		}
	}
	return -1
}
