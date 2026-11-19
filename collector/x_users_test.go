package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func TestCollectXUsersUsesBatchesAndDoesNotStoreToken(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if r.Header.Get("Authorization") != "Bearer profile-token" {
			t.Fatal("missing bearer token")
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"data":[{"id":"1","username":"demo"}]}`))
	}))
	defer server.Close()

	collection, err := collectXUsers(
		context.Background(), server.Client(), server.URL,
		[]string{"1", "2", "3"}, 2, "profile-token",
	)
	if err != nil {
		t.Fatal(err)
	}
	if requests != 2 || len(collection.Batches) != 2 || collection.UserCount != 2 {
		t.Fatalf("unexpected collection: %+v", collection)
	}
	encoded := compactAPIError(mustJSON(t, collection))
	if containsString(encoded, "profile-token") {
		t.Fatal("collection exposed bearer token")
	}
}

func TestLoadIDsDeduplicatesAndCaps(t *testing.T) {
	path := filepath.Join(t.TempDir(), "ids.txt")
	if err := os.WriteFile(path, []byte("1\n2\n1\n3\n"), 0o600); err != nil {
		t.Fatal(err)
	}
	ids, err := loadIDs(path, 2)
	if err != nil {
		t.Fatal(err)
	}
	if len(ids) != 2 || ids[0] != "1" || ids[1] != "2" {
		t.Fatalf("unexpected IDs: %v", ids)
	}
}

func mustJSON(t *testing.T, value any) []byte {
	t.Helper()
	data, err := jsonMarshal(value)
	if err != nil {
		t.Fatal(err)
	}
	return data
}
