"""UI routes for the sample orchestrator application."""

# Standard library imports
from typing import List, Optional
from datetime import datetime

# Third-party imports
from flask import Blueprint, render_template, abort, request, url_for, redirect, flash, current_app
from werkzeug.exceptions import HTTPException
import requests
from sqlalchemy.orm import joinedload
import json
# Local application imports
from src.database.utils import get_db
from src.database.models import (
    ProjectModel, RecordingModel, SampleModel,
    ProjectType, VirtualInstrumentModel, SampleMappingItemModel, VelocityGroupModel,
    LoopGenerationConfigModel, LoopRenderingConfigModel
)

# Local application imports
from src.core.stage_runner import STAGE_REGISTRY
from src.core.workflows import WORKFLOW_REGISTRY
from src.core.loop_orchestrator import LoopOrchestrator

# Import stages to ensure they're registered
import src.core.stages.slicing_stage  # noqa: F401
import src.core.stages.noise_reduction_stage  # noqa: F401
import src.core.stages.vocal_chop_perfection_stage  # noqa: F401
import src.core.stages.decent_sampler_export_stage  # noqa: F401

# Define the blueprint for UI routes
ui_bp = Blueprint(
    "ui_bp",
    __name__,
    template_folder="../templates/ui",  # Points to src/templates/ui
    static_folder="../static",  # Points to src/static
    static_url_path="/ui/static",  # URL path for these static files
)

# Import and initialize dashboard routes after ui_bp is defined
from . import dashboard_routes  # noqa: E402
dashboard_routes.init_dashboard_routes(ui_bp)

from . import manifest_routes  # noqa: E402
manifest_routes.init_manifest_routes(ui_bp)

# --- Loop Generation Routes ---

@ui_bp.route("/projects/<int:project_id>/loop_generation", methods=["GET"])
def loop_generation_ui(project_id: int) -> str:
    """Renders the loop generation dashboard for a project."""
    with get_db() as db:
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            abort(404, description=f"Project with ID {project_id} not found.")

        gen_configs = db.query(LoopGenerationConfigModel).all()
        render_configs = db.query(LoopRenderingConfigModel).all()

        return render_template(
            "loop_generation.html",
            project=project,
            gen_configs=gen_configs,
            render_configs=render_configs,
            now=datetime.utcnow()
        )

@ui_bp.route("/configs/generation/new", methods=["GET", "POST"])
@ui_bp.route("/configs/generation/<int:config_id>/edit", methods=["GET", "POST"])
def edit_gen_config(config_id: Optional[int] = None):
    """Handles creating or editing a loop generation configuration."""
    with get_db() as db:
        config = None
        if config_id:
            config = db.query(LoopGenerationConfigModel).filter(LoopGenerationConfigModel.id == config_id).first()
            if not config:
                abort(404)

        if request.method == "POST":
            name = request.form.get("name")
            engine_id = request.form.get("engine_id")
            key = request.form.get("key")
            meter = request.form.get("meter")
            tempo = float(request.form.get("tempo", 120.0))
            bars = int(request.form.get("bars", 4))
            seed = int(request.form.get("seed", 42))
            engine_options_json = request.form.get("engine_options_json", "{}")

            if not config:
                config = LoopGenerationConfigModel(name=name)
                db.add(config)
            
            config.name = name
            config.engine_id = engine_id
            config.key = key
            config.meter = meter
            config.tempo = tempo
            config.bars = bars
            config.seed = seed
            config.engine_options_json = engine_options_json
            
            db.commit()
            flash(f"Generation config '{name}' saved.", "success")
            return redirect(request.args.get("next") or url_for("ui_bp.index"))

        return render_template(
            "edit_gen_config.html",
            config=config,
            now=datetime.utcnow()
        )

