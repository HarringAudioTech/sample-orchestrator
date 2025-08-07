"""UI routes for the sample orchestrator application."""

# Standard library imports
from typing import List, Optional
from datetime import datetime

# Third-party imports
from flask import Blueprint, render_template, abort, request, url_for, redirect, flash, current_app
from werkzeug.exceptions import HTTPException
import requests

import json
# Local application imports
from src.database.utils import get_db
from src.database.models import ProjectModel, RecordingModel, ProjectType, VirtualInstrumentModel

# Local application imports
from src.core.stage_runner import STAGE_REGISTRY
from src.core.workflows import WORKFLOW_REGISTRY

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
    """Renders the HTML form for creating a new project.

    This route handles GET requests to `/ui/projects/new`. It displays a
    web page containing a form that users can fill out to provide details
    for a new project (e.g., name, description).
    It utilizes the "create_project.html" template.

    Args:
        None.

    Returns:
        str: The rendered HTML content of the new project creation page.
             The page title is set to "Create Project".
    """
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
    """Handles the submission of the new project creation form.

    This route processes the form data, calls the API to create a new project,
    and redirects the user based on the outcome.
    """
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
    
    # Default to SAMPLE_PACK as the project type
    project_type = ProjectType.SAMPLE_PACK.value
    
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

        # We need to get the VirtualInstrumentModel to access its properties
        vi_project = db.query(VirtualInstrumentModel).filter(VirtualInstrumentModel.id == project_id).first()

        return render_template(
            "dspreset_settings.html",
            project=vi_project,
            now=datetime.utcnow()
        )

@ui_bp.route("/projects/<int:project_id>/dspreset_settings", methods=["POST"])
def dspreset_settings_submit(project_id: int):
    """Handles the submission of the DSPreset settings form."""
    with get_db() as db:
        project = db.query(VirtualInstrumentModel).filter(VirtualInstrumentModel.id == project_id).first()

        if not project:
            abort(404, description=f"Project with ID {project_id} not found.")

        if project.project_type != ProjectType.VIRTUAL_INSTRUMENT.value:
            abort(403, description="DSPreset settings are only available for Virtual Instrument projects.")

        project.name = request.form.get('project_name')
        project.base_note = int(request.form.get('base_note'))
        project.velocity_layers = int(request.form.get('velocity_layers'))
        project.round_robins = int(request.form.get('round_robins'))

        metadata = project.meta_data
        metadata['author'] = request.form.get('author')
        project.metadata_json = json.dumps(metadata)

        # Handle artwork upload
        if 'artwork' in request.files:
            artwork_file = request.files['artwork']
            if artwork_file.filename != '':
                # In a real app, you'd save this to a secure location
                # and store the path in the database.
                # For now, we'll just store the filename in metadata.
                metadata['artwork_path'] = artwork_file.filename
                project.metadata_json = json.dumps(metadata)

        db.commit()
        flash("DSPreset settings updated successfully!", "success")
        return redirect(url_for('ui_bp.dspreset_settings_form', project_id=project_id))


@ui_bp.route("/projects/<string:project_id>/progress", methods=["GET"])
def project_progress(project_id: str) -> str:
    """Renders the progress monitoring page for a specific project.

    This route displays a page where users can view the status or progress
    of a particular project, identified by `project_id`. This might include
    details about ongoing tasks, completed work, or other relevant metrics.
    It utilizes the "project_progress.html" template.

    In a full implementation, this function would fetch details about the
    project (using `project_id`) from a database or backend service to
    populate the template with dynamic data.

    Args:
        project_id (str): The unique identifier of the project for which
                          to display the progress page. This is passed as a
                          path variable from the URL.

    Returns:
        str: The rendered HTML content of the project progress page. The page
             title is dynamically set to include the `project_id`.
    """
    # In the future, you would fetch project details using project_id
    return render_template(
        "project_progress.html", 
        title=f"Project {project_id}", 
        project_id=project_id,
        now=datetime.utcnow()  # Add current time for base template
    )


@ui_bp.route("/projects/<int:project_id>/import_audio", methods=["GET"])
def import_project_audio_ui(project_id: int) -> str:
    """Renders the UI for importing an audio file to a specific project.

    Args:
        project_id (int): The ID of the project to import audio for.

    Returns:
        str: Rendered HTML page for audio import.
    """
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
    """Renders the UI for processing a specific recording.

    Args:
        project_id (int): The ID of the project.
        recording_id (int): The ID of the recording to process.

    Returns:
        str: Rendered HTML page for processing a recording.
    """
    # Use get_db() as a context manager
    with get_db() as db:
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            abort(404, description=f"Project with ID {project_id} not found.")

        recording = db.query(RecordingModel).filter(RecordingModel.id == recording_id).first()
        if not recording or recording.project_id != project_id:
            abort(404, description=f"Recording with ID {recording_id} not found in project {project_id}.")

        return render_template(
            "process_recording.html",
            project=project,
            recording=recording,
            workflows=WORKFLOW_REGISTRY,
            stages=STAGE_REGISTRY,
            now=datetime.utcnow()  # Add current time for base template
        )


@ui_bp.route("/projects/<int:project_id>/recordings/<int:recording_id>/process", methods=["POST"])
def process_recording_submit(project_id: int, recording_id: int) -> str:
    """Handles the submission of the recording processing form.

    This route processes the form data, constructs the API payload,
    calls the backend API to initiate processing, and redirects the user
    with flash messages based on the outcome.
    """
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
        if response and response.json() and 'error' in response.json():
            error_message = response.json()['error']
        flash(error_message, "error")
        return redirect(url_for('ui_bp.process_recording_ui', project_id=project_id, recording_id=recording_id))
