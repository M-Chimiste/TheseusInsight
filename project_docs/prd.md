Product Requirements Document

Agentic Researcher (Local-First, LLM-Agnostic Edition)

⸻

1 — Purpose

Build a stand‑alone “Agentic Researcher” module that automates literature reviews by:
	1.	Starting local‑first – querying an existing SQLite database of full‑text papers you already host.
	2.	Iteratively expanding outward – invoking configurable external search tools (e.g., arXiv, Semantic Scholar) only when local sources are exhausted or insufficient.
	3.	Remaining LLM‑agnostic – all model calls go through a single pluggable interface (call_llm()), letting operators swap Hugging Face, Ollama, vLLM, or any cloud API without code changes.
	4.	Producing structured outputs – summaries, citations, and a justification trail saved back into the same SQLite DB for downstream analytics.

⸻

2 — Scope

	In‑Scope	Out‑of‑Scope
Core iterative literature‑review loop	Yes	
Local SQLite search & full‑text retrieval	Yes	Other DBs (can be added via adapters)
External search adapters for arXiv & Semantic Scholar	Yes (baseline)	Paid or unpublished APIs (e.g., Elsevier Scopus)
Generic LLM interface (call_llm)	Yes	Fine‑tuning or training LLMs
Lightweight CLI & Python SDK	Yes	Full Web UI (future)
Basic PDF ingestion (if text missing)	Yes	Sophisticated OCR/figure extraction


⸻

3 — Personas

Persona	Goal	Pain Points Today
Research Engineer (primary)	Embed automated lit‑review into an existing knowledge‑graph pipeline.	Manually cobbling multiple scripts; vendor‑lock with OpenAI.
Data Scientist	Rapidly surface the most relevant papers in a niche domain.	Slow academic search, context‑switching across tools.
Backend Developer	Maintain a single SQLite source‑of‑truth.	Inconsistent data schemas across ingestion pipelines.


⸻

4 — User Stories
	1.	Local First
As a Research Engineer, when I pose a research question, the agent should first surface top‑K matches already stored in my SQLite DB with similarity scores.
	2.	Iterative Expansion
As a Data Scientist, if local results are below a relevancy threshold or count, the agent should automatically query external repositories and ingest new papers.
	3.	Structured Trace
As a Developer, I need every agent action (prompt, tool call, paper IDs) recorded so I can reproduce or audit decisions.
	4.	Model Swap
As an Ops Engineer, I can point call_llm() to a new model endpoint via config without touching business logic.

⸻

5 — Functional Requirements

Ref	Requirement
FR‑1	Provide a CLI command agentic-research "query" that triggers a full research run.
FR‑2	Implement LocalSearchTool: vectorize the query via a configurable embedding model, compute cosine similarity over stored embeddings, and lazily cache new embeddings.
FR‑3	The agent loop must parse fenced commands SUMMARY <query>, FULL_TEXT <paper_id>, and ADD_PAPER <id> and dispatch each to the correct handler.
FR‑4	On ADD_PAPER with an external ID, download the PDF, parse it via SpacyLayoutDocProcessor → FlatMarkdownParser, and store the resulting Markdown in papers.text.
FR‑5	Terminate when collected summaries ≥ num_papers_target or iterations ≥ max_steps.
FR‑6	Persist results in lit_reviews (research_question, summary_json, trace_json).
FR‑7	Provide Python SDK helpers run_lit_review(question) and search_local(query).
FR‑8	Accept a declarative model_config (JSON / YAML) listing a boss model and a pool of worker models.
FR‑9	All LLM calls must route through the existing ModelFactory.invoke() using parameters from model_config.
FR‑10	During a run, the agent may dynamically choose worker models; each decision is recorded in trace_json.
FR‑11	PDF ingestion uses SpacyLayoutDocProcessor and FlatMarkdownParser to produce Markdown stored in papers.text.
FR‑12	Expose real‑time log streaming via WebSocket or SSE; messages include task_id, timestamp, phase, progress percentage, and free‑text message.
FR‑13	UI: Add a “Research Agent” page (Dashboard + Sidebar) showing live logs, progress, and final summary.
FR‑14	Every run creates a tasks row (task_type = 'research_agent') and appears in job history.
FR‑15	While any research_agent task is processing, the scheduler must block creation/execution of newsletter or podcast tasks.
FR‑16	Settings UI: Add panel to select the boss model (single‑select) and manage worker models (multi‑select).
FR‑17	Persist the configuration in settings under key research_agent_model_config (JSON).
FR‑18	Backend: Implement POST /api/research-agent/run → { taskId }; GET /api/tasks/{taskId}; and WS /ws/research-agent/{taskId} for streaming status.
FR‑19	Agent must POST webhook progress updates to /api/research-agent/webhook; backend stores interim state so the UI can restore a run after page reload.