@ui_bp.route("/configs/rendering/new", methods=["GET", "POST"])
@ui_bp.route("/configs/rendering/<int:config_id>/edit", methods=["GET", "POST"])
def edit_render_config(config_id: Optional[int] = None):
    """Handles creating or editing a loop rendering configuration."""
    with get_db() as db:
        config = None
        if config_id:
            config = db.query(LoopRenderingConfigModel).filter(LoopRenderingConfigModel.id == config_id).first()
            if not config:
                abort(404)

        if request.method == "POST":
            name = request.form.get("name")
            midi_port = request.form.get("midi_port")
            audio_device_index = request.form.get("audio_device_index")
            if audio_device_index:
                audio_device_index = int(audio_device_index)
            else:
                audio_device_index = None
            capture_tail_seconds = float(request.form.get("capture_tail_seconds", 2.0))
            patch_data_json = request.form.get("patch_data_json", "{}")

            if not config:
                config = LoopRenderingConfigModel(name=name)
                db.add(config)
            
            config.name = name
            config.midi_port = midi_port
            config.audio_device_index = audio_device_index
            config.capture_tail_seconds = capture_tail_seconds
            config.patch_data_json = patch_data_json
            
            db.commit()
            flash(f"Rendering config '{name}' saved.", "success")
            return redirect(request.args.get("next") or url_for("ui_bp.index"))

        return render_template(
            "edit_render_config.html",
            config=config,
            now=datetime.utcnow()
        )

@ui_bp.route("/projects/<int:project_id>/loop_generation/run", methods=["POST"])
def run_loop_generation(project_id: int):
    """Triggers loop generation batch."""
    batch_label = request.form.get("batch_label")
    count = int(request.form.get("count", 4))
    gen_config_id = int(request.form.get("gen_config_id"))
    render_config_id = int(request.form.get("render_config_id"))

    with get_db() as db:
        orchestrator = LoopOrchestrator(db)
        try:
            results = orchestrator.capture_loop_batch_with_config(
                project_id=project_id,
                batch_label=batch_label,
                count=count,
                gen_config_id=gen_config_id,
                render_config_id=render_config_id
            )
            flash(f"Successfully generated {len(results)} loops.", "success")
        except Exception as e:
            current_app.logger.error(f"Error in loop generation: {e}")
            flash(f"Error generating loops: {str(e)}", "error")

        return redirect(url_for("ui_bp.loop_generation_ui", project_id=project_id))

# --- Existing Routes ---

# Add a simple test route to check if routes are being registered
@ui_bp.route("/test-route")
def test_route() -> str:
    """A simple test route to check if routes are being registered."""
    return "Test route is working!"

# Root route for the UI blueprint
@ui_bp.route("/")
def index() -> str:
    """Renders the main entry page for the UI blueprint.

    This route shows a list of all projects. If there are no projects,
    it shows a welcome message with a button to create a new project.

    Returns:
        str: The rendered HTML content of the project list page.
    """
    # Import datetime at the top of the file if not already imported
    from datetime import datetime
    
    # Get database session using context manager
    with get_db() as db:
        try:
            # Query all projects, ordered by most recently created
            projects = db.query(ProjectModel).order_by(ProjectModel.created_at.desc()).all()
            return render_template(
                "ui/project_list.html", 
                title="My Projects", 
                projects=projects,
                now=datetime.utcnow()
            )
        except Exception as e:
            current_app.logger.error(f"Error fetching projects: {str(e)}")
            flash("An error occurred while loading projects. Please try again.", "error")
            return render_template(
                "ui/project_list.html", 
                title="My Projects", 
                projects=[],
                now=datetime.utcnow()
            )

@ui_bp.route("/projects/new", methods=["GET"])
def create_project_form() -> str:
    """Renders the HTML form for creating a new project."""
    from datetime import datetime
    from src.database.models import ProjectType
    
    return render_template(
        "create_project.html", 
        title="Create Project",
        now=datetime.utcnow(),
        project_types=[t.value for t in ProjectType],
        selected_type=ProjectType.SAMPLE_PACK.value
    )


