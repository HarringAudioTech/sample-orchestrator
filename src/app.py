"""
Main entry point for the FastAPI Sample Orchestrator application.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.database.utils import init_db
from src.api.routes import api_router
from src.ui.routes import ui_router

# --- Configuration ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_FOLDER = PROJECT_ROOT / "data" / "uploads"
SAMPLES_BASE_DIR = PROJECT_ROOT / "data" / "projects"

# --- Lifecycle Management ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    # Startup: Ensure directories exist
    for folder in [UPLOAD_FOLDER, SAMPLES_BASE_DIR]:
        folder.mkdir(parents=True, exist_ok=True)
    
    # Initialize database
    init_db()
    
    yield
    # Shutdown: Cleanup if needed
    pass

# --- App Initialization ---
app = FastAPI(
    title="Sample Orchestrator",
    description="Modern audio sample management and processing API",
    version="2.0.0",
    lifespan=lifespan
)

# --- Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Static Files & Templates ---
app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/templates")

# --- Routers ---
app.include_router(api_router, prefix="/api")
app.include_router(ui_router)

# --- Root Endpoints ---
@app.get("/", tags=["General"])
async def root():
    """Basic health check and welcome endpoint."""
    return {"message": "Welcome to the Audio Processing and Sample Management API!"}

# --- Error Handlers ---
@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=404,
        content={"error": "Not Found", "message": "The requested resource was not found."},
    )

@app.exception_handler(500)
async def internal_server_error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "message": "An unexpected error occurred."},
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.app:app", host="0.0.0.0", port=5001, reload=True)