6 — Non‑Functional Requirements — Non-Functional Requirements — Non‑Functional Requirements

Category	Requirement
Extensibility	New search adapters follow BaseSearchTool ABC (find_papers_by_str, retrieve_full_text).
Portability	Runs on macOS/Linux; pure‑Python ≥ 3.10; no system binaries except poppler (optional) for PDF text.
Performance	Local search of 10 000 papers ≤ 2 s on M1 laptop.
Observability	Emit JSON logs (debug, info, warning, error) and optional OpenTelemetry spans.
Security	No outbound net unless tool adapter invoked; all keys stored via environment variables.
Licensing	Apache‑2.0 or MIT; external libraries must be compatible.


⸻

7 — System Architecture

flowchart TD
    subgraph Agentic Researcher
        A[CLI / SDK] -->|research question| B[Agent Loop]
        B --> C[LocalSearchTool]
        B -->|fallback| D[(External Search\nAdapters)]
        C --> E[SQLite DB\npapers, embeddings]
        D --> E
        B --> F[call_llm()]
        F -. env -.> M[Local/Remote LLM]
        F -. env -.> N[Embedding Model]
        B --> G[Results Persister]
        G --> H[SQLite DB\nlit_reviews]
    end


⸻

8 — Data Model (SQLite + sqlite‑vec)

This project plugs directly into the Theseus Insight v1.0 database you provided. All tables below already exist in data/theseus.db and are therefore authoritative. Only one new table (lit_reviews) is added by the Agentic Researcher module.

⸻

8.1 Physical Characteristics

Property	Value	Notes
Engine	SQLite 3 + sqlite‑vec extension	Vector similarity via VECTOR column type
File	data/theseus.db	Path supplied via DATABASE_URL
Connection API	Python sqlite3	No external driver required


⸻

8.2 Core Entity Relationship

model_providers 1 ────< models
                        ▲
 papers ───────┐
 newsletters   ├── stored artefacts
 podcasts ─────┘
 settings  (key/value)
 logs      (append‑only)
 tasks     (async state)

Foreign‑key: models.provider_id → model_providers.id (ON DELETE CASCADE when ported to Postgres).

⸻

8.3 Table Specifications (Authoritative)

8.3.1 papers

Column	Type	Constraints	Description
id	INTEGER	PK AUTOINCREMENT	Surrogate key
title	TEXT	NOT NULL	Paper title
abstract	TEXT	NOT NULL	Abstract text
date	DATE	NOT NULL	Publication date
date_run	DATE	NOT NULL	Processing date
score	REAL	 –	Relevance score assigned by LLM/agent
rationale	TEXT	 –	LLM explanation of relevance
related	BOOLEAN	DEFAULT FALSE	TRUE if on‑topic
cosine_similarity	REAL	 –	Embedding similarity to seed query
url	TEXT	UNIQUE	PDF or landing‑page URL
embedding_model	TEXT	 –	Name/version of embedding model used
embedding	VECTOR	 NULLABLE	sqlite‑vec vector (e.g. 384‑d REAL)
search_vector	TSVECTOR	generated	Full‑text index (title + abstract)
title_vector	TSVECTOR	generated	Title‑only index
abstract_vector	TSVECTOR	generated	Abstract‑only index

Agentic Researcher behaviour
• Reads existing rows first (“local‑first” search).
• Computes & caches embedding for any paper where it is NULL.
• May update score, rationale, related, and cosine_similarity during each run.

8.3.2 logs

(append‑only execution and error log)

