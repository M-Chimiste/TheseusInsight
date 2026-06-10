"""Characterize profile endpoints: default profile + CRUD roundtrip."""


def test_default_profile_endpoint(client, empty_db):
    resp = client.get("/api/profiles/default")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Default"
    assert body["is_default"] is True

    listing = client.get("/api/profiles")
    assert listing.status_code == 200
    names = [p["name"] for p in listing.json()]
    assert "Default" in names


def test_profile_crud_roundtrip(client, empty_db, golden):
    created = client.post(
        "/api/profiles",
        json={
            "name": "CRUD Profile",
            "description": "created by characterization test",
            "color": "#00ff00",
            "tags": ["crud"],
            "email_recipients": ["someone@example.org"],
        },
    )
    assert created.status_code == 200, created.text
    profile = created.json()
    assert profile["name"] == "CRUD Profile"
    golden("profile_create_keys", sorted(profile.keys()))
    pid = profile["id"]

    fetched = client.get(f"/api/profiles/{pid}")
    assert fetched.status_code == 200
    golden("profile_with_stats_keys", sorted(fetched.json().keys()))

    updated = client.put(f"/api/profiles/{pid}", json={"description": "updated"})
    assert updated.status_code == 200
    assert updated.json()["description"] == "updated"

    deleted = client.delete(f"/api/profiles/{pid}")
    assert deleted.status_code == 200

    gone = client.get(f"/api/profiles/{pid}")
    assert gone.status_code == 404
