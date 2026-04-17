"""Data-related UI routes for the sample orchestrator using FastAPI and SQLModel."""

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from src.database.utils import get_db
from src.database.models import RecordingModel, SampleModel

templates = Jinja2Templates(directory="src/templates")
data_router = APIRouter(prefix="/ui/projects/{project_id}", tags=["Data"])

@data_router.get("/recordings/{recording_id}", response_class=HTMLResponse)
async def view_recording(project_id: int, recording_id: int, request: Request, db: Session = Depends(get_db)):
    """Renders the page for viewing a single recording and its samples."""
    recording = db.get(RecordingModel, recording_id)
    if not recording:
        raise HTTPException(status_code=404, detail=f"Recording with ID {recording_id} not found.")

    # Explicitly query for samples
    statement = select(SampleModel).where(SampleModel.recording_id == recording_id)
    samples = db.exec(statement).all()

    return templates.TemplateResponse(
        request=request,
        name="ui/view_recording.html",
        context={
            "title": f"Recording - {recording.name}",
            "recording": recording,
            "samples": samples,
            "now": datetime.utcnow()
        }
    )

@data_router.get("/samples/{sample_id}", response_class=HTMLResponse)
async def view_sample(sample_id: int, request: Request, db: Session = Depends(get_db)):
    """Renders the page for viewing a single sample."""
    sample = db.get(SampleModel, sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail=f"Sample with ID {sample_id} not found.")

    return templates.TemplateResponse(
        request=request,
        name="ui/view_sample.html",
        context={
            "title": f"Sample - {sample.id}",
            "sample": sample,
            "now": datetime.utcnow()
        }
    )
