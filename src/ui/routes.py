from flask import Blueprint, render_template, abort, request
from werkzeug.exceptions import HTTPException
from src.database.models import Project as ProjectModel, Recording as RecordingModel
from src.database.utils import get_db
from src.core.stage_runner import STAGE_REGISTRY
from src.core.workflows import WORKFLOW_REGISTRY
import src.core.stages.slicing_stage  # noqa: F401
import src.core.stages.noise_reduction_stage  # noqa: F401
import src.core.stages.vocal_chop_perfection_stage # noqa: F401


# Define the blueprint for UI routes
ui_bp = Blueprint(
    "ui_bp",
    __name__,
    template_folder="../templates/ui",  # Points to src/templates/ui
    static_folder="../static",  # Points to src/static
    static_url_path="/ui/static",  # URL path for these static files
)


@ui_bp.route("/projects/<int:project_id>/dashboard")
def dashboard(project_id: int) -> str:
    """Renders the main application dashboard page for a specific project.

    This route serves the primary user interface page, typically displaying
    an overview of projects, activities, or other key information.
    It utilizes the "dashboard.html" template.

    Args:
        project_id (int): The ID of the project to display the dashboard for.

    Returns:
        str: The rendered HTML content of the dashboard page. The page title
             is set to "Dashboard - {project.name}".
    """
    db_session_generator = get_db()
    db = next(db_session_generator)
    try:
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            abort(404, description=f"Project with ID {project_id} not found.")

        recordings = db.query(RecordingModel).filter(RecordingModel.project_id == project_id).all()

        return render_template(
            "dashboard.html",
            title=f"Dashboard - {project.name}",
            project=project,
            recordings=recordings,
        )
    finally:
        try:
            next(db_session_generator)  # Ensure the finally block in get_db is executed
        except StopIteration:
            pass


# Optional: Add a root route for the UI blueprint if desired,
# for example, redirecting to the dashboard or showing a simple welcome page.
@ui_bp.route("/")
def index() -> str:
    """Renders the main entry page for the UI blueprint.

    Currently, this route renders the "dashboard.html" template, effectively
    making the dashboard the landing page for the `/ui/` URL prefix.
    In the future, this could be changed to render a dedicated welcome or
    index page for the UI section.

    Args:
        None.

    Returns:
        str: The rendered HTML content of the dashboard page, with the page
             title set to "Welcome".
    """
    # For now, let's also point the UI root to the dashboard.
    # Alternatively, this could be a separate landing page.
    return render_template("dashboard.html", title="Welcome")


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


from flask import Blueprint, render_template, abort, request, url_for, redirect, flash, current_app
from werkzeug.exceptions import HTTPException
from src.database.models import Project as ProjectModel, Recording as RecordingModel
from src.database.utils import get_db
from src.core.stage_runner import STAGE_REGISTRY
from src.core.workflows import WORKFLOW_REGISTRY
import src.core.stages.slicing_stage  # noqa: F401
import src.core.stages.noise_reduction_stage  # noqa: F401
import src.core.stages.vocal_chop_perfection_stage # noqa: F401
import src.core.stages.decent_sampler_export_stage # noqa: F401
import requests # Import requests library

