"""
Construction kit exporter.

This module provides logic to export project assets in a hierarchical 
directory structure based on manifest rules.
"""

import os
import shutil
import zipfile
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from src.database.models import ProjectModel, SampleModel, MidiFileModel
from src.core.manifest_evaluator import ManifestEvaluator
from src.core.project_manager import ProjectManager

logger = logging.getLogger(__name__)

class ConstructionKitExporter:
    """
    Exports project assets into a structured Construction Kit bundle.
    """

    def __init__(self, db: Session):
        self.db = db

    def export_kit(self, project_id: int, output_path: str) -> str:
        """
        Export the project assets into a zip file with a hierarchical structure.
        Structure: Song_Name / Section_Name / [Instrument]_[Variation].wav
        """
        project = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")

        evaluator = ManifestEvaluator(self.db)
        evaluation = evaluator.evaluate_project(project_id)
        
        # Create temp directory for export
        temp_dir = Path(f"/tmp/export_{project_id}_{os.getpid()}")
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # 1. Export assigned assets
            for rule_result in evaluation["rule_results"]:
                # Determine folder path from tags
                # We'll use song and section tags if available, otherwise category
                sample_match = next((m for m in rule_result["matches"] if m["type"] == "sample"), None)
                tags = sample_match["tags"] if sample_match else {}
                
                song_name = self._sanitize(tags.get("song", "General"))
                section_name = self._sanitize(tags.get("section", rule_result["category"] or "Other"))
                
                dest_dir = temp_dir / song_name / section_name
                dest_dir.mkdir(parents=True, exist_ok=True)
                
                for idx, match in enumerate(rule_result["matches"]):
                    asset_id = match["id"]
                    if match["type"] == "sample":
                        asset = self.db.query(SampleModel).filter(SampleModel.id == asset_id).first()
                        if asset and os.path.exists(asset.file_path):
                            ext = os.path.splitext(asset.file_path)[1]
                            dest_name = f"{self._sanitize(rule_result['name'])}_{idx+1}{ext}"
                            shutil.copy2(asset.file_path, dest_dir / dest_name)
                    
                    elif match["type"] == "midi":
                        # For MIDI, we might need to write the file data from DB
                        # Assuming it's base64 encoded text in MidiFileModel
                        asset = self.db.query(MidiFileModel).filter(MidiFileModel.id == asset_id).first()
                        if asset:
                            import base64
                            midi_data = base64.b64decode(asset.file_data)
                            dest_name = f"{self._sanitize(rule_result['name'])}_{idx+1}.mid"
                            with open(dest_dir / dest_name, "wb") as f:
                                f.write(midi_data)

            # 2. Export unassigned assets into a separate folder
            if evaluation["unassigned_assets"]:
                unassigned_dir = temp_dir / "Unassigned"
                unassigned_dir.mkdir(parents=True, exist_ok=True)
                for idx, asset_info in enumerate(evaluation["unassigned_assets"]):
                    asset_id = asset_info["id"]
                    if asset_info["type"] == "sample":
                        asset = self.db.query(SampleModel).filter(SampleModel.id == asset_id).first()
                        if asset and os.path.exists(asset.file_path):
                            shutil.copy2(asset.file_path, unassigned_dir / os.path.basename(asset.file_path))

            # 3. Zip it up
            zip_file_path = output_path
            if not zip_file_path.endswith(".zip"):
                zip_file_path += ".zip"
                
            with zipfile.ZipFile(zip_file_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(temp_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, temp_dir)
                        zipf.write(file_path, arcname)
            
            return zip_file_path

        finally:
            # Clean up temp directory
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _sanitize(self, name: str) -> str:
        """Sanitizes a string for filesystem use."""
        if not name:
            return "unknown"
        return "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in name).strip()
