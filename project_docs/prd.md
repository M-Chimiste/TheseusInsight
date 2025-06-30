# PRD: Migration from SQLite to PostgreSQL 14 with pgvector

## 1 – Background & Motivation
Theseus Insight currently relies on a local SQLite database (with the `sqlite_vec` extension for vector search). While SQLite is excellent for a lightweight, zero-config experience, it becomes a bottleneck when the dataset grows or when multiple processes need concurrent read/write access. PostgreSQL 14 is the current LTS release and, in conjunction with the `pgvector` extension, offers: 

* Native vector similarity search that scales horizontally.
* Mature full-text-search (FTS) capabilities and advanced indexing options.
* Robust concurrency handling, strong ACID guarantees, and a path toward eventual sharding/cloud-hosted solutions.

Migrating to PostgreSQL will unlock production-grade scalability while preserving the developer-friendly experience we enjoy today.

---

## 2 – Goals (✅ = success criteria)
1. **Seamless Migration Path** – Provide a one-click script (or CLI) that converts an existing SQLite database into a PostgreSQL database with **zero data loss**. ✅
2. **Feature Parity (1:1 Compatibility)** – All current data access APIs (`PaperDatabase` methods and router endpoints) keep the same signatures and behaviour. ✅
3. **Easy On-boarding** – New users can spin up the full stack (API, Postgres, pgvector) with a *single* docker-compose command or `./scripts/install-and-start.sh`. ✅
4. **Containerised Infrastructure** – Docker images/services for `postgres:14-alpine` + `pgvector` are supplied and pre-configured. ✅
5. **Backward Compatibility** – Import/export utilities migrate data **once** from the old SQLite format; SQLite will no longer be a supported runtime backend after migration. ✅
6. **Single Engine** – The application codebase runs **exclusively on PostgreSQL 14** (with pgvector). No hybrid or fallback mode. ✅

---

## 3 – Non-Goals
* Re-architecting domain logic or changing existing API contracts beyond what is strictly required for PostgreSQL compatibility.
* Sharding/High-availability Postgres setups (can be tackled later).
* Supporting SQLite as a runtime backend after the migration is **out of scope** (we will remove it).

---

## 4 – Personas & Use-Cases
1. **New Developer** – Clones the repo, runs one command, and gets a local Postgres with pgvector seeded.
2. **Existing User** – Has months of data in SQLite; runs a migration script to upgrade in-place (or side-by-side) without schema edits.
3. **DevOps Engineer** – Deploys Theseus Insight in staging/production via Docker/Kubernetes using an external Postgres service.
4. **Data Scientist** – Executes complex vector + keyword queries benefiting from pgvector performance.

---

## 5 – Assumptions
* PostgreSQL 14 is available (locally via Docker or remote).
* `pgvector` extension is installable via `CREATE EXTENSION IF NOT EXISTS pgvector;`.
* We can rely on standard extensions such as `pg_trgm` or `unaccent` for FTS if needed.
* Python drivers: `psycopg[binary]==3.x` will be our default Postgres driver.
* We *may* introduce an ORM (SQLAlchemy) but will first prefer a minimal adapter layer to keep the diff small.

---

## 6 – Functional Requirements
| ID | Requirement |
|-----|-------------|
| FR-1 | Provide `docker-compose.postgres.yml` with a Postgres 14 service, pre-installed pgvector, correct locale/encoding. |
| FR-2 | Add an init script that creates the database, required schemas, tables, indexes, and the `vector` columns mirroring the existing schema. |
| FR-3 | Replace all SQLite FTS5 queries with PostgreSQL full-text search (`tsvector`, `GIN/GIST` indexes). |
| FR-4 | Replace `sqlite_vec` cosine-similarity calls with `pgvector` equivalents (`embedding <=> query_embedding`). |
| FR-5 | Implement a **migration CLI** (`python -m scripts.migrate_sqlite_to_postgres <sqlite_path> <connection_url>`) that: a) introspects SQLite schema; b) creates equivalent tables in Postgres; c) batches data insertions; d) rebuilds indexes. |
| FR-6 | Update import/export utilities (`db_export.py`, `db_import.py`) so they can **read SQLite and write Postgres** during migration, then operate solely on Postgres afterwards. |
| FR-7 | Introduce a configuration layer exposing Postgres connection details (host, port, user, password, database). *No engine toggle will remain after migration.* |
| FR-8 | Refactor `PaperDatabase` to target Postgres-only queries while preserving the external API surface. |
| FR-9 | Automated tests proving the same query results between engines for a representative dataset. |
| FR-10 | Update CI pipeline to spin up Postgres service & run tests against it. |