@ui_bp.route("/projects/create", methods=["POST"])
def create_project_submit():
    """Handles the submission of the new project creation form."""
    project_name = request.form.get('project_name')
    project_description = request.form.get('project_description')

    if not project_name:
        flash("Project name is required.", "error")
        from datetime import datetime
        return render_template(
            "create_project.html",
            title="Create Project",
            now=datetime.utcnow(),
            project_name=project_name,
            project_description=project_description
        )

    from datetime import datetime
    from src.database.models import ProjectType
    
    # Get project type from form, defaulting to SAMPLE_PACK
    project_type = request.form.get('project_type', ProjectType.SAMPLE_PACK.value)
    
    # The API is mounted at the root path, so we don't need the /api prefix
    api_url = "http://localhost:5001/projects"
    current_app.logger.info(f"Attempting to create project via API at {api_url}")
    
    payload = {
        "name": project_name, 
        "description": project_description,
        "project_type": project_type
    }

    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        project_data = response.json()
        project_id = project_data.get('id')
        flash(f"Project '{project_name}' created successfully!", "success")
        return redirect(url_for('ui_bp.dashboard', project_id=project_id))
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error creating project via API: {e}")
        error_message = "Failed to create project. Please try again."
        try:
            if hasattr(e, 'response') and e.response and e.response.json() and 'error' in e.response.json():
                error_message = e.response.json()['error']
        except:
            pass
            
        flash(error_message, "error")
        return render_template(
            "create_project.html",
            title="Create Project",
            now=datetime.utcnow(),
            project_name=project_name,
            project_description=project_description,
            project_types=[t.value for t in ProjectType],
            selected_type=project_type
        )


@ui_bp.route("/projects/<int:project_id>/dspreset_settings", methods=["GET"])
def dspreset_settings_form(project_id: int) -> str:
    """Renders the form for editing DSPreset settings."""
    with get_db() as db:
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()

        if not project:
            abort(404, description=f"Project with ID {project_id} not found.")

        if project.project_type != ProjectType.VIRTUAL_INSTRUMENT.value:
            abort(403, description="DSPreset settings are only available for Virtual Instrument projects.")

        # Eagerly load all necessary data for the virtual instrument project
        vi_project = db.query(VirtualInstrumentModel).options(
            joinedload(VirtualInstrumentModel.recordings)
            .joinedload(RecordingModel.samples)
            .joinedload(SampleModel.sample_mapping_items)
            .joinedload(SampleMappingItemModel.velocity_group),
            joinedload(VirtualInstrumentModel.velocity_groups)
        ).filter(VirtualInstrumentModel.id == project_id).first()

        return render_template(
            "dspreset_settings.html",
            project=vi_project,
            now=datetime.utcnow()
        )

