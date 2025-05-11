from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from theseus_insight.api.routers import pdf, script, podcast, visualizer, settings_router
from theseus_insight.api.theseus_insight_routes import router as theseus_insight_router
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="Theseus Insight API",
    description="API for Theseus Insight podcast generation and visualization",
    version="1.0.0"
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
