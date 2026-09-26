from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router

app = FastAPI(
    title="ORCA (Oceanic Resource & Condition Assistant) API",
    description="Agentic backend handling multimodal marine queries.",
    version="1.0.0"
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the main routes
app.include_router(router, prefix="/api/v1")

@app.get("/health")
@app.get("/api/v1/health")
def health_check():
    """Simple health check endpoint."""
    return {
        "status": "healthy",
        "system": "ORCA Multi-Agent Backend",
        "version": "1.0.0",
        "database": "connected"
    }
