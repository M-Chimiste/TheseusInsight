"""Characterize trends endpoints on an empty database (envelopes only)."""


def test_trends_list_empty_envelope(client, empty_db, golden):
    resp = client.get("/api/trends")
    assert resp.status_code == 200
    golden("trends_empty_envelope", resp.json())


def test_trends_system_info_keys(client, empty_db, golden):
    resp = client.get("/api/trends/system-info")
    assert resp.status_code == 200
    # Values vary by machine (CPU counts etc.) — pin only the key set.
    golden("trends_system_info_keys", sorted(resp.json().keys()))


def test_trends_research_interests_empty(client, empty_db):
    resp = client.get("/api/trends/research-interests")
    assert resp.status_code == 200


def test_trends_profile_filters_accepted(client, seeded_data):
    """Exercise the id/tag filter resolution paths (extracted in B2)."""
    by_ids = client.get(
        "/api/trends", params={"profile_ids": str(seeded_data["test_profile_id"])}
    )
    assert by_ids.status_code == 200

    by_tag = client.get("/api/trends", params={"profile_tag": "ml"})
    assert by_tag.status_code == 200

    both = client.get(
        "/api/trends",
        params={"profile_ids": str(seeded_data["test_profile_id"]), "profile_tags": "ml"},
    )
    assert both.status_code == 200


def test_trends_invalid_profile_ids_is_400(client, empty_db):
    """Fixed in B7: the blanket `except Exception` used to swallow this
    HTTPException and re-raise it as a 500."""
    resp = client.get("/api/trends", params={"profile_ids": "abc"})
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid profile_ids format. Must be comma-separated integers."


def test_papers_profile_tag_filter(client, seeded_data):
    """Tag filter resolves to the Test Profile and its scored papers."""
    resp = client.get("/api/papers", params={"profile_tag": "ml"})
    assert resp.status_code == 200
    titles = sorted(p["title"] for p in resp.json()["items"])
    assert titles == ["Alpha Paper", "Beta Paper"]

    # CURRENT behavior: a tag matching no profiles resolves to an empty id
    # list, which the repository layer treats as "no filter" — all papers
    # come back. Pinned as-is (matches pre-refactor semantics).
    none = client.get("/api/papers", params={"profile_tag": "no-such-tag"})
    assert none.status_code == 200
    assert len(none.json()["items"]) == 3
