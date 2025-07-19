"""UI routes for the sample orchestrator application."""

# Standard library imports
from typing import List, Optional

# Third-party imports
from flask import Blueprint, render_template, abort, request, url_for, redirect, flash, current_app
from werkzeug.exceptions import HTTPException
import requests

# Local application imports
from src.core.stage_runner import STAGE_REGISTRY
from src.core.workflows import WORKFLOW_REGISTRY

# Import stages to ensure they're registered
import src.core.stages.slicing_stage  # noqa: F401
import src.core.stages.noise_reduction_stage  # noqa: F401
import src.core.stages.vocal_chop_perfection_stage  # noqa: F401
import src.core.stages.decent_sampler_export_stage  # noqa: F401

# Import database models and utils
from src.database.models import Project as ProjectModel, Recording as RecordingModel
from src.database.utils import get_db

from datetime import datetime

# --- Helper for datetime restoration from ISO strings ---

def _restore_datetimes(d):
    """Convert ISO datetime strings in a dict to datetime objects for template usage.
    
    Handles nested dictionaries and lists of dictionaries. Converts all known datetime fields
    from ISO format strings to datetime objects.
    """
    if not isinstance(d, dict) and not isinstance(d, list):
        return d
        
    if isinstance(d, list):
        return [_restore_datetimes(item) for item in d]
        
    # Handle dict case
    datetime_fields = ["created_at", "updated_at", "processed_at", "recorded_at"]
    result = {}
    
    for key, value in d.items():
        if key in datetime_fields and isinstance(value, str):
            try:
                result[key] = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                result[key] = value
        elif isinstance(value, dict):
            result[key] = _restore_datetimes(value)
        elif isinstance(value, list):
            result[key] = [_restore_datetimes(item) for item in value]
        else:
            result[key] = value
            
    return result

def _ensure_consistent_context(project=None, recording=None, **kwargs):
    """Ensure consistent context dict structure for templates.
    
    Args:
        project: Project dict or None
        recording: Recording dict or None
        **kwargs: Additional context values
        
    Returns:
        dict: Consistent context dictionary with all required fields
    """
    # Ensure project has all required fields
    if project is None:
        project = {}
    
    project = {
        'id': project.get('id'),
        'name': project.get('name'),
        'description': project.get('description', ''),
        'project_type': project.get('project_type'),
        'created_at': project.get('created_at'),
        'updated_at': project.get('updated_at'),
        **{k: v for k, v in project.items() if k not in ['id', 'name', 'description', 'project_type', 'created_at', 'updated_at']}
    }
    
    # Ensure recording has all required fields
    if recording is None:
        recording = {}
        
    recording = {
        'id': recording.get('id'),
        'name': recording.get('name'),
        'file_path': recording.get('file_path'),
        'processing_status': recording.get('processing_status'),
        'created_at': recording.get('created_at'),
        'updated_at': recording.get('updated_at'),
        **{k: v for k, v in recording.items() if k not in ['id', 'name', 'file_path', 'processing_status', 'created_at', 'updated_at']}
    }
    
    # Return combined context
    return {
        'project': project,
        'recording': recording,
        'project_id': project.get('id'),
        'recording_id': recording.get('id'),
        **kwargs
    }

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

@ui_bp.route("/projects/<int:project_id>")
def project_detail(project_id: int) -> str:
    """Renders the project detail page for a specific project.
    
    Args:
        project_id (int): The ID of the project to display.
        
    Returns:
        str: The rendered HTML content of the project detail page.
    """
    try:
        # Get project details from API
        api_url = f"{current_app.config['API_BASE_URL']}/api/projects/{project_id}"
        response = requests.get(api_url)
        
        if response.status_code == 404:
            # Render project detail with error banner and 200
            return render_template(
                "project_detail.html",
                **_ensure_consistent_context(
                    project={"id": project_id},
                    error="Project not found"
                ),
                title="Project Not Found"
            ), 200
        
        response.raise_for_status()  # Raise exception for other HTTP errors
        project = _restore_datetimes(response.json())
        
        # Render the project detail template with the project data
        return render_template(
            "project_detail.html",
            **_ensure_consistent_context(project=project),
            title=f"Project: {project['name']}"
        )
    except requests.RequestException as e:
        current_app.logger.error(f"Error fetching project details: {e}")
        return render_template(
            "project_detail.html",
            **_ensure_consistent_context(
                project={"id": project_id},
                error="Error fetching project details. Please try again later."
            ),
            title="Error - Project Details"
        ), 200

