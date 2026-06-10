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
