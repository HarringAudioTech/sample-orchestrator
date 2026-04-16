"""
API routes for the Sample Orchestrator using FastAPI and SQLModel.
"""

import os
import json
from typing import List, Optional, Dict, Any
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlmodel import Session, select
from starlette.status import HTTP_201_CREATED

from src.database.utils import get_db
from src.database.models import (
    ProjectModel, RecordingModel, SampleModel, 
    ProjectType, LoopGenerationConfigModel, LoopRenderingConfigModel
)
from src.core.project_manager import ProjectManager
from src.core.project import Project as CoreProject

api_router = APIRouter()

# --- Project Routes ---
projects_router = APIRouter(prefix="/projects", tags=["Projects"])

@projects_router.post("", response_model=ProjectModel, status_code=HTTP_201_CREATED)
async def create_project(
    project: ProjectModel, 
    db: Session = Depends(get_db)
):
    """Creates a new project."""
    db.add(project)
    db.commit()
    db.refresh(project)
    
    # Create project directory
    ProjectManager.create_project_directory(
        project_id=project.id,
        project_type=project.project_type,
        app_config={} # Need to handle config better in future
    )
    return project

@projects_router.get("", response_model=List[ProjectModel])
async def list_projects(
    project_type: Optional[ProjectType] = None,
    db: Session = Depends(get_db)
):
    """Lists all projects, optionally filtered by type."""
    statement = select(ProjectModel)
    if project_type:
        statement = statement.where(ProjectModel.project_type == project_type)
    results = db.exec(statement.order_by(ProjectModel.created_at.desc())).all()
    return results

@projects_router.get("/{project_id}", response_model=ProjectModel)
async def get_project(project_id: int, db: Session = Depends(get_db)):
    """Retrieves a specific project."""
    project = db.get(ProjectModel, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

# --- Recording Routes ---
recordings_router = APIRouter(prefix="/recordings", tags=["Recordings"])

@projects_router.post("/{project_id}/recordings", response_model=RecordingModel, status_code=HTTP_201_CREATED)
async def add_project_recording(
    project_id: int,
    name: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Adds a new recording to a project via file upload."""
    project = db.get(ProjectModel, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Save file
    project_upload_dir = Path(f"data/uploads/project_{project_id}")
    project_upload_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = project_upload_dir / file.filename
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Add to DB via core logic
    core_proj = CoreProject(project_id=project_id, db_session=db)
    recording = core_proj.add_recording(file_path=str(file_path), name=name)
    return recording

@projects_router.get("/{project_id}/recordings", response_model=List[RecordingModel])
async def list_project_recordings(project_id: int, db: Session = Depends(get_db)):
    """Lists all recordings for a project."""
    project = db.get(ProjectModel, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.recordings

# --- Config Routes ---
configs_router = APIRouter(prefix="/configs", tags=["Configurations"])

@configs_router.get("/generation", response_model=List[LoopGenerationConfigModel])
async def list_gen_configs(db: Session = Depends(get_db)):
    return db.exec(select(LoopGenerationConfigModel)).all()

@configs_router.post("/generation", response_model=LoopGenerationConfigModel, status_code=HTTP_201_CREATED)
async def create_gen_config(config: LoopGenerationConfigModel, db: Session = Depends(get_db)):
    db.add(config)
    db.commit()
    db.refresh(config)
    return config

# Assemble the API Router
api_router.include_router(projects_router)
api_router.include_router(recordings_router)
api_router.include_router(configs_router)