# Root route for the UI blueprint
@ui_bp.route("/")
def index() -> str:
    """Renders the main entry page for the UI blueprint.

    Currently, this route renders the "dashboard.html" template, effectively
    making the dashboard the landing page for the `/ui/` URL prefix.
    
    Fetches the first project from the database to display in the dashboard.
    If no projects exist, renders the dashboard without project data.

    Returns:
        str: The rendered HTML content of the dashboard page.
    """
    from src.database.models import Project
    from src.database.utils import get_db
    
    # Get a database session using the context manager
    with get_db() as db:
        project = db.query(Project).order_by(Project.created_at.desc()).first()
        
        from src.database.models import model_to_dict

        from datetime import datetime

        def restore_datetimes(d):
            if not d:
                return d
            for key in ("created_at", "updated_at"):
                if key in d and isinstance(d[key], str):
                    try:
                        d[key] = datetime.fromisoformat(d[key])
                    except ValueError:
                        pass
            return d

        # Convert ORM objects to dictionaries expected by tests/templates
        project_dict = restore_datetimes(model_to_dict(project)) if project else None

        # Get recordings if project exists, otherwise use empty list
        recordings = [restore_datetimes(model_to_dict(r)) for r in project.recordings] if project else []

        # Get all projects for list view and convert to dicts
        projects = db.query(Project).order_by(Project.created_at.desc()).all()
        projects_dict = [restore_datetimes(model_to_dict(p)) for p in projects]

        # Render the template with the projects and recordings
        return render_template(
            "dashboard.html",
            title="Welcome",
            project=project_dict,
            projects=projects_dict,
            recordings=recordings,
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
    return render_template("create_project.html", title="Create Project")


@ui_bp.route("/projects/create", methods=["POST"])
def create_project_submit():
    """Handles the submission of the new project creation form.

    This route processes the form data, calls the API to create a new project,
    and redirects the user based on the outcome.
    """
    project_name = request.form.get('project_name')
    project_description = request.form.get('project_description')

    if not project_name:
        # Render form with error context for UI contract (do not redirect)
        return render_template(
            "create_project.html",
            title="Create Project",
            error="Project name is required.",
        ), 200

    # Use the configured API base URL
    api_base_url = current_app.config.get("API_BASE_URL", "http://localhost:5000")
    api_url = f"{api_base_url.rstrip('/')}/projects"
    payload = {"name": project_name, "description": project_description}

    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        project_data = response.json()
        project_id = project_data.get('id')
        flash(f"Project '{project_name}' created successfully!", "success")
        return redirect(url_for('ui_bp.index', project_id=project_id))
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error creating project via API: {e}")
        error_message = f"Failed to create project: {str(e)}"
        # Check if we have a response with error details
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                if isinstance(error_data, dict) and 'error' in error_data:
                    error_message = error_data['error']
                elif isinstance(error_data, str):
                    error_message = f"API Error: {error_data}"
            except (ValueError, AttributeError):
                # If we can't parse JSON or access response, use the default error message
                pass
        flash(error_message, "error")
        return redirect(url_for('ui_bp.create_project_form'))



@ui_bp.route("/projects/<int:project_id>/upload_audio", methods=["GET", "POST"])
def upload_project_audio(project_id: int):
    """UI route for uploading audio to a project. GET renders form, POST handles upload."""
    from werkzeug.utils import secure_filename
    import os
    ALLOWED_EXTENSIONS = {"wav", "aiff", "wave", "aif"}

    def allowed_file(filename):
        return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

    # Get project data
    with get_db() as db:
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        project_dict = _restore_datetimes(model_to_dict(project)) if project else {"id": project_id}
    
    # Handle GET request
    if request.method == "GET":
        return render_template(
            "import_audio.html",
            **_ensure_consistent_context(
                project=project_dict,
                error=None,
                success_message=None
            )
        )
    
    # Handle POST request
    recording_name = request.form.get("recording_name")
    audio_file = request.files.get("audio_file")
    
    # Validate project exists
    if not project or not project_dict.get("name"):
        return render_template(
            "import_audio.html",
            **_ensure_consistent_context(
                project=project_dict,
                error=f"Project with ID {project_id} not found.",
                success_message=None
            )
        ), 200
        
    # Validate form data
    if not recording_name or not audio_file:
        return render_template(
            "import_audio.html",
            **_ensure_consistent_context(
                project=project_dict,
                error="Recording name and audio file are required.",
                success_message=None
            )
        ), 200
        
    if not allowed_file(audio_file.filename):
        return render_template(
            "import_audio.html",
            **_ensure_consistent_context(
                project=project_dict,
                error="File type not allowed. Please upload a WAV or AIFF file.",
                success_message=None
            )
        ), 200
    
    # Process the uploaded file
    filename = secure_filename(audio_file.filename)
    # In a real app, you would save the file and create a recording record here
    # audio_file.save(os.path.join("uploads", filename))
    
    # Return success response
    print("DEBUG: Returning success template with success_message")
    result = render_template(
        "import_audio.html",
        **_ensure_consistent_context(
            project=project_dict,
            error=None,
            success_message="Audio uploaded successfully"
        )
    )
    print(f"DEBUG: Success message in template: {'audio uploaded successfully' in result.lower()}")
    return result
    return result

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
        "project_progress.html", title=f"Project {project_id}", project_id=project_id
    )


