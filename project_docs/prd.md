# Topic Evolution & Trend-Forecast Dashboard PRD

## 1\. Summary

Build an automated dashboard that surfaces **emerging machine-learning topics, their evolution over time, and short-term forecasts** based on the papers harvested by Theseus Insight.  The dashboard helps researchers quickly understand where the field is heading and identify topics worth exploring.

## 2\. Problem Statement

ML researchers spend significant time scanning ArXiv, Twitter, blog posts, and conference proceedings to track new trends.  Theseus Insight already collects and embeds thousands of papers but offers no longitudinal view—users see only a snapshot.  Providing temporal visualisations and predictive signals will turn raw paper feeds into **actionable strategic insight**.

## 3\. Goals & Success Metrics

| Goal | Metric |
| :---- | :---- |
| Surface top emerging topics | Top-10 topic chart auto-updates daily |
| Show historical popularity curves | At least 12 months of back-filled data rendered within 2 s |
| Forecast near-term growth | ±15 % MAE on 3-month topic frequency prediction benchmark |
| Drive usage | ≥30 % of weekly active users open the Trends page in first 3 months |

## 4\. Non-Goals

* Predict paper *citations* (complex, long-term).  
* Support non-ML domains (biology, medicine, etc.).

## 5\. User Stories

1. **Sarah, PhD student** – wants to see "Diffusion models" popularity over the last 18 months to justify her research direction.  
2. **Alex, ML engineer** – needs a weekly digest of rising topics (e.g., "LLM alignment") for roadmap planning.  
3. **Conference reviewer** – compares saturation levels of "Graph Neural Networks" vs "Transformers" to calibrate acceptance criteria.  
4. **Maria, a research lead,** spots 'Federated Learning for Edge AI' is a surging topic. She clicks to generate a mind-map of its core papers to understand the sub-domains, then generates a one-off newsletter digest to share with her team.

## 6\. Functional Requirements

### 6.1 Data Pipeline

* **Nightly Scheduled Job** — A nightly APScheduler job inside the existing backend container clusters *all new* paper embeddings by week/month/quarter.  The same code path can also be triggered **on-demand** via the `POST /api/trends/recompute` endpoint.
* Use **BERTopic** (HDBSCAN + c-TF-IDF) for topic extraction with configurable granularity.  
* Persist `topics` table: `(topic_id, label, keywords, created_at)` and `topic_metrics` table: `(topic_id, period, doc_count, avg_embedding)`.  
* Optional: Vectorise topic centroids for similarity queries.  
* Ensure new tables are covered by the DB creation scripts **and** import/export utilities so older exports continue to load without errors.

### 6.2 Forecasting Module

* Apply **Prophet** (Python package) as the primary forecasting model for each topic.  
* Store 1-, 3-, 6-month forecast values (`forecast_doc_count`).  
* Trigger re-training nightly (as part of the scheduled job) or ad-hoc via the Admin endpoint.

### 6.3 API Endpoints (FastAPI)

| Method | Route | Purpose |
| :---- | :---- | :---- |
| `GET` | `/api/trends` | List top *N* topics with current metrics |
| `GET` | `/api/trends/{topic_id}` | Historical curve \+ forecast \+ representative papers |
| `POST` | `/api/trends/recompute` | (Admin) Force pipeline rerun |
| `GET` | `/api/papers` | Add `?topic_id=` query param for filtering |
| `POST` | `/api/mindmap/expand` | Add `?topic_id=` to seed from a topic |
| `POST` | `/api/newsletter/generate` | Add `?topic_id=` to source papers from a topic |

### 6.4 React UI

* New **"Trends"** page accessible from sidebar.  
* Components:  
  * Topic heat-map grid (sparkline + growth %).  
  * Detail drawer with interactive line chart (**D3**), key papers list, and action buttons ("Create Mind-Map", "Generate Newsletter").  
  * Configurable keyword trendlines showing popularity over weeks (similar to financial charts like candlestick charts)  
  * Filter controls: date range, min doc count, include sub-topics.  
  * Search for specific topics  
* **Component Updates:**  
  * `PaperCard.tsx` / `PaperRowCard.tsx`: Display topic tags (e.g., `LLM Alignment 🔥`) that link to the Trends dashboard.  
  * `Papers.tsx`: Add "Filter by Topic" and "Sort by Trend" controls.

### 6.5 Notifications

* Optional weekly email/webhook summarising top 3 surging topics. Job should be added as part of the newsletter pipeline as its own section.

## 7\. Integration with Existing Features

### 7.1 Research Library & Search

* **From Trends to Papers:** The trend detail view will list representative papers. A button ("Explore all papers") will link to the Research Library, pre-filtered for that topic.  
* **From Papers to Trends:** Paper cards will display clickable topic tags, allowing users to pivot from a specific paper to its broader trend context.  
* **Trend-Aware Search:** Users can filter their library by topic and sort results by trend dynamics (e.g., "Surging First") to surface papers in accelerating fields.

### 7.2 Mind-Map Explorer

* **Launch Mind-Map from Topic:** A button on the trend detail page will generate a mind-map seeded from the topic's most representative papers, providing an instant view of its intellectual structure.  
* **Trend-Annotated Mind-Maps:** Nodes on the mind-map canvas can be visually annotated (e.g., with a colored halo or icon) to indicate the trendiness of the topics they belong to.

### 7.3 Content Generation (Newsletters & Podcasts)

* **"Trend Digest" Generation:** Users can generate a one-off newsletter or podcast directly from a trend page, using its core papers as the source material for a focused summary.

## 8\. Non-Functional Requirements

* End-to-end pipeline completes \<15 min for 1.5 M papers.  
* Dashboard loads \<2 s P95, even on low-spec laptops.  
* Forecast accuracy logged; auto-alert if MAE \>30 %.

## 9\. Technical Approach

1. **Batch Processor** (`theseus_insight/data_processing/trends.py`) runs as a **nightly APScheduler job** *and* can be invoked on-demand via `/api/trends/recompute`.  
2. Re-use existing embedding store → group by calendar period, run BERTopic.  
3. Append results into **Postgres** tables (`topics`, `topic_metrics`) and ensure import/export scripts handle the new data gracefully.  
4. Expose via new router `api/routers/trends.py` (similar style to `mindmap.py`), updating existing routers to handle topic-based actions.  
5. Frontend: Create `pages/Trends.tsx`, update existing components (`PaperCard.tsx`, `Papers.tsx`) to display and link trend data.  Leverage **D3** for visualisations; state managed via existing context hooks.

## 10\. Open Questions / Risks

* **Topic Granularity** – Automatic vs manual merging of similar clusters?  
* **Model Dependencies** – BERTopic requires HDBSCAN & Prophet requires CmdStan; ensure wheels/binaries available for Apple Silicon and are sized appropriately for Docker layers.  
* **Database Size** – Use existing Postgres and PG Vector implementation.  
* **UI Complexity** – Adding topic filters and sorting to the search page must be done without cluttering the interface.

## 11\. Milestones & Timeline (tentative)

| Phase | Milestone |
| :---- | :---- |
| 1 | Schema design & Alembic migration |
| 2 | Back-fill pipeline \+ unit tests |
| 3 | Forecast module & metrics logging |
| 4 | API endpoints & Swagger docs (including integrations) |
| 5 | React UI (MVP Dashboard) |
| 6 | React UI (Integrations with existing pages) |