@ui_bp.route("/projects/<int:project_id>/dspreset_settings", methods=["POST"])
def dspreset_settings_submit(project_id: int):
    """Handles the submission of the DSPreset settings form, including sample mappings."""
    with get_db() as db:
        project = db.query(VirtualInstrumentModel).options(
            joinedload(VirtualInstrumentModel.recordings)
            .joinedload(RecordingModel.samples)
            .joinedload(SampleModel.sample_mapping_items),
            joinedload(VirtualInstrumentModel.velocity_groups)
        ).filter(VirtualInstrumentModel.id == project_id).first()

        if not project:
            abort(404, description=f"Project with ID {project_id} not found.")

        # --- Update Project-Level Settings ---
        project.name = request.form.get('project_name', project.name)
        try:
            base_note = request.form.get('base_note')
            project.base_note = int(base_note) if base_note and base_note.strip() else None
            round_robins = request.form.get('round_robins')
            project.round_robins = int(round_robins) if round_robins and round_robins.strip() else None
        except (ValueError, TypeError):
            flash("Invalid number format for base note or round robins.", "error")
            return redirect(url_for('ui_bp.dspreset_settings_form', project_id=project_id))

        metadata = project.meta_data or {}
        metadata['author'] = request.form.get('author')
        if 'artwork' in request.files and request.files['artwork'].filename != '':
            metadata['artwork_path'] = request.files['artwork'].filename
        project.metadata_json = json.dumps(metadata)

        # --- Handle Velocity Groups ---
        layer_ids = request.form.getlist('layer_id')
        deleted_layer_ids = request.form.getlist('deleted_layers')

        # Delete groups
        for layer_id_str in deleted_layer_ids:
            if layer_id_str.isdigit():
                group_to_delete = db.query(VelocityGroupModel).filter_by(id=int(layer_id_str)).first()
                if group_to_delete:
                    db.delete(group_to_delete)

        # Create/Update groups
        new_layer_id_map = {}
        for layer_id in layer_ids:
            try:
                name = request.form.get(f'layer_name_{layer_id}')
                low_vel = int(request.form.get(f'layer_low_vel_{layer_id}'))
                high_vel = int(request.form.get(f'layer_high_vel_{layer_id}'))

                if layer_id.startswith('new_'):
                    new_group = VelocityGroupModel(
                        project_id=project.id,
                        name=name,
                        low_vel=low_vel,
                        high_vel=high_vel
                    )
                    db.add(new_group)
                    db.flush() # Flush to get the new ID
                    new_layer_id_map[layer_id] = new_group.id
                elif layer_id.isdigit():
                    group = next((g for g in project.velocity_groups if g.id == int(layer_id)), None)
                    if group:
                        group.name = name
                        group.low_vel = low_vel
                        group.high_vel = high_vel
            except (ValueError, TypeError):
                flash(f"Invalid velocity value for layer {layer_id}. Please enter valid numbers.", "error")
                continue

        # --- Update Sample-Level Mappings ---
        selected_sample_ids = set(request.form.getlist('selected_samples'))
        all_samples = [s for rec in project.recordings for s in rec.samples]

        for sample in all_samples:
            sample_id_str = str(sample.id)
            mapping_item = next(iter(sample.sample_mapping_items), None)

            if sample_id_str in selected_sample_ids:
                if not mapping_item:
                    mapping_item = SampleMappingItemModel(sample_id=sample.id)
                    db.add(mapping_item)

                try:
                    mapping_item.root_note = int(request.form.get(f'sample_root_note_{sample.id}'))
                    mapping_item.key_range_start = int(request.form.get(f'sample_lo_key_{sample.id}'))
                    mapping_item.key_range_end = int(request.form.get(f'sample_hi_key_{sample.id}'))

                    group_id_str = request.form.get(f'sample_velocity_group_{sample.id}')
                    if group_id_str and group_id_str.startswith('new_'):
                        mapping_item.velocity_group_id = new_layer_id_map.get(group_id_str)
                    elif group_id_str and group_id_str.isdigit():
                        mapping_item.velocity_group_id = int(group_id_str)
                    else:
                        mapping_item.velocity_group_id = None

                except (ValueError, TypeError):
                    flash(f"Invalid mapping value for sample {sample.name}. Please enter valid numbers.", "error")
                    continue
            else:
                # If sample is not selected, delete its mapping
                if mapping_item:
                    db.delete(mapping_item)

        try:
            db.commit()
            flash("DSPreset settings updated successfully!", "success")
        except Exception as e:
            db.rollback()
            current_app.logger.error(f"Failed to update DSPreset settings: {e}")
            flash("An error occurred while saving the settings. Please try again.", "error")

        return redirect(url_for('ui_bp.dspreset_settings_form', project_id=project_id))


@ui_bp.route("/projects/<string:project_id>/progress", methods=["GET"])
def project_progress(project_id: str) -> str:
    """Renders the progress monitoring page for a specific project."""
    return render_template(
        "project_progress.html", 
        title=f"Project {project_id}", 
        project_id=project_id,
        now=datetime.utcnow()  # Add current time for base template
    )


@ui_bp.route("/projects/<int:project_id>/import_audio", methods=["GET"])
def import_project_audio_ui(project_id: int) -> str:
    """Renders the UI for importing an audio file to a specific project."""
    # Use get_db() as a context manager
    with get_db() as db:
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()

        if not project:
            abort(404, description=f"Project with ID {project_id} not found.")

        # Add now variable to match other templates
        return render_template(
            "import_audio.html",
            project_id=project.id,
            project_name=project.name,
            error=None,  # Initially no error
            success_message=None,  # Initially no success message
            now=datetime.utcnow()  # Add current time for base template
        )


