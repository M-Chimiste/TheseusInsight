"""Shared fixtures for the characterization-test suite.

DESIGN CONSTRAINTS (verified against the codebase — do not "simplify"):

1. `DATABASE_URL` is read once, at import of `theseus_insight.db`
   (db/__init__.py). Importing ANY theseus_insight submodule executes the
   package __init__, which imports the whole backend. Therefore this file
   sets all env vars BEFORE any theseus_insight import, and asserts nothing
   imported it first.

2. `theseus_insight.main` triggers DB access at import time
   (api/tasks.py module-level TaskManager(), research_agent.py orphan
   cleanup). The test DB must be up and migrated before that import — see
   the `client` fixture ordering.

3. The FastAPI lifespan must NOT run in tests: it starts APScheduler, the
   TaskManager workers, and startup_cleanup.py which kill -TERMs any
   judge_worker process ON THE WHOLE MACHINE. `TestClient(app)` is used
   WITHOUT a `with` block — starlette only runs lifespan inside the
   context manager. Never write `with TestClient(...)` in this suite.
"""
import json
import os
import pathlib
import sys

assert not any(
    m == "theseus_insight" or m.startswith("theseus_insight.") for m in sys.modules
), "conftest.py must set DATABASE_URL before theseus_insight is imported"

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://theseus:theseus@localhost:5434/theseus_test"
)
TEST_DB_NAME = TEST_DB_URL.rsplit("/", 1)[-1]
# Refuse to run against anything that isn't an expendable test database.
assert TEST_DB_NAME.endswith("_test"), (
    f"Test database name must end with '_test', got {TEST_DB_NAME!r}"
)

os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["DB_POOL_MIN_SIZE"] = "1"
os.environ["DB_POOL_MAX_SIZE"] = "5"
os.environ["DB_POOL_TIMEOUT"] = "10"  # fail fast instead of the 60s default
os.environ["APP_SECRET_KEY"] = "test_secret"
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import psycopg
import pytest

ADMIN_URL = TEST_DB_URL.rsplit("/", 1)[0] + "/postgres"
GOLDEN_DIR = pathlib.Path(__file__).parent / "goldens"

# A deterministic 768-dim embedding pointing along axis 0 / axis 1.
EMB_DIM = 768


def axis_embedding(axis: int, value: float = 1.0) -> list[float]:
    vec = [0.0] * EMB_DIM
    vec[axis] = value
    return vec


def pgvector_literal(vec: list[float]) -> str:
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


@pytest.fixture(scope="session", autouse=True)
def migrated_db():
    """Drop/recreate the test DB and run the production migration chain.

    Running MigrationRunner against an empty database every session IS the
    migration characterization test — it exercises the exact startup path.
    """
    try:
        admin = psycopg.connect(ADMIN_URL, autocommit=True, connect_timeout=5)
    except Exception as exc:  # pragma: no cover
        pytest.exit(
            f"Test database not reachable at {ADMIN_URL}: {exc}\n"
            "Start it with: make test-db",
            returncode=2,
        )
    try:
        admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")
        admin.execute(f"CREATE DATABASE {TEST_DB_NAME}")
    finally:
        admin.close()

    # First theseus_insight import happens here, with a healthy empty DB.
    from theseus_insight.db.migrations import MigrationRunner

    runner = MigrationRunner()
    applied, skipped, issues = runner.run_migrations()
    assert issues == [], f"Migration issues on fresh database: {issues}"
    yield {"applied": applied, "skipped": skipped}


@pytest.fixture(scope="session")
def client(migrated_db):
    """FastAPI TestClient with lifespan deliberately NOT started.

    See module docstring point 3 — never wrap this in `with`.
    """
    from fastapi.testclient import TestClient
    from theseus_insight.main import app

    return TestClient(app)


@pytest.fixture()
def db():
    """Raw psycopg connection for seeding/inspecting, independent of app pools."""
    conn = psycopg.connect(TEST_DB_URL, autocommit=True, row_factory=psycopg.rows.dict_row)
    yield conn
    conn.close()


def _truncate(conn) -> None:
    conn.execute(
        "TRUNCATE papers, logs, tasks RESTART IDENTITY CASCADE"
    )
    conn.execute("DELETE FROM profile_research_interests")
    conn.execute("DELETE FROM paper_profile_scores")
    conn.execute("DELETE FROM research_profiles WHERE is_default = FALSE")


@pytest.fixture()
def empty_db(db):
    """Tables cleared (migration-created Default profile kept)."""
    _truncate(db)
    return db


@pytest.fixture()
def seeded_data(db):
    """Deterministic fixture dataset, inserted with raw SQL.

    Raw SQL on purpose: characterization tests must not depend on the
    repository code that the refactor is about to move.
    """
    _truncate(db)

    papers = [
        # (title, abstract, date, date_run, score, rationale, related, url, embedding)
        ("Alpha Paper", "Transformers for everything.", "2025-01-10", "2025-01-11",
         9.0, "highly relevant", True, "https://example.org/alpha",
         pgvector_literal(axis_embedding(0))),
        ("Beta Paper", "Graph methods for citation analysis.", "2025-01-05", "2025-01-06",
         5.0, "somewhat relevant", False, "https://example.org/beta",
         pgvector_literal(axis_embedding(1))),
        ("Gamma Paper", "Survey of obsolete techniques.", "2025-01-01", "2025-01-02",
         2.0, "not relevant", False, "https://example.org/gamma", None),
    ]
    for row in papers:
        db.execute(
            """
            INSERT INTO papers (title, abstract, date, date_run, score, rationale,
                                related, url, embedding, embedding_model)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'fake-model')
            """,
            row,
        )

    default_profile = db.execute(
        "SELECT id FROM research_profiles WHERE is_default = TRUE"
    ).fetchone()
    test_profile = db.execute(
        """
        INSERT INTO research_profiles (name, description, color, tags, is_active, is_default)
        VALUES ('Test Profile', 'fixture profile', '#ff0000', '["ml"]'::jsonb, TRUE, FALSE)
        RETURNING id
        """
    ).fetchone()

    db.execute(
        """
        INSERT INTO paper_profile_scores (paper_id, profile_id, score, related, rationale, judge_model)
        VALUES (1, %(pid)s, 8, TRUE, 'fixture: on-topic', 'fake-judge'),
               (2, %(pid)s, 3, FALSE, 'fixture: off-topic', 'fake-judge')
        """,
        {"pid": test_profile["id"]},
    )

    return {
        "paper_ids": [1, 2, 3],
        "default_profile_id": default_profile["id"] if default_profile else None,
        "test_profile_id": test_profile["id"],
    }


@pytest.fixture(scope="session")
def golden():
    """Golden-file comparator.

    Missing golden -> written and the test passes (review before committing).
    UPDATE_GOLDENS=1 -> rewrite all goldens.
    """

    def check(name: str, value):
        path = GOLDEN_DIR / f"{name}.json"
        serialized = json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"
        if os.environ.get("UPDATE_GOLDENS") == "1" or not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(serialized)
            print(f"[golden] wrote {path.name}")
            return
        expected = path.read_text()
        assert serialized == expected, (
            f"Golden mismatch for {name!r}. If the change is intentional, "
            f"rerun with UPDATE_GOLDENS=1 and review the diff."
        )

    return check
