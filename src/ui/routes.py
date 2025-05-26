from flask import Blueprint, render_template

# Define the blueprint for UI routes
ui_bp = Blueprint(
    "ui_bp",
    __name__,
    template_folder="../templates/ui",  # Points to src/templates/ui
    static_folder="../static",  # Points to src/static
    static_url_path="/ui/static",  # URL path for these static files
)


@ui_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html", title="Dashboard")


# Optional: Add a root route for the UI blueprint if desired,
# for example, redirecting to the dashboard or showing a simple welcome page.
@ui_bp.route("/")
def index():
    # For now, let's also point the UI root to the dashboard.
    # Alternatively, this could be a separate landing page.
    return render_template("dashboard.html", title="Welcome")


@ui_bp.route("/projects/new", methods=["GET"])
def create_project_form():
    return render_template("create_project.html", title="Create Project")


@ui_bp.route("/projects/create", methods=["POST"])
def create_project_submit():
    # Placeholder for form submission logic
    # In a real app, you would process form data here, e.g.:
    # project_name = request.form.get('project_name')
    # description = request.form.get('project_description')
    # ... save to database ...
    # return redirect(url_for('ui_bp.dashboard')) # Or project detail page
    return "Project creation submitted (not yet implemented)", 200


@ui_bp.route("/projects/<string:project_id>/progress", methods=["GET"])
def project_progress(project_id):
    # In the future, you would fetch project details using project_id
    return render_template(
        "project_progress.html",
        title=f"Project {project_id}",
        project_id=project_id)