Column	Type	Constraints	Description
id	INTEGER	PK	
task_id	TEXT	NOT NULL	Associated async job
status	TEXT	NOT NULL	Human‑readable message
datetime_run	TIMESTAMP	 NULLABLE	Optional timestamp

8.3.3 newsletters

Column	Type	Constraints	Description
id	INTEGER	PK AUTOINCREMENT	
content	TEXT	NOT NULL	Markdown newsletter body
start_date	DATE	NOT NULL	First paper date included
end_date	DATE	NOT NULL	Last paper date included
date_sent	DATE	NOT NULL	Email dispatch date

8.3.4 podcasts

Column	Type	Constraints	Description
id	INTEGER	PK AUTOINCREMENT	
title	TEXT	NOT NULL	Episode title
date	DATE	NOT NULL	Generation date
script	TEXT	NOT NULL	JSON dialogue
description	TEXT	NOT NULL	Show‑notes

8.3.5 settings (key‑value)

Column	Type	Constraints	Description
key	TEXT	PK	Unique setting name
value	TEXT	NOT NULL	JSON or plain text value

8.3.6 model_providers

Column	Type	Constraints	Description
id	INTEGER	PK AUTOINCREMENT	
name	TEXT	NOT NULL UNIQUE	Provider label (openai, ollama)

8.3.7 models

Column	Type	Constraints	Description
id	INTEGER	PK AUTOINCREMENT	
provider_id	INTEGER	NOT NULL FK → model_providers.id	
name	TEXT	NOT NULL	Model identifier
config_json	TEXT	NULLABLE	Provider‑specific cfg
UNIQUE	(provider_id, name)	Prevents duplicates	

8.3.8 tasks

Column	Type	Constraints	Description
task_id	TEXT	PK	Async job id
task_type	TEXT	NOT NULL	Task category (newsletter, podcast, visualizer, research_agent)
status	TEXT	NOT NULL	processing 
config_json	TEXT	NOT NULL	Input parameters (JSON)
start_time	TIMESTAMP	NOT NULL	Start timestamp
end_time	TIMESTAMP	NULLABLE	End timestamp
error	TEXT	NULLABLE	Error message (if failed)
result_json	TEXT	NULLABLE	Result payload
progress	DOUBLE PRECISION	DEFAULT 0	Percentage complete
current_step	TEXT	NULLABLE	Step name
message	TEXT	NULLABLE	Human‑readable info

8.3.9 lit_reviews (NEW – created by Agentic Researcher)

Column	Type	Constraints	Description
id	INTEGER	PK AUTOINCREMENT	
research_question	TEXT	NOT NULL	Original user prompt
summary_json	TEXT	NOT NULL	JSON list [{paper_id, summary, rationale}]
trace_json	TEXT	NOT NULL	Full audit trail of prompts, tool invocations
created_ts	DATETIME	DEFAULT CURRENT_TIMESTAMP	


⸻

8.4 Performance & Indexing Notes
	•	Vector indexing is provided by sqlite‑vec; the embedding column on papers automatically gets a compatible ANN index.
	•	Primary keys create B‑tree indexes.  Additional helpful indexes:

CREATE INDEX IF NOT EXISTS idx_papers_date        ON papers(date);
CREATE INDEX IF NOT EXISTS idx_papers_score       ON papers(score DESC);
CREATE INDEX IF NOT EXISTS idx_podcasts_date      ON podcasts(date);
CREATE INDEX IF NOT EXISTS idx_newsletters_dates  ON newsletters(start_date, end_date);


⸻

8.3 — API Integration (Theseus Insight Backend)

The Research Agent module must integrate with the existing FastAPI contract fileciteturn3file0 and mirror the WebSocket patterns already used by newsletter and podcast pipelines fileciteturn3file1.

Method	Path	Purpose
POST	/api/research-agent/run	Start a new Research Agent run; payload includes researchQuestion, optional modelConfigOverride. Returns { taskId } (HTTP 202).
WS	/ws/research-agent/{taskId}	Stream RunStatus JSON frames until completion/failure. Identical schema to /ws/newsletter/{taskId}.
GET	/api/tasks/{taskId}/status	Re‑use existing status endpoint for polling.
GET	/api/runs	The run appears with pipeline_type: 'research_agent', enabling history view in Dashboard.
GET/PUT	/api/settings/research-agent-model-config	CRUD for boss/worker model definitions (maps to settings.research_agent_model_config).

