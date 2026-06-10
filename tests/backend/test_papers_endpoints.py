"""Characterize /api/papers list behavior: envelope, sorting, filters."""


def test_empty_papers_envelope(client, empty_db, golden):
    resp = client.get("/api/papers")
    assert resp.status_code == 200
    golden("papers_empty_envelope", resp.json())


def test_pagination_and_score_sort(client, seeded_data):
    resp = client.get(
        "/api/papers", params={"page_size": 2, "sort_field": "score", "sort_direction": "desc"}
    )
    assert resp.status_code == 200
    body = resp.json()
    titles = [p["title"] for p in body["items"]]
    assert titles == ["Alpha Paper", "Beta Paper"]
    assert body["total_items"] == 3
    assert body["total_pages"] == 2
    # Timestamps must come back as ISO strings (pins _convert_paper_timestamps).
    assert body["items"][0]["date"] == "2025-01-10"
    assert body["items"][0]["date_run"] == "2025-01-11"


def test_min_score_filter(client, seeded_data):
    resp = client.get("/api/papers", params={"score": 4})
    assert resp.status_code == 200
    titles = sorted(p["title"] for p in resp.json()["items"])
    assert titles == ["Alpha Paper", "Beta Paper"]


def test_date_range_filter(client, seeded_data):
    resp = client.get(
        "/api/papers", params={"from_date": "2025-01-04", "to_date": "2025-01-08"}
    )
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.json()["items"]]
    assert titles == ["Beta Paper"]


def test_invalid_profile_ids_response(client, seeded_data):
    """CURRENT behavior: the intended 400 is swallowed by get_papers' blanket
    `except Exception` (papers.py:409 has no `except HTTPException: raise`
    guard) and re-raised as 500. Pinned as-is; fixing the status code is a
    deliberate behavior change for the B2 helper-extraction phase — update
    this test in that commit.
    """
    resp = client.get("/api/papers", params={"profile_ids": "abc"})
    assert resp.status_code == 500
    assert "Invalid profile IDs format" in resp.json()["detail"]


def test_profile_score_join(client, seeded_data):
    """profile_id + min_profile_score filters through paper_profile_scores."""
    resp = client.get(
        "/api/papers",
        params={"profile_id": seeded_data["test_profile_id"], "min_profile_score": 5},
    )
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.json()["items"]]
    assert titles == ["Alpha Paper"]
