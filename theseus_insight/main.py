from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from theseus_insight.api.routers import pdf, script, podcast, visualizer, settings_router
from theseus_insight.api.theseus_insight_routes import router as theseus_insight_router
from dotenv import load_dotenv
import os
import json
from pathlib import Path
from contextlib import asynccontextmanager
from theseus_insight.data_model.data_handling import PaperDatabase

load_dotenv()

# Helper to populate settings from config files on first launch
def _populate_settings_from_config():
    """
    Populate the SQLite `settings` table on first launch.

    • If the table already contains at least one row, the function exits.
    • Otherwise it looks for `config/orchestration.json` and
      `config/research_interests.txt` (relative to the repository root) and,
      if present, stores their raw contents in the database under the keys
      `orchestration_config` and `research_interests` respectively.
    • Missing files are ignored silently.

    The database location is taken from the THESEUS_DB_PATH environment
    variable, defaulting to `data/papers.db`.
    """
    db_path = os.environ.get("THESEUS_DB_PATH", "data/papers.db")
    db = PaperDatabase(db_path)

    # Abort early if any setting already exists
    if db.get_all_settings():
        return

    repo_root = Path(__file__).resolve().parent.parent
    config_dir = repo_root / "config"

    orch_path = config_dir / "orchestration.json"
    interests_path = config_dir / "research_interests.txt"

    if orch_path.exists():
        with open(orch_path, "r", encoding="utf-8") as f:
            db.set_setting("orchestration_config", f.read())

    if interests_path.exists():
        with open(interests_path, "r", encoding="utf-8") as f:
            db.set_setting("research_interests", f.read())


# Lifespan handler (replaces deprecated on_event("startup"))
@asynccontextmanager
async def lifespan(app: FastAPI):
    _populate_settings_from_config()
    yield

app = FastAPI(
    title="Theseus Insight API",
    description="API for Theseus Insight podcast generation and visualization",
    version="0.9.0",
    lifespan=lifespan,
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React development server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(pdf.router, prefix="/api/pdf", tags=["PDF"])
app.include_router(script.router, prefix="/api/script", tags=["Script"])
app.include_router(podcast.router, prefix="/api/podcast", tags=["Podcast"])
app.include_router(visualizer.router, prefix="/api/visualizer", tags=["Visualizer"])
app.include_router(theseus_insight_router, prefix="/api/theseus_insight", tags=["theseus_insight"])
app.include_router(settings_router, prefix="/api", tags=["Settings"])

@app.get("/")
async def root():
    return {
        "message": "Welcome to Theseus Insight API",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }
