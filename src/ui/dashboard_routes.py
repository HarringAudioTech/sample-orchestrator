"""Dashboard routes for the UI blueprint."""
import datetime
from flask import render_template, abort
from src.database.utils import get_db
from src.database.models import Project, model_to_dict
from src.ui.routes import _ensure_consistent_context

from datetime import datetime

def _restore_datetimes(d):
    """Convert ISO datetime strings in a dict to datetime objects for template usage."""
    if not isinstance(d, dict):
        return d
    for key in ("created_at", "updated_at"):
        if key in d and isinstance(d[key], str):
            try:
                d[key] = datetime.fromisoformat(d[key])
            except ValueError:
                pass
    return d

def init_dashboard_routes(ui_bp):
    """Initialize dashboard routes for the given UI blueprint.
    
    Args:
        ui_bp: The Flask Blueprint to register the routes with.
    """
    @ui_bp.route("/dashboard/<int:project_id>")
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
        print(f"DEBUG: Dashboard route called with project_id={project_id}")
        with get_db() as db:
            try:
                print(f"DEBUG: Querying for project with id={project_id}")
                project = db.query(Project).filter(Project.id == project_id).first()
                print(f"DEBUG: Project query result: {project}")
                
                if not project:
                    print(f"DEBUG: Project with id={project_id} not found")
                    return render_template(
                        "dashboard.html",
                        **_ensure_consistent_context(
                            project={"id": project_id},
                            error="Project not found"
                        ),
                        title="Dashboard - Project Not Found",
                        recordings=[],
                        now=datetime.now()
                    ), 200

                print(f"DEBUG: Getting recordings from project relationship")
                project_dict = _restore_datetimes(model_to_dict(project))
                recordings = project.recordings
                recordings_dict = [_restore_datetimes(model_to_dict(r)) for r in recordings]
                print(f"DEBUG: Found {len(recordings_dict)} recordings")

                return render_template(
                    "dashboard.html",
                    **_ensure_consistent_context(
                        project=project_dict,
                        recordings=recordings_dict
                    ),
                    title=f"Dashboard - {project_dict['name']}",
                    now=datetime.now()
                )
            except Exception as e:
                print(f"ERROR in dashboard route: {str(e)}")
                return render_template(
                    "dashboard.html",
                    **_ensure_consistent_context(
                        project={"id": project_id},
                        error=f"An error occurred: {str(e)}"
                    ),
                    title="Error - Dashboard",
                    recordings=[],
                    now=datetime.now()
                ), 500
