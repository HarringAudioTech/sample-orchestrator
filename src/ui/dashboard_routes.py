"""Dashboard routes for the UI blueprint."""
import datetime
from flask import render_template, abort

# Add missing imports
from src.database.utils import get_db
from src.database.models import ProjectModel

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
        
        # Use get_db() as a context manager
        with get_db() as db:
            print(f"DEBUG: Querying for project with id={project_id}")
            project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            print(f"DEBUG: Project query result: {project}")
            
            if not project:
                print(f"DEBUG: Project with id={project_id} not found")
                abort(404, description=f"Project with ID {project_id} not found.")

            print(f"DEBUG: Getting recordings from project relationship")
            recordings = project.recordings
            print(f"DEBUG: Found {len(recordings)} recordings")

            # Return the rendered template with the project data and current datetime
            return render_template(
                "dashboard.html",
                title=f"Dashboard - {project.name}",
                project=project,
                recordings=recordings,
                now=datetime.datetime.now()
            )
