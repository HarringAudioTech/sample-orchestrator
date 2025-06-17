from flask import Blueprint, render_template, abort
from src.database.models import Project as ProjectModel
from src.database.utils import get_db

# Define the blueprint for UI routes
ui_bp = Blueprint(
    "ui_bp",
    __name__,
    template_folder="../templates/ui",  # Points to src/templates/ui
    static_folder="../static",  # Points to src/static
    static_url_path="/ui/static",  # URL path for these static files
)


@ui_bp.route("/dashboard")
def dashboard() -> str:
    """Renders the main application dashboard page.

    This route serves the primary user interface page, typically displaying
    an overview of projects, activities, or other key information.
    It utilizes the "dashboard.html" template.

    Args:
        None.

    Returns:
        str: The rendered HTML content of the dashboard page. The page title
             is set to "Dashboard".
    """
    return render_template("dashboard.html", title="Dashboard")


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


@ui_bp.route("/projects/create", methods=["POST"])
def create_project_submit() -> tuple[str, int]:
    """Handles the submission of the new project creation form.

    This route is intended for POST requests, typically from the form rendered
    by `create_project_form`. It is responsible for taking the submitted
    form data (e.g., project name, description), processing it (e.g.,
    saving it to a database), and then usually redirecting the user to
    another page, like the dashboard or the newly created project's page.

    Note:
        Currently, this function is a placeholder. It does not perform any
        actual project creation or data processing. It returns a simple
        message and an HTTP 200 status code. In a complete implementation,
        it would interact with a backend service or database.

    Args:
        None. Expects form data in `flask.request.form`.

    Returns:
        tuple[str, int]: A tuple containing a string message and an HTTP
                         status code. In its current placeholder state, it
                         returns ("Project creation submitted (not yet implemented)", 200).
                         A full implementation would typically return a redirect
                         response or render a success/failure template.
    """
    # Placeholder for form submission logic
    # In a real app, you would process form data here, e.g.:
    # project_name = request.form.get('project_name')
    # description = request.form.get('project_description')
    # ... save to database ...
    # return redirect(url_for('ui_bp.dashboard')) # Or project detail page
    return "Project creation submitted (not yet implemented)", 200


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
    db = get_db()
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()

    if not project:
        abort(404, description=f"Project with ID {project_id} not found.")

    return render_template(
        "ui/import_audio.html",
        project_id=project.id,
        project_name=project.name,
        error=None,  # Initially no error
        success_message=None,  # Initially no success message
    )