@ui_bp.route("/projects/<int:project_id>/recordings/<int:recording_id>/process", methods=["GET"])
def process_recording_ui(project_id: int, recording_id: int) -> str:
    """Renders the UI for processing a specific recording."""
    # Use get_db() as a context manager
    with get_db() as db:
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            abort(404, description=f"Project with ID {project_id} not found.")

        recording = db.query(RecordingModel).filter(RecordingModel.id == recording_id).first()
        if not recording or recording.project_id != project_id:
            abort(404, description=f"Recording with ID {recording_id} not found in project {project_id}.")

        # Instantiate workflows for template
        workflows_instances = {name: workflow_class() for name, workflow_class in WORKFLOW_REGISTRY.items()}
        return render_template(
            "process_recording.html",
            project=project,
            recording=recording,
            workflows=workflows_instances,
            stages=STAGE_REGISTRY,
            now=datetime.utcnow()  # Add current time for base template
        )


@ui_bp.route("/projects/<int:project_id>/recordings/<int:recording_id>/process", methods=["POST"])
def process_recording_submit(project_id: int, recording_id: int) -> str:
    """Handles the submission of the recording processing form."""
    workflow_name = request.form.get('workflow_name')
    instrument_name = request.form.get('instrument_name')
    instrument_author = request.form.get('instrument_author')

    from datetime import datetime
    # Use the correct API URL with the proper port (5001 as defined in docker-compose.yml)
    api_url = f"http://localhost:5001/recordings/{recording_id}/process"
    current_app.logger.info(f"Processing recording via API at {api_url}")
    payload = {
        "output_dir_suffix": f"processed_by_{workflow_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}" # Unique suffix
    }

    if workflow_name == 'decent_sampler_creation_workflow':
        payload["stages_chain"] = [
            {
                "stage_name": "slicing",
                "params": {}
            },
            {
                "stage_name": "decent_sampler_export",
                "params": {
                    "instrument_name": instrument_name,
                    "instrument_author": instrument_author
                }
            }
        ]
    else:
        payload["workflow_name"] = workflow_name

    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        result = response.json()
        flash(f"Processing successful! {result.get('message', '')}", "success")
        flash(f"Output: {result.get('output_location', '')}", "info")
        return redirect(url_for('ui_bp.dashboard', project_id=project_id))
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error processing recording via API: {e}")
        error_message = "Failed to process recording. Please try again."
        if hasattr(e, 'response') and e.response and e.response.json() and 'error' in e.response.json():
            error_message = e.response.json()['error']
        flash(error_message, "error")
        return redirect(url_for('ui_bp.process_recording_ui', project_id=project_id, recording_id=recording_id))



@ui_bp.route("/projects/<int:project_id>/recordings/<int:recording_id>", methods=["GET"])
def view_recording(project_id: int, recording_id: int) -> str:
    """Renders the page for viewing a single recording and its samples."""
    with get_db() as db:
        recording = (
            db.query(RecordingModel)
            .filter(RecordingModel.id == recording_id, RecordingModel.project_id == project_id)
            .first()
        )

        if not recording:
            abort(404, description=f"Recording with ID {recording_id} not found in project {project_id}.")

        return render_template(
            "view_recording.html",
            title=f"Recording: {recording.name}",
            recording=recording,
            samples=recording.samples,
            now=datetime.utcnow()
        )

@ui_bp.route("/projects/<int:project_id>/recordings/<int:recording_id>/samples", methods=["GET"])
def view_samples(project_id: int, recording_id: int) -> str:
    """Renders the page for viewing samples of a specific recording."""
    with get_db() as db:
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            abort(404, description=f"Project with ID {project_id} not found.")

        recording = db.query(RecordingModel).filter(RecordingModel.id == recording_id).first()
        if not recording or recording.project_id != project_id:
            abort(404, description=f"Recording with ID {recording_id} not found in project {project_id}.")

        samples = recording.samples

        return render_template(
            "view_samples.html",
            project=project,
            recording=recording,
            samples=samples,
            now=datetime.utcnow()
        )


@ui_bp.route("/samples/<int:sample_id>", methods=["GET"])
def view_sample(sample_id: int) -> str:
    """Renders the page for viewing a single sample."""
    with get_db() as db:
        sample = db.query(SampleModel).filter(SampleModel.id == sample_id).first()
        if not sample:
            abort(404, description=f"Sample with ID {sample_id} not found.")

        return render_template(
            "view_sample.html",
            title=f"Sample - {sample.name}",
            sample=sample,
            now=datetime.utcnow()
        )
