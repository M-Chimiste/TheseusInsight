Research Agent — Step‑by‑Step Implementation Plan

This plan maps directly to Functional Requirements (FR‑1 → FR‑19) in the PRD and assumes the Theseus Insight application is already cloned with all dependencies installed.

⸻

Phase 1 — Data‑Layer Foundations

Step	Action	Output
1.1	Extend tasks enum & constants to include "research_agent".	Updated TaskType model / Pydantic schema
1.2	Create Alembic migration to ensure the tasks table schema matches the PRD and includes the new task type.	Migration script applied
1.3	Verify the papers table matches the PRD: add embedding_model column and FTS5 triggers if missing.	Confirmed or updated schema


⸻

Phase 2 — Core Research Agent Engine (Backend)

Step	FR	Action
2.1	FR‑2	Implement LocalSearchTool (agentic_research/local_search.py) for embedding and similarity search over papers.
2.2	FR‑3,4	Port the agent loop into agentic_research/loop.py, replacing model calls with ModelFactory.invoke() and injecting the search tool.
2.3	FR‑8‑10	Add AgentModelRouter that loads the boss/worker configuration from research_agent_model_config and routes calls through the factory.
2.4	FR‑11	Integrate SpacyLayoutDocProcessor → FlatMarkdownParser as an async ingestion step for new PDFs.
2.5	FR‑12	Emit structured RunLog events; store them in logs and publish each message via an internal asyncio.Queue.
2.6	FR‑18	Add POST /api/research-agent/run to FastAPI: validate input, create tasks row, launch background coroutine, return {taskId}.
2.7	FR‑18	Implement WebSocket endpoint /ws/research-agent/{taskId} that streams log events by consuming the queue.
2.8	FR‑14	Update the scheduler so that while any research_agent task is processing, new newsletter or podcast tasks are rejected.
2.9	FR‑15	On each progress milestone, POST a webhook to /api/tasks/{id}/status so UI reloads show current state.


⸻

Phase 3 — Frontend Integration (React / MUI)

Step	FR	Action
3.1	FR‑13	Add a dedicated route /research-agent; insert navigation links in Sidebar.tsx and Dashboard.
3.2	—	Create useResearchAgent hook that calls the new API, opens the WebSocket, and streams log events.
3.3	—	Build UI components: progress bar, live log console, and summary card rendered in Markdown.
3.4	FR‑16	Extend Settings.tsx with “Research Agent Models” panel (boss dropdown, worker multi‑select).
3.5	FR‑17	Persist the model configuration via /api/settings/research_agent_model_config and expose it through a React context provider.
3.6	FR‑12	Show a toast banner on any page when a research‑agent job is running, with a quick‑link to the run.


⸻

Phase 4 — Documentation & Ops

Step	Action
4.1	Update README with Research Agent usage, env vars, and sample API calls.
4.2	Add OpenAPI documentation for the new REST and WebSocket endpoints.
4.3	Draft a runbook covering scheduler blocking rules and troubleshooting steps.


⸻

Next Action

Create the feature branch feature/research-agent and start with Phase 1, Step 1.1.