@ui_bp.route("/projects/<int:project_id>/import_audio", methods=["GET"])
def import_project_audio_ui(project_id: int) -> str:
    """Renders the UI for importing an audio file to a specific project.

    Args:
        project_id (int): The ID of the project to import audio for.

    Returns:
        str: Rendered HTML page for audio import.
    """
    with get_db() as db:
        from src.database.models import model_to_dict
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            # Always pass a dict for project, with id and name None if not found
            project_dict = {"id": project_id, "name": None}
            return render_template(
                "import_audio.html",
                project=project_dict,
                project_id=project_id,
                project_name=None,
                error=f"Project with ID {project_id} not found.",
                success_message=None,
            ), 200

        project_dict = model_to_dict(project)
        return render_template(
            "import_audio.html",
            project=project_dict,
            project_id=project.id,
            project_name=project.name,
            error=None,
            success_message=None,
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
    with get_db() as db:
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            return render_template(
                "process_recording.html",
                **_ensure_consistent_context(
                    project={"id": project_id},
                    recording={"id": recording_id},
                    error=f"Project with ID {project_id} not found."
                ),
                workflows=WORKFLOW_REGISTRY,
                stages=STAGE_REGISTRY
            ), 200

        from src.database.models import model_to_dict
        recording = db.query(RecordingModel).filter(RecordingModel.id == recording_id).first()
        if not recording or recording.project_id != project_id:
            return render_template(
                "process_recording.html",
                **_ensure_consistent_context(
                    project=model_to_dict(project) if project else {"id": project_id},
                    recording={"id": recording_id},
                    error=f"Recording with ID {recording_id} not found in project {project_id}."
                ),
                workflows=WORKFLOW_REGISTRY,
                stages=STAGE_REGISTRY
            ), 200

        # Use ORM for logic, dict for template only
        recording_dict = _restore_datetimes(model_to_dict(recording))
        project_dict = _restore_datetimes(model_to_dict(project))

        return render_template(
            "process_recording.html",
            **_ensure_consistent_context(
                project=project_dict,
                recording=recording_dict
            ),
            workflows=WORKFLOW_REGISTRY,
            stages=STAGE_REGISTRY,
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

    api_url = f"http://localhost:5000/recordings/{recording_id}/process"
    from datetime import datetime
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




