package main

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestCollectXQuotesFollowsPaginationAndPreservesRoot(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if !strings.Contains(r.URL.Path, "/root-1/quote_tweets") {
			t.Fatalf("unexpected path %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		if requests == 1 {
			_, _ = w.Write([]byte(`{"data":[{"id":"q1"}],"meta":{"result_count":1,"next_token":"next"}}`))
			return
		}
		if r.URL.Query().Get("pagination_token") != "next" {
			t.Fatal("pagination token was not followed")
		}
		_, _ = w.Write([]byte(`{"data":[{"id":"q2"}],"meta":{"result_count":1}}`))
	}))
	defer server.Close()

	collection, err := collectXQuotes(
		context.Background(), server.Client(), server.URL+"/{id}/quote_tweets",
		[]string{"root-1"}, 20, 10, "token",
	)
	if err != nil {
		t.Fatal(err)
	}
	if requests != 2 || collection.QuotePostCount != 2 || collection.SeedCount != 1 {
		t.Fatalf("unexpected collection: %+v", collection)
	}
	if collection.Seeds[0].RootPostID != "root-1" {
		t.Fatal("root post relation was not preserved")
	}
}
