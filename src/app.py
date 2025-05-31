"""
This module serves as the main entry point for the Flask application.
It defines the application factory `create_app` which initializes the Flask app,
configures it, sets up database connections, registers API blueprints,
and defines basic error handlers and a root route.

The application can be run directly using `python -m src.app` for development.
"""

import os

# g is not used in current session management
from flask import Flask, jsonify, request
from src.api.routes import projects_bp, recordings_bp, samples_bp
from src.ui.routes import ui_bp  # Import the UI blueprint
from src.database.utils import (
    init_db,
    get_session_local,
    get_engine,
)  # Renamed SessionLocal to get_session_local


# --- Application Factory ---
def create_app() -> Flask:
    """
    Creates and configures an instance of the Flask application.

    This factory function:
    1. Initializes the Flask app.
    2. Sets up application configuration (e.g., paths for uploads, samples).
    3. Initializes the database and creates tables if they don't exist (on first run).
       Note: In a production environment, database initialization might be handled
       by a separate script or migration tool (e.g., Alembic).
    4. Registers API blueprints for different parts of the application.
    5. Defines global error handlers for common HTTP errors (404, 500).
    6. Creates a simple root route for basic API health check/welcome message.

    Returns:
        Flask: The configured Flask application instance.
    """
    app = Flask(__name__)

    # --- Configuration ---
    # Determine project root to build absolute paths for data directories.
    # __file__ is src/app.py, so project_root is one level up.
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    app.config["UPLOAD_FOLDER"] = os.path.join(project_root, "data", "uploads")
    app.config["SAMPLES_BASE_DIR"] = os.path.join(project_root, "data", "projects")
    # Example: app.config['DATABASE_URL'] = os.environ.get('DATABASE_URL', 'sqlite:///./default.db')
    # The actual DATABASE_URL is currently hardcoded in src/database/utils.py

    app.logger.info(f"UPLOAD_FOLDER set to: {app.config['UPLOAD_FOLDER']}")
    app.logger.info(
        f"SAMPLES_BASE_DIR set to: {
            app.config['SAMPLES_BASE_DIR']}"
    )

    # --- Database Initialization ---
    # This is called every time create_app() is run.
    # init_db() itself is idempotent (CREATE TABLE IF NOT EXISTS).
    # For development, this is convenient. For production, consider CLI
    # commands.
    with app.app_context():
        # Initialize the database and create tables.
        # The database URL is taken from src.database.utils.DATABASE_URL.
        # get_session_local().bind.engine.url provides the actual URL being
        # used.
        init_db()
        app.logger.info(
            f"Database initialized. DB located at: {
                get_engine().url}"
        )

    # --- Request-scoped Database Session (Alternative) ---
    # The current approach in routes.py is to create/close sessions per route.
    # An alternative Flask pattern is to use `g` object and app context handlers:
    #
    # @app.before_request
    # def before_request_hook():
    #     g.db = get_session_local()() # Create a session
    #
    # @app.teardown_appcontext
    # def teardown_db_session(exception=None):
    #     db = g.pop('db', None)
    #     if db is not None:
    #         db.close()
    #
    # Routes would then access `g.db`. This can simplify session handling in
    # routes.

    # --- Register Blueprints ---
    app.register_blueprint(projects_bp)
    app.register_blueprint(recordings_bp)
    app.register_blueprint(samples_bp)
    app.logger.info("API Blueprints registered.")

    # Register UI Blueprint
    app.register_blueprint(ui_bp, url_prefix="/ui")
    app.logger.info(
        f"UI Blueprint registered with prefix /ui. Templates expected at {
            ui_bp.template_folder} relative to blueprint, and {
            app.template_folder} relative to app root."
    )

    # --- Basic Error Handling ---
    @app.errorhandler(404)
    def not_found_error(error):
        """Handles 404 Not Found errors with a JSON response."""
        app.logger.warning(f"404 Not Found: {request.path} (Error: {error})")
        return (
            jsonify(
                {
                    "error": "Not Found",
                    "message": "The requested URL was not found on the server.",
                }
            ),
            404,
        )

    @app.errorhandler(500)
    def internal_server_error(error):
        """Handles 500 Internal Server Error with a JSON response."""
        app.logger.error(
            f"500 Internal Server Error: {
                request.path} (Error: {error})",
            exc_info=True,
        )
        return (
            jsonify(
                {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred on the server.",
                }
            ),
            500,
        )

    @app.route("/")
    def index():
        """A simple root route to indicate the API is running."""
        return jsonify(
            {"message": "Welcome to the Audio Processing and Sample Management API!"}
        )

    return app


# --- Main Execution ---
if __name__ == "__main__":
    # This block is executed when the script is run directly (e.g., `python -m src.app`).
    # It's primarily for development purposes.
    current_app_instance = create_app()

    # Ensure essential data directories exist before starting the server.
    # These directories are configured in `create_app`.
    for folder_key in ["UPLOAD_FOLDER", "SAMPLES_BASE_DIR"]:
        folder_path = current_app_instance.config.get(folder_key)
        if folder_path and not os.path.exists(folder_path):
            try:
                os.makedirs(folder_path, exist_ok=True)
                current_app_instance.logger.info(
                    f"Successfully created data directory: {folder_path}"
                )
            except OSError as e:
                current_app_instance.logger.error(
                    f"Error creating data directory {folder_path}: {e}", exc_info=True
                )
                # Depending on severity, might exit here.

    # Note: For production, use a dedicated WSGI server like Gunicorn or Waitress
    # instead of Flask's built-in development server.
    # Example: gunicorn -w 4 "src.app:create_app()"
    current_app_instance.logger.info("Starting Flask development server...")
    current_app_instance.run(
        # Enable debug mode for development (auto-reloads, debugger)
        debug=True,
        host="0.0.0.0",  # Listen on all available network interfaces
        port=5000,  # Standard port for Flask dev server
    )
