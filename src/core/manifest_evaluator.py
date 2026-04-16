"""
Manifest evaluator for construction kits.

This module provides logic to match project assets (samples and MIDI) against 
manifest rules and calculate fulfillment progress.
"""

from typing import Dict, Any, List, Optional, Set
from sqlalchemy.orm import Session
import json
import logging

from src.database.models import (
    SampleModel, 
    MidiFileModel, 
    ManifestRuleModel, 
    ManifestModel,
    ProjectModel,
    RecordingModel,
    MidiCaptureSessionModel
)

logger = logging.getLogger(__name__)

class ManifestEvaluator:
    """
    Evaluates how well project assets fulfill the requirements defined in a manifest.
    """

    def __init__(self, db: Session):
        self.db = db

    def evaluate_project(self, project_id: int) -> Dict[str, Any]:
        """
        Evaluate all assets in a project against its manifest.

        Args:
            project_id: The ID of the project to evaluate.

        Returns:
            A dictionary containing:
            - total_progress: Overall percentage of manifest fulfillment.
            - rule_results: Detailed status for each manifest rule.
            - unassigned_assets: Assets that didn't match any rule.
        """
        # 1. Fetch the manifest and its rules
        manifest = self.db.query(ManifestModel).filter(ManifestModel.project_id == project_id).first()
        if not manifest:
            return {
                "total_progress": 0,
                "rule_results": [],
                "unassigned_assets": [],
                "error": "No manifest found for this project"
            }

        rules = self.db.query(ManifestRuleModel).filter(ManifestRuleModel.manifest_id == manifest.id).all()
        if not rules:
            return {
                "total_progress": 100,
                "rule_results": [],
                "unassigned_assets": [],
                "message": "Manifest has no rules"
            }

        # 2. Fetch all samples and MIDI files for the project
        samples = self.db.query(SampleModel).join(RecordingModel).filter(
            RecordingModel.project_id == project_id
        ).all()
        
        midi_files = self.db.query(MidiFileModel).join(MidiCaptureSessionModel).filter(
            MidiCaptureSessionModel.project_id == project_id
        ).all()

        # 3. Initialize rule results
        rule_results = []
        fulfilled_asset_ids = {
            "samples": set(),
            "midi": set()
        }

        for rule in rules:
            # Ensure we have a rule object, not a tuple (sometimes happens in join queries)
            if isinstance(rule, tuple):
                rule = rule[0]
                
            matching_samples = []
            matching_midi = []
            
            # Extract tags for matching
            required_tags = rule.required_tags
            if isinstance(required_tags, str):
                try:
                    required_tags = json.loads(required_tags)
                except json.JSONDecodeError:
                    required_tags = {}
            
            # Match samples
            for sample in samples:
                if self._matches_tags(sample.meta_data, required_tags):
                    matching_samples.append({
                        "id": sample.id,
                        "name": sample.name,
                        "type": "sample",
                        "tags": sample.meta_data
                    })
                    fulfilled_asset_ids["samples"].add(sample.id)

            # Match MIDI files
            # Note: MidiFileModel doesn't have a direct metadata_json, 
            # we might need to look at the capture session metadata or instrument data.
            # For now, we'll check if the capture session has matching tags.
            for midi in midi_files:
                session_meta = midi.capture_session.meta_data if hasattr(midi.capture_session, 'meta_data') else {}
                if self._matches_tags(session_meta, required_tags):
                    matching_midi.append({
                        "id": midi.id,
                        "name": f"MIDI Channel {midi.channel}",
                        "type": "midi",
                        "tags": session_meta
                    })
                    fulfilled_asset_ids["midi"].add(midi.id)

            combined_matches = matching_samples + matching_midi
            match_count = len(combined_matches)
            progress = min(100, int((match_count / rule.target_count) * 100)) if rule.target_count > 0 else 100

            rule_results.append({
                "rule_id": rule.id,
                "name": rule.name,
                "category": rule.category,
                "target_count": rule.target_count,
                "match_count": match_count,
                "progress": progress,
                "matches": combined_matches,
                "is_fulfilled": match_count >= rule.target_count
            })

        # 4. Find unassigned assets
        unassigned_assets = []
        for sample in samples:
            if sample.id not in fulfilled_asset_ids["samples"]:
                unassigned_assets.append({
                    "id": sample.id,
                    "name": sample.name,
                    "type": "sample",
                    "tags": sample.meta_data
                })

        for midi in midi_files:
            if midi.id not in fulfilled_asset_ids["midi"]:
                unassigned_assets.append({
                    "id": midi.id,
                    "name": f"MIDI Channel {midi.channel}",
                    "type": "midi",
                    "tags": midi.capture_session.meta_data if hasattr(midi.capture_session, 'meta_data') else {}
                })

        # 5. Calculate total progress
        total_rules = len(rules)
        total_progress = sum(r["progress"] for r in rule_results) / total_rules if total_rules > 0 else 100

        return {
            "total_progress": int(total_progress),
            "rule_results": rule_results,
            "unassigned_assets": unassigned_assets
        }

    def _matches_tags(self, asset_tags: Dict[str, Any], required_tags: Dict[str, Any]) -> bool:
        """
        Check if an asset's tags satisfy the required tags.
        A match occurs if all keys in required_tags exist in asset_tags and have matching values.
        Values are matched case-insensitively if they are strings.
        """
        if not required_tags:
            return False # Rule must have some requirements

        for key, required_value in required_tags.items():
            if key not in asset_tags:
                return False
            
            asset_value = asset_tags[key]
            
            # Handle string matching case-insensitively
            if isinstance(required_value, str) and isinstance(asset_value, str):
                if required_value.lower() != asset_value.lower():
                    return False
            else:
                if required_value != asset_value:
                    return False
                    
        return True
