"""Pin the whole HTTP surface: any route added/removed/renamed fails this."""


def test_openapi_surface_unchanged(client, golden):
    spec = client.get("/openapi.json")
    assert spec.status_code == 200
    paths = spec.json()["paths"]
    surface = sorted(
        f"{method.upper()} {path}"
        for path, methods in paths.items()
        for method in methods
    )
    golden("api_surface", surface)