The frontend contract table in Theseus Insight will be extended accordingly so React components can call these routes without special‑case code. fileciteturn3file1

⸻

9 — Key Algorithms

9.1 Local Search

embed_query ← EmbeddingModel(q)
for each paper without embedding: compute & store embedding
similarities ← cosine(embed_query, paper.embeddings)
return top_k by similarity desc

9.2 Agent Loop (Literature Review Phase)
	1.	Prompt role “PhDStudent” with system + user context.
	2.	Parse LLM response for fenced code triple‑backtick commands.
	3.	Dispatch:
	•	SUMMARY → LocalSearchTool.find_papers_by_str
	•	FULL_TEXT → LocalSearchTool.retrieve_full_text
	•	ADD_PAPER → Either copy from local DB or fetch via external adapter.
	4.	Feedback results to LLM.
	5.	Repeat until stop criteria, then call PhDStudentAgent.format_review().

⸻

10 — Configurable Parameters (config.yaml)

embeddings:
  model: sentence-transformers/all-MiniLM-L6-v2
  cache_dir: ~/.cache/agentic_research/embeddings

agent:
  llm_backend: llama37b-quantized
  temperature: 0.4
  max_steps: 10
  num_papers_target: 5

search:
  local_top_k: 12
  external_backends:
    - type: arxiv
      max_results: 20
    - type: semanticscholar
      max_results: 20


⸻

11 — Open Interfaces

Interface	Signature	Notes
call_llm	def call_llm(prompt:str, model:str, temperature:float)->str	Must be provided by host app; can raise LLMError.
BaseSearchTool	find_papers_by_str(query:str, N:int)->str`retrieve_full_text(id:str	int)->str`
CLI	agentic-research "<question>" --config conf.yaml	Streams JSON events or table output.


⸻

12 — Testing & Validation

Layer	Test Case
Unit	LocalSearchTool returns identical top‑1 for deterministic query.
Agent Loop	With mock call_llm emitting scripted commands, collects exactly 5 summaries in ≤ 3 steps.
Integration	End‑to‑end run on sample DB of 50 PDFs succeeds with no external network.
Regression	Swapping embedding model (e.g., E5‑v2) does not raise errors; similarity distribution sanity‑checked.


⸻

13 — Metrics / KPIs

Metric	Target
Local hit ratio (#papers from local ÷ total)	≥ 70 % for domain where DB is rich
Average iterations	≤ 6 per query
Latency (cold)	≤ 20 s to first summary
Agent reproducibility	Running twice with same seed produces identical paper list


⸻

14 — Milestones

Date	Deliverable
T + 2 w	MVP: LocalSearchTool + embedding cache; CLI prints top‑K.
T + 4 w	Complete Agent Loop w/ mock call_llm; unit tests green.
T + 6 w	External arXiv & Semantic Scholar adapters; PDF ingestion pipeline.
T + 7 w	LLM‑agnostic interface, config file, and Python SDK published (v0.1).
T + 8 w	Hardening pass, docs, release candidate v1.0.


⸻

15 — Risks & Mitigations

Risk	Impact	Mitigation
Embedding model version drift	Inconsistent similarity outcomes	Pin default model + checksum; allow override.
External API rate limits	Agent stalls	Back‑off & cache results; prefer local.
LLM hallucination of wrong IDs	Wrong papers fetched	Validate IDs against regex and existence in DB/API.


⸻

16 — Appendix A – Example Prompt Template

System:
You are a diligent PhD candidate conducting a literature review.

User:
Research topic: "{{question}}"
Phase: "{{phase}}" (step {{step}})
Known summaries so far:
{{summaries_block}}
Instructions:
- If you need more papers, respond with ```SUMMARY <search query>```.
- To inspect full text of a paper you’ve seen, respond with ```FULL_TEXT <paper_id>```.
- Once satisfied with the review, respond with ```COMPLETE``` followed by a bullet-point summary.


