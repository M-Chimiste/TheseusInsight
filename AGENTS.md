# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Project Overview

Theseus Insight is a full-stack research paper analysis platform with a FastAPI backend and React/TypeScript frontend. It fetches papers from ArXiv, scores them with LLMs, generates newsletters and podcasts, and provides advanced visualizations (mind-maps, 3D star maps, research timelines).

## Development Commands

### Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Run backend (development)
uvicorn theseus_insight.main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend
```bash
cd theseus-ui
npm install
npm run dev      # Development server on http://localhost:5173
npm run build    # Production build
npm run lint     # ESLint
```

### Docker (full stack with PostgreSQL)
```bash
docker compose up --build  # API + built frontend on http://localhost:8000
```

### Database Migrations
Migrations run automatically on API startup via `theseus_insight/db/migrations.py`. Migration SQL files are in `scripts/00X_*.sql`.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  React Frontend (theseus-ui/)                                   │
│  - Material-UI components, D3.js visualizations                 │
│  - XYFlow for graph visualization, Socket.io for WebSockets     │
└─────────────────────────────────────────────────────────────────┘
                    ↓ REST API + WebSocket
┌─────────────────────────────────────────────────────────────────┐
│  FastAPI Backend (theseus_insight/)                             │
├─────────────────────────────────────────────────────────────────┤
│  api/routers/        → API endpoint modules                     │
│  api/models.py       → Pydantic request/response schemas        │
│  data_access/        → Repository pattern for DB operations     │
│  data_processing/    → Paper harvesting, scoring, embeddings    │
│  research_agent/     → Multi-agent AI research orchestration    │
│  podcast/            → TTS and podcast generation               │
│  mindmap/            → Mind-map visualization generation        │
│  star_map/           → 3D constellation visualization           │
│  db/                 → Database connection and migrations       │
└─────────────────────────────────────────────────────────────────┘
                    ↓ asyncpg
┌─────────────────────────────────────────────────────────────────┐
│  PostgreSQL + pgvector                                          │
│  - Vector similarity search for semantic paper relationships    │
│  - Full-text search (tsvector/tsquery) for keyword search       │
│  - Hybrid scoring combining both approaches                     │
└─────────────────────────────────────────────────────────────────┘
```

## Key Patterns

**LLM Integration**: Uses [LLMFactory](https://github.com/M-Chimiste/LLMFactory.git) for unified inference across OpenAI, Anthropic, Gemini, Ollama, LM Studio, and LlamaCPP. Model configuration is in `config/orchestration.json`.

**Multi-Server Inference**: Supports distributing LLM workloads across multiple Ollama/LM Studio servers. Configuration stored in `inference_servers` table.

**Data Access Layer**: Repository pattern in `data_access/` with async PostgreSQL operations via asyncpg. Each entity (papers, profiles, newsletters) has its own repository.

**WebSocket Progress**: Long-running tasks (newsletter generation, mind-map building, star map computation) use WebSockets for real-time progress updates. See `api/routers/websockets.py`.

**Profile System**: Multi-profile support where each profile has its own research interests, email recipients, and ArXiv filters. Most features are profile-aware.

## Important Files

- `theseus_insight/main.py` - FastAPI application entry point
- `theseus_insight/api/models.py` - All Pydantic schemas
- `theseus_insight/data_access/papers.py` - Paper search with hybrid semantic+keyword scoring
- `theseus_insight/research_agent/workflow.py` - Research agent orchestration
- `config/orchestration.json` - LLM model configuration
- `theseus-ui/src/services/` - Frontend API client services

## Environment Variables

Key variables (set in `.env`):
- `DATABASE_URL` - PostgreSQL connection string
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` - LLM API keys
- `OLLAMA_URL` - Local Ollama server URL (default: `http://127.0.0.1:11434`)
- `LMSTUDIO_HOST` - LM Studio server host:port (default: `localhost:1234`)
- `APP_SECRET_KEY` - Encrypts stored credentials

**Note**: Do NOT set `DATABASE_URL` when using Docker Compose; it's configured automatically.

## Project Tracking

After each coding session, update `project_status.md` with:
- What has been implemented
- What needs to be implemented next
- A detailed debug log
