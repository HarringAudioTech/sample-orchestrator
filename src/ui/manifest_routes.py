"""Manifest routes for construction kits using FastAPI and SQLModel."""

import json
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from src.database.utils import get_db
from src.database.models import (
    ProjectModel, 
    ConstructionKitProjectModel, 
    ManifestModel, 
    ManifestRuleModel,
    LoopRenderingConfigModel,
    ProjectType
)
from src.core.manifest_evaluator import ManifestEvaluator
from src.core.loop_orchestrator import LoopOrchestrator
from src.core.construction_kit_exporter import ConstructionKitExporter

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="src/templates")

manifest_router = APIRouter(prefix="/projects/{project_id}/manifest", tags=["Manifest"])

def _sanitize_path(name: str) -> str:
    """Sanitizes a string for filesystem use."""
    if not name:
        return "unknown"
    return "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in name).strip()

@manifest_router.get("/builder", response_class=HTMLResponse)
async def manifest_builder(project_id: int, request: Request, db: Session = Depends(get_db)):
    """Renders the manifest builder UI."""
    project = db.get(ProjectModel, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Ensure it's a construction kit project
    if project.project_type != ProjectType.CONSTRUCTION_KIT:
        return RedirectResponse(url=f"/projects/{project_id}", status_code=status.HTTP_303_SEE_OTHER)

    # Get or create manifest
    statement = select(ManifestModel).where(ManifestModel.project_id == project_id)
    manifest = db.exec(statement).first()
    if not manifest:
        manifest = ManifestModel(project_id=project_id)
        db.add(manifest)
        db.commit()
        db.refresh(manifest)

    return templates.TemplateResponse(
        request=request,
        name="ui/manifest_builder.html",
        context={"project": project, "manifest": manifest, "now": datetime.utcnow()}
    )

@manifest_router.post("/builder")
async def manifest_builder_submit(
    project_id: int, 
    request: Request,
    rules_json: str = Form(...),
    db: Session = Depends(get_db)
):
    """Handles saving rules from the dynamic builder."""
    project = db.get(ProjectModel, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    statement = select(ManifestModel).where(ManifestModel.project_id == project_id)
    manifest = db.exec(statement).first()
    if not manifest:
        manifest = ManifestModel(project_id=project_id)
        db.add(manifest)
        db.commit()
        db.refresh(manifest)

    try:
        new_rules = json.loads(rules_json)
        
        # Clear existing rules
        statement = select(ManifestRuleModel).where(ManifestRuleModel.manifest_id == manifest.id)
        old_rules = db.exec(statement).all()
        for r in old_rules:
            db.delete(r)
        
        # Add new ones
        for r in new_rules:
            rule = ManifestRuleModel(
                manifest_id=manifest.id,
                name=r.get("name"),
                category=r.get("category"),
                target_count=r.get("target_count", 1),
                required_tags_json=json.dumps(r.get("required_tags", {}))
            )
            db.add(rule)
        
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Error saving manifest rules: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error saving manifest: {str(e)}")

    return RedirectResponse(
        url=f"/projects/{project_id}/manifest/builder", 
        status_code=status.HTTP_303_SEE_OTHER
    )

@manifest_router.get("/status", response_class=HTMLResponse)
async def manifest_status(project_id: int, request: Request, db: Session = Depends(get_db)):
    """Renders the manifest fulfillment status dashboard."""
    project = db.get(ProjectModel, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    render_configs = db.exec(select(LoopRenderingConfigModel)).all()
    
    evaluator = ManifestEvaluator(db)
    results = evaluator.evaluate_project(project_id)
    
    return templates.TemplateResponse(
        request=request,
        name="ui/manifest_status.html",
        context={
            "project": project,
            "results": results,
            "render_configs": render_configs,
            "now": datetime.utcnow()
        }
    )

@manifest_router.post("/fulfill/{rule_id}")
async def fulfill_rule(
    project_id: int, 
    rule_id: int,
    render_config_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """Triggers the LoopOrchestrator to generate assets for a specific rule."""
    try:
        orchestrator = LoopOrchestrator(db)
        orchestrator.fulfill_manifest_rule(
            project_id=project_id,
            rule_id=rule_id,
            render_config_id=render_config_id
        )
    except Exception as e:
        logger.error(f"Error fulfilling manifest rule: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

    return RedirectResponse(
        url=f"/projects/{project_id}/manifest/status", 
        status_code=status.HTTP_303_SEE_OTHER
    )

@manifest_router.post("/export")
async def export_kit(project_id: int, db: Session = Depends(get_db)):
    """Triggers the ConstructionKitExporter to package the kit."""
    project = db.get(ProjectModel, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    output_dir = f"data/projects/{project_id}/exports"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{_sanitize_path(project.name)}_kit.zip")
    
    try:
        exporter = ConstructionKitExporter(db)
        zip_path = exporter.export_kit(project_id, output_path)
        return FileResponse(zip_path, filename=os.path.basename(zip_path))
    except Exception as e:
        logger.error(f"Error exporting kit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
