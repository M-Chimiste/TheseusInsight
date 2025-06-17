# Mind‑Map Explorer – Phased Implementation Plan

*Role:* **LLM Software‑Engineer Agent** (single developer)
*Context:* All dependencies & local dev environment are pre‑provisioned. SQLite+`sqlite‑vec` DB is backed‑up and ready.
*Goal:* Deliver the Mind‑Map Explorer feature set described in the PRD, fully integrated with the existing **PapersHistory** library.

---

## Phase 1 – Core Data Services

| Task                                                                                  | Details                                                                                       |
| ------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| 1.1 Data access layer                                                                 | Create `paper_repository.py` (async, cached).                                                 |
| `get_paper(id)`, `search_papers(q)`, `nearest_embeddings(vec, k)` using `sqlite‑vec`. |                                                                                               |
| 1.2 Embedding service                                                                 | Wrap existing embedding models behind `EmbeddingProvider` contract (factory pattern).         |
| 1.3 LLMFactory skeleton                                                               | Define `generate(task: str, prompt: str, **kw) → str` and providers registry (local, remote). |
| **Deliverable**                                                                       | Unit tests: nearest‑neighbour returns expected papers; LLMFactory returns mock output.        |

---

## Phase 2 – LangGraph Pipeline

| Task                                                          | Details                                                                   |
| ------------------------------------------------------------- | ------------------------------------------------------------------------- |
| 2.1 State schema                                              | Implement `MMState` TypedDict.                                            |
| 2.2 Nodes                                                     | `SelectSeed`, `EmbedSeed`, `Retriever`, `SummarisePaper`, `BuildMindMap`. |
| Summarisation uses `LLMFactory` with generic prompt template. |                                                                           |
| 2.3 Runner & tests                                            | Bundle as `mindmap_graph.py`; write integration test with a known seed.   |
| **Deliverable**                                               | `pytest -k mindmap_graph` passes; JSON output validates schema.           |

---

## Phase 3 – Backend API & Streaming

| Task                  | Details                                                              |
| --------------------- | -------------------------------------------------------------------- |
| 3.1 FastAPI endpoints | `/expand` (WebSocket/SSE), `/parse-pdfs`, `/paper/{id}`.             |
| 3.2 Stream adapter    | Transform LangGraph snapshots → JSON patch messages.                 |
| 3.3 Security          | Add API key env toggle for remote‑LLM routes.                        |
| **Deliverable**       | Swagger docs live; local WebSocket demo streams nodes incrementally. |

---

## Phase 4 – React Integration

| Task                  | Details                                                                           |
| --------------------- | --------------------------------------------------------------------------------- |
| 4.1 Hook export       | Implement `useMindMap(paperId)` inside PapersHistory; opens explorer modal/panel. |
| 4.2 Canvas v1         | Use React Flow for drag/zoom; render nodes/edges.                                 |
| 4.3 Side Drawer       | Metadata, “Expand node”, “Parse PDF” button.                                      |
| 4.4 Streaming reducer | Consume JSON patches; optimistic updates.                                         |
| **Deliverable**       | Manual E2E demo: open paper → interactive map in browser.                         |

---

## Phase 5 – On‑Demand PDF Parsing&#x20;

| Task                                 | Details                                                   |
| ------------------------------------ | --------------------------------------------------------- |
| 5.1 Integrate MarkdownitDocProcessor | Batch parse up to 20 PDFs; extract sections.              |
| 5.2 Embedding & storage              | Insert into `paper_fulltext`, compute section embeddings. |
| 5.3 UI feedback                      | Batch queue modal, per‑PDF progress.                      |
| **Deliverable**                      | Parsed sections searchable; UI highlights new insights.   |

---

## Phase 6 – Filtering, Search & Export

| Task                  | Details                                               |
| --------------------- | ----------------------------------------------------- |
| 6.1 Filter panel      | Year slider, venue multiselect, similarity threshold. |
| 6.2 Keyword highlight | Client‑side search over currently loaded nodes.       |
| 6.3 Export            | PNG via `html‑to‑image`; JSON snapshot download.      |
| **Deliverable**       | Features accessible & pass smoke tests.               |

---

## Phase 7 – Docs & Hand‑off

| Task                  | Details                                              |
| --------------------- | ---------------------------------------------------- |
| 7.1 Docs              | Update `README`, add developer guide, API reference. |
| 7.2 Deployment script | `Makefile` target: `make dev` & `make prod`.         |
| **Deliverable**       | Tag `v1.0.0` released; hand‑off notes shared.        |

---