---

## 7 – Non-Functional Requirements
* **Performance** – Vector search latency ≤ 200 ms for 100k embeddings (128-D) on a 2-CPU local machine.
* **Scalability** – Schema & indexes should comfortably handle 5 million papers.
* **Reliability** – Migration tool aborts on first error, provides resumable checkpoints.
* **Security** – Credentials stored via env vars or Docker secrets; no hard-coded passwords.
* **Observability** – DB connection pool metrics exposed via existing `/metrics` endpoint (future work).
* **Operational Overhead** – Postgres requires memory/disk; users with ultra-light needs will still be able to *export* their data but must run Postgres going forward.

---

## 8 – Acceptance Criteria
1. Running `make dev` (or script) on a clean checkout starts API & Postgres and passes the full test suite.
2. Migrating a real SQLite DB (≥ 10k papers) results in identical record counts per table and identical random sample queries.
3. Vector similarity & hybrid search endpoints return *numerically close* (±0.001 cosine) results versus SQLite for the same inputs.
4. Documentation (`docs/installation_README.md`) updated to reflect new prerequisites.

---

## 9 – Risks & Mitigations
* **Data Type Mismatches** – Certain columns (`BOOLEAN`, `BLOB`, `TEXT`) differ; we will run automated validation after import.  
* **FTS Ranking Differences** – PostgreSQL's ranking differs from SQLite's `bm25`; we will normalise scores or offer deterministic order when equal.  
* **Migration Downtime** – Provide side-by-side migration to minimise downtime, with a final cut-over flag.

---

## 10 – Open Questions
1. (Removed – decision made to deprecate SQLite entirely.)
2. Which ORM/driver strategy: raw SQL (`psycopg`), lightweight query builder (`SQLModel`), or full SQLAlchemy Core?
3. Do we want to support cloud Postgres providers out-of-the-box (AWS RDS, Supabase) and how do we manage SSL certs?
4. Should we version-control DB migrations via Alembic for future schema changes?

---

## 11 – Phased Implementation Plan

### Phase 0 – Planning & PRD *(current)*
* Draft & sign off PRD, collect feedback, freeze scope.

### Phase 1 – Infrastructure Setup (⏱ 1-2 days)
* Add `docker-compose.postgres.yml` (Postgres 14 + `pgvector`).
* Provide `scripts/setup_postgres.sh` to create DB, user, extensions.
* Update docs + CI to spin up the new service.

### Phase 2 – Abstraction Layer (⏱ 2-3 days)
* Refactor `PaperDatabase` and related modules to use `psycopg` / Postgres-specific SQL. Remove SQLite-specific logic (`_check_sqlite_vec`, FTS5 calls, etc.).
* Ensure unit tests cover the new Postgres code path end-to-end.

### Phase 3 – Schema Translation & Migration Tooling (⏱ 3-4 days)
* Write SQL schema for Postgres mirroring tables, constraints, indexes.
* Map FTS5 → `tsvector` columns & triggers.
* Implement CLI migration script with chunked inserts & progress bar.
* Test migration on sample dataset, include validation step.

### Phase 4 – Feature Parity Updates (⏱ 3-5 days)
* Re-implement vector similarity queries using `pgvector` syntax.
* Replace FTS queries with `to_tsvector`, `plainto_tsquery` or ranked `websearch_to_tsquery`.
* Ensure hybrid search weighting logic matches current behaviour.

### Phase 5 – Import/Export Enhancements (⏱ 1-2 days)
* Extend existing `db_export.py` / `db_import.py` to detect engine & use COPY for Postgres.
* Add option to export as JSONL for portability.

### Phase 6 – DX & Documentation (⏱ 1 day)
* Update `README.md`, `docs/*_README.md`, and `scripts/install-*`.
* Provide quick-start video/gif (optional).

### Phase 7 – Backward Compatibility & Deprecation (⏱ 0.5 day)
* Delete residual SQLite code, scripts, and env flags. Update docs to state Postgres is **mandatory** as of this release.

### Phase 8 – Final Testing & Release (⏱ 1 day)
* Regression testing across all endpoints (API + UI).
* Performance benchmarks vs SQLite.
* Tag release `vX.Y.0` and announce migration guide.

_Total estimated effort: **~12-17 person-days**._

---

## 12 – Next Steps
1. Circulate this PRD for feedback (contributors & stakeholders).
2. Address open questions & lock down decisions (ORM, deprecation strategy).
3. Kick-off Phase 1 once approved.
