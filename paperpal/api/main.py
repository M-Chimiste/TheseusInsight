from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from paperpal.api.routers import pdf, script, podcast, visualizer
from paperpal.api.paperpal_routes import router as paperpal_router


app = FastAPI(
    title="PaperPal API",
    description="API for PaperPal podcast generation and visualization",
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
app.include_router(paperpal_router, prefix="/api/paperpal", tags=["paperpal"])

@app.get("/")
async def root():
    return {
        "message": "Welcome to PaperPal API",
        "docs_url": "/docs",
        "redoc_url": "/redoc"
    }
