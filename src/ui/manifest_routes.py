"""Manifest routes for construction kits."""

import json
import logging
import os
from flask import render_template, abort, request, redirect, url_for, flash, jsonify, current_app, send_file
from datetime import datetime

from src.database.utils import get_db
from src.database.models import (
    ProjectModel, 
    ConstructionKitProjectModel, 
    ManifestModel, 
    ManifestRuleModel,
    LoopRenderingConfigModel
)
from src.core.manifest_evaluator import ManifestEvaluator
from src.core.loop_orchestrator import LoopOrchestrator
from src.core.construction_kit_exporter import ConstructionKitExporter

logger = logging.getLogger(__name__)

def _sanitize_path(name: str) -> str:
    """Sanitizes a string for filesystem use."""
    if not name:
        return "unknown"
    return "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in name).strip()

def init_manifest_routes(ui_bp):
    """
    Initialize manifest-related routes for the given UI blueprint.
    """

    @ui_bp.route("/projects/<int:project_id>/manifest/builder", methods=["GET", "POST"])
    def manifest_builder(project_id: int):
        """
        Renders the manifest builder UI and handles saving rules.
        """
        with get_db() as db:
            project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            if not project:
                abort(404)
            
            # Ensure it's a construction kit project
            if project.project_type != "construction_kit":
                flash("Manifest builder is only available for Construction Kit projects.", "warning")
                return redirect(url_for("ui_bp.dashboard", project_id=project_id))

            # Get or create manifest
            manifest = db.query(ManifestModel).filter(ManifestModel.project_id == project_id).first()
            if not manifest:
                manifest = ManifestModel(project_id=project_id)
                db.add(manifest)
                db.commit()
                # Refresh manifest to get ID
                manifest = db.query(ManifestModel).filter(ManifestModel.project_id == project_id).first()

            if request.method == "POST":
                # Handle saving rules from the dynamic builder
                rules_data = request.form.get("rules_json")
                if rules_data:
                    try:
                        new_rules = json.loads(rules_data)
                        
                        # Clear existing rules and add new ones
                        db.query(ManifestRuleModel).filter(ManifestRuleModel.manifest_id == manifest.id).delete()
                        
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
                        flash("Manifest rules updated successfully!", "success")
                    except Exception as e:
                        db.rollback()
                        logger.error(f"Error saving manifest rules: {e}", exc_info=True)
                        flash(f"Error saving manifest: {str(e)}", "danger")

                return redirect(url_for("ui_bp.manifest_builder", project_id=project_id))

            return render_template(
                "manifest_builder.html",
                project=project,
                manifest=manifest,
                now=datetime.now()
            )

    @ui_bp.route("/projects/<int:project_id>/manifest/status")
    def manifest_status(project_id: int):
        """
        Renders the manifest fulfillment status dashboard.
        """
        with get_db() as db:
            project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            if not project:
                abort(404)
                
            render_configs = db.query(LoopRenderingConfigModel).all()
            
            evaluator = ManifestEvaluator(db)
            results = evaluator.evaluate_project(project_id)
            
            return render_template(
                "manifest_status.html",
                project=project,
                results=results,
                render_configs=render_configs,
                now=datetime.now()
            )

    @ui_bp.route("/api/projects/<int:project_id>/manifest/evaluate")
    def api_manifest_evaluate(project_id: int):
        """
        Returns manifest evaluation results as JSON.
        """
        with get_db() as db:
            evaluator = ManifestEvaluator(db)
            results = evaluator.evaluate_project(project_id)
            return jsonify(results)

    @ui_bp.route("/projects/<int:project_id>/manifest/fulfill/<int:rule_id>", methods=["POST"])
    def fulfill_rule(project_id: int, rule_id: int):
        """
        Triggers the LoopOrchestrator to generate assets for a specific rule.
        """
        render_config_id = request.form.get("render_config_id")
        if not render_config_id:
            flash("Please select a rendering configuration.", "danger")
            return redirect(url_for("ui_bp.manifest_status", project_id=project_id))

        with get_db() as db:
            try:
                orchestrator = LoopOrchestrator(db)
                results = orchestrator.fulfill_manifest_rule(
                    project_id=project_id,
                    rule_id=rule_id,
                    render_config_id=int(render_config_id)
                )
                flash(f"Successfully generated {len(results)} assets for the rule!", "success")
            except Exception as e:
                logger.error(f"Error fulfilling manifest rule: {e}", exc_info=True)
                flash(f"Error fulfilling manifest rule: {str(e)}", "danger")

        return redirect(url_for("ui_bp.manifest_status", project_id=project_id))

    @ui_bp.route("/projects/<int:project_id>/manifest/export", methods=["POST"])
    def export_kit(project_id: int):
        """
        Triggers the ConstructionKitExporter to package the kit.
        """
        with get_db() as db:
            project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            if not project:
                abort(404)

            output_dir = os.path.join(current_app.config.get("SAMPLES_BASE_DIR", "data/projects"), str(project_id), "exports")
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{_sanitize_path(project.name)}_kit.zip")
            
            try:
                exporter = ConstructionKitExporter(db)
                zip_path = exporter.export_kit(project_id, output_path)
                return send_file(zip_path, as_attachment=True)
            except Exception as e:
                logger.error(f"Error exporting kit: {e}", exc_info=True)
                flash(f"Error exporting kit: {str(e)}", "danger")
                return redirect(url_for("ui_bp.manifest_status", project_id=project_id))