# Define the blueprint for UI routes
ui_bp = Blueprint(
    "ui_bp",
    __name__,
    template_folder="../templates/ui",  # Points to src/templates/ui
    static_folder="../static",  # Points to src/static
    static_url_path="/ui/static",  # URL path for these static files
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
        return redirect(url_for('ui_bp.create_project_form'))

    api_url = f"http://localhost:5000/projects" # Assuming API runs on localhost:5000
    payload = {"name": project_name, "description": project_description}

    try:
        response = requests.post(api_url, json=payload)
        response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
        project_data = response.json()
        project_id = project_data.get('id')
        flash(f"Project '{project_name}' created successfully!", "success")
        return redirect(url_for('ui_bp.dashboard', project_id=project_id))
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error creating project via API: {e}")
        error_message = "Failed to create project. Please try again."
        if response and response.json() and 'error' in response.json():
            error_message = response.json()['error']
        flash(error_message, "error")
        return redirect(url_for('ui_bp.create_project_form'))



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
    db_session_generator = get_db()
    db = next(db_session_generator)
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()

    try:
        if not project:
            abort(404, description=f"Project with ID {project_id} not found.")

        return render_template(
            "import_audio.html", # Corrected path based on template folder structure
            project_id=project.id,
            project_name=project.name,
            error=None,  # Initially no error
            success_message=None,  # Initially no success message
        )
    finally:
        try:
            next(db_session_generator) # Ensure the finally block in get_db is executed
        except StopIteration:
            pass


@ui_bp.route("/projects/<int:project_id>/recordings/<int:recording_id>/process", methods=["GET"])
def process_recording_ui(project_id: int, recording_id: int) -> str:
    """Renders the UI for processing a specific recording.

    Args:
        project_id (int): The ID of the project.
        recording_id (int): The ID of the recording to process.

    Returns:
        str: Rendered HTML page for processing a recording.
    """
    db_session_generator = get_db()
    db = next(db_session_generator)
    try:
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
            stages=STAGE_REGISTRY
        )
    finally:
        try:
            next(db_session_generator)
        except StopIteration:
            pass


# --- UI Blueprint Error Handler ---
@ui_bp.errorhandler(HTTPException)
def handle_ui_exception(e: HTTPException):
    """Return HTML for HTTP errors on the UI blueprint routes.
    This ensures that if abort() is called or an exception derived from
    HTTPException occurs during the handling of a UI route, the user
    is shown a user-friendly HTML error page instead of a default
    JSON or plain text error.
    """
    # Get the standard response object for the exception
    response = e.get_response()

    # Check if the client prefers HTML content.
    # The ui_bp routes are primarily for user-facing HTML, so we prioritize HTML error pages.
    # This condition can be adjusted if some UI routes might be called by clients
    # that don't prefer HTML (e.g., htmx requests not specifically asking for HTML snippets).
    if "text/html" in request.accept_mimetypes:
        # If HTML is preferred, render the custom error template.
        # The 'error' object (the exception 'e') is passed to the template,
        # which can then access 'e.code' and 'e.description'.
        return render_template("error.html", error=e), e.code

    # If the client does not prefer HTML (e.g., an API client mistakenly hitting a UI route,
    # or an htmx request that doesn't set Accept: text/html),
    # return the default response from the exception (often JSON or plain text).
    return response


@ui_bp.route("/projects/<int:project_id>/recordings/<int:recording_id>/samples", methods=["GET"])
def view_recording_samples_ui(project_id: int, recording_id: int) -> str:
    """Renders the UI for viewing samples associated with a specific recording.

    Args:
        project_id (int): The ID of the project.
        recording_id (int): The ID of the recording whose samples are to be viewed.

    Returns:
        str: Rendered HTML page for viewing recording samples.
    """
    db_session_generator = get_db()
    db = next(db_session_generator)
    try:
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            abort(404, description=f"Project with ID {project_id} not found.")

        recording = db.query(RecordingModel).filter(RecordingModel.id == recording_id).first()
        if not recording or recording.project_id != project_id:
            abort(404, description=f"Recording with ID {recording_id} not found in project {project_id}.")

        samples = recording.samples # Access samples via relationship

        return render_template(
            "view_samples.html",
            project=project,
            recording=recording,
            samples=samples
        )
    finally:
        try:
            next(db_session_generator)
        except StopIteration:
            pass


@ui_bp.errorhandler(404)
def handle_ui_404_error(e):
    """Return a custom HTML page for 404 Not Found errors on the UI blueprint.
    Ensures that users always see a user-friendly HTML page for 404s
    originating from UI routes. The exception 'e' (a NotFound instance)
    contains 'code' and 'description' attributes that are passed to the
    error template.
    """
    # Note: e.code will be 404.
    # e.description will be the message from abort(404, description="...")
    # or a default "Not Found" message if no description was provided.
    return render_template("error.html", error=e), 404
