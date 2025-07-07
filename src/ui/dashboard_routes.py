"""Dashboard routes for the UI blueprint."""
from flask import render_template, abort
from src.database.models import Project as ProjectModel, Recording as RecordingModel
from src.database.utils import get_db

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
        db_session_generator = get_db()
        db = next(db_session_generator)
        try:
            print(f"DEBUG: Querying for project with id={project_id}")
            project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            print(f"DEBUG: Project query result: {project}")
            
            if not project:
                print(f"DEBUG: Project with id={project_id} not found")
                abort(404, description=f"Project with ID {project_id} not found.")

            print(f"DEBUG: Querying for recordings for project_id={project_id}")
            recordings = db.query(RecordingModel).filter(RecordingModel.project_id == project_id).all()
            print(f"DEBUG: Found {len(recordings)} recordings")

            return render_template(
                "dashboard.html",
                title=f"Dashboard - {project.name}",
                project=project,
                recordings=recordings,
            )
        except Exception as e:
            print(f"ERROR in dashboard route: {str(e)}")
            raise
        finally:
            try:
                next(db_session_generator)  # Ensure the finally block in get_db is executed
            except StopIteration:
                pass
