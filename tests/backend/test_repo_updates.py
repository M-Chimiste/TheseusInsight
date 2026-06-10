"""Exercise the dynamic-UPDATE paths converted to build_set_clause (B2)."""


def test_build_set_clause():
    from theseus_insight.data_access.base import build_set_clause

    sql, params = build_set_clause({"a": 1, "b": "x"})
    assert sql == "a = %s, b = %s"
    assert params == [1, "x"]

    sql, params = build_set_clause(
        {"a": 1}, extra=("updated_at = now()", "n = n + 1")
    )
    assert sql == "a = %s, updated_at = now(), n = n + 1"
    assert params == [1]

    sql, params = build_set_clause({})
    assert sql == ""
    assert params == []


def test_model_catalog_update_roundtrip(empty_db):
    from theseus_insight.data_access.model_catalog import ModelCatalogRepository

    model_id = ModelCatalogRepository.insert(
        {
            "alias": "test-model",
            "model_string": "org/test-model",
            "provider_name": "ollama",
            "model_type": "judge",
            "tags": ["a"],
        }
    )
    ModelCatalogRepository.update(
        model_id, {"alias": "renamed", "tags": ["a", "b"], "temperature": 0.5}
    )
    row = ModelCatalogRepository.get(model_id)
    assert row["alias"] == "renamed"
    assert row["tags_json"] == ["a", "b"]
    assert row["temperature"] == 0.5

    ModelCatalogRepository.delete(model_id)


def test_task_update_status_roundtrip(empty_db):
    from theseus_insight.data_access.tasks import TaskRepository

    TaskRepository.upsert("t-b2", "newsletter", "pending", {"k": "v"})
    TaskRepository.update_status(
        "t-b2", "processing", progress=0.5, message="halfway", metadata={"step": 2}
    )
    row = TaskRepository.get("t-b2")
    assert row["status"] == "processing"
    assert row["progress"] == 0.5
    assert row["message"] == "halfway"
    assert row["metadata"] == {"step": 2}

    # status-only update must not clobber other columns
    TaskRepository.update_status("t-b2", "completed")
    row = TaskRepository.get("t-b2")
    assert row["status"] == "completed"
    assert row["message"] == "halfway"
