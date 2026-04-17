"""
UI routes for the Sample Orchestrator using FastAPI and SQLModel.
"""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from src.database.utils import get_db
from src.database.models import (
    ProjectModel, RecordingModel, ProjectType
)

# pylint: disable=no-member

# Initialize templates
templates = Jinja2Templates(directory="src/templates")

# Custom filters for Jinja2 (matching Flask's behavior if needed)
templates.env.filters["replace"] = lambda s, old, new: s.replace(old, new)
templates.env.filters["title"] = lambda s: s.title()

ui_router = APIRouter(tags=["UI"])

@ui_router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    """Renders the main entry page showing all projects."""
    statement = select(ProjectModel).order_by(ProjectModel.created_at.desc())
    projects = db.exec(statement).all()
    return templates.TemplateResponse(
        "ui/project_list.html", 
        {"request": request, "title": "My Projects", "projects": projects, "now": datetime.utcnow()}
    )

@ui_router.get("/projects/new", response_class=HTMLResponse)
async def create_project_form(request: Request):
    """Renders the HTML form for creating a new project."""
    # Pre-format project types for the template
    project_types_formatted = [
        (t.value, t.value.replace('_', ' ').title()) for t in ProjectType
    ]
    return templates.TemplateResponse(
        "ui/create_project.html", 
        {
            "request": request, 
            "title": "Create Project",
            "now": datetime.utcnow(),
            "project_types": project_types_formatted,
            "selected_type": ProjectType.SAMPLE_PACK.value
        }
    )

@ui_router.post("/projects/create")
async def create_project_submit(
    project_name: str = Form(...),
    project_description: Optional[str] = Form(None),
    project_type: str = Form(ProjectType.SAMPLE_PACK.value),
    db: Session = Depends(get_db)
):
    """Handles the submission of the new project creation form."""
    new_project = ProjectModel(
        name=project_name,
        description=project_description,
        project_type=project_type
    )
    db.add(new_project)
    db.commit()
    db.refresh(new_project)
    
    # Redirect to dashboard
    return RedirectResponse(
        url=f"/projects/{new_project.id}", 
        status_code=status.HTTP_303_SEE_OTHER
    )

@ui_router.get("/projects/{project_id}", response_class=HTMLResponse)
async def dashboard(project_id: int, request: Request, db: Session = Depends(get_db)):
    """Renders the project dashboard."""
    project = db.get(ProjectModel, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Explicitly query for recordings to ensure we get a list
    statement = select(RecordingModel).where(RecordingModel.project_id == project_id)
    recordings = db.exec(statement).all()
    
    return templates.TemplateResponse(
        "ui/dashboard.html", 
        {
            "request": request, 
            "project": project, 
            "recordings": recordings,
            "now": datetime.utcnow()
        }
    )

@ui_router.get("/styleguide", response_class=HTMLResponse)
async def styleguide(request: Request):
    """Renders the design system styleguide."""
    return templates.TemplateResponse(
        "ui/styleguide.html",
        {"request": request, "title": "Design System Styleguide", "now": datetime.utcnow()}
    )

@ui_router.get("/projects/{project_id}/import_audio", response_class=HTMLResponse)
async def import_project_audio_ui(project_id: int, request: Request, db: Session = Depends(get_db)):
    """Renders the audio import page."""
    project = db.get(ProjectModel, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    return templates.TemplateResponse(
        "ui/import_audio.html",
        {
            "request": request,
            "project_id": project.id,
            "project_name": project.name,
            "now": datetime.utcnow()
        }
    )

@ui_router.get("/projects/{project_id}/loop_generation", response_class=HTMLResponse)
async def loop_generation_ui(project_id: int, request: Request, db: Session = Depends(get_db)):
    """Stub for loop generation UI."""
    project = db.get(ProjectModel, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return templates.TemplateResponse(
        "ui/loop_generation.html", 
        {"request": request, "project": project, "now": datetime.utcnow()}
    )

@ui_router.get("/projects/{project_id}/dspreset_settings", response_class=HTMLResponse)
async def dspreset_settings_form(project_id: int, request: Request, db: Session = Depends(get_db)):
    """Stub for DSPreset settings form."""
    project = db.get(ProjectModel, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if project.project_type != ProjectType.VIRTUAL_INSTRUMENT:
        raise HTTPException(status_code=403, detail="DSPreset settings only available for virtual instruments")

    return templates.TemplateResponse(
        "ui/dspreset_settings.html", 
        {"request": request, "project": project, "now": datetime.utcnow()}
    )

@ui_router.post("/projects/{project_id}/dspreset_settings")
async def dspreset_settings_submit(
    project_id: int, 
    project_name: str = Form(...),
    db: Session = Depends(get_db)
):
    """Stub for DSPreset settings submission."""
    project = db.get(ProjectModel, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project.name = project_name
    db.add(project)
    db.commit()
    
    return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)

@ui_router.get("/projects/{project_id}/recordings/{recording_id}/process", response_class=HTMLResponse)
async def process_recording_ui(project_id: int, recording_id: int, request: Request):
    """Stub for recording processing UI."""
    return templates.TemplateResponse(
        "ui/process_recording.html", 
        {"request": request, "project_id": project_id, "recording_id": recording_id, "now": datetime.utcnow()}
    )
