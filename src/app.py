"""
This module serves as the main entry point for the Flask application.
It defines the application factory `create_app` which initializes the Flask app,
configures it, sets up database connections, registers API blueprints,
and defines basic error handlers and a root route.

The application can be run directly using `python -m src.app` for development.
"""

# Standard library imports
import os
from pathlib import Path
from typing import Any, Dict, Optional

# Third-party imports
from flask import Flask, jsonify, request
from flask_cors import CORS

# Local application imports
from src.api.routes import projects_bp, recordings_bp, samples_bp
from src.ui.routes import ui_bp  # Import the UI blueprint
from src.ui.data_routes import data_bp # Import the data UI blueprint
from src.ui.test_bp import test_bp  # Import the test blueprint
from src.database.utils import get_db

# Import models to ensure they are registered with SQLAlchemy
import src.database.models  # noqa: F401

# --- Application Factory ---
from typing import Tuple
from werkzeug.exceptions import HTTPException


def create_app() -> Flask:
    """Creates, configures, and returns an instance of the Flask application.

    This function serves as the application factory. Its responsibilities include:
    1.  Initializing the core Flask application object.
    2.  Setting up application-level configuration parameters. This includes
        defining paths for data storage such as upload folders and sample
        directories. These paths are constructed relative to the project root.
    3.  Registering various API blueprints that define the application's routes
        and endpoints. This includes blueprints for project management,
        recordings, samples, and user interface components.
    4.  Defining global error handlers for common HTTP error codes like 404 (Not Found)
        and 500 (Internal Server Error). These handlers ensure that such errors
        are returned as JSON responses.
    5.  Establishing a simple root ("/") route that provides a basic welcome
        message, useful for health checks or initial API interaction.

    Database initialization (`init_db`) is *not* performed automatically within
    this function upon app creation. It is expected to be handled manually or
    through a separate process, such as a CLI command or a migration tool,
    especially in production environments.

    Returns:
        Flask: The fully configured Flask application instance, ready to be run
               by a WSGI server or the Flask development server.
    """
    app: Flask = Flask(__name__)
    
    # Load configuration from environment or use defaults
    app.config.update(
        SECRET_KEY=os.environ.get('FLASK_SECRET_KEY', 'dev-key-change-in-production'),
        SQLALCHEMY_DATABASE_URI=os.environ.get('DATABASE_URL', 'sqlite:///orchestrator.db'),
        SQLALCHEMY_TRACK_MODIFICATIONS=False
    )

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
        f"SAMPLES_BASE_DIR set to: {app.config['SAMPLES_BASE_DIR']}"
    )

    # --- Database Initialization ---
    # This is called every time create_app() is run.
    # init_db() itself is idempotent (CREATE TABLE IF NOT EXISTS).
    # For development, this is convenient. For production, consider CLI
    # commands.
    #
    # Previously, database initialization (init_db()) was called here
    # within an app_context. This has been removed to prevent automatic
    # database creation on app startup.
    # Database initialization should now be handled manually,
    # e.g., by running `python -m src.database.utils`
    # or using a dedicated CLI command/migration tool (like Alembic).

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

    # Register UI Blueprint with /ui prefix
    app.register_blueprint(ui_bp, url_prefix='/ui')
    app.logger.info(
        f"UI Blueprint registered with prefix /ui. Templates expected at {ui_bp.template_folder} relative to blueprint, and {app.template_folder} relative to app root."
    )

    # Register Data UI Blueprint with /ui prefix
    app.register_blueprint(data_bp, url_prefix='/ui')
    app.logger.info(
        f"Data UI Blueprint registered with prefix /ui. Templates expected at {data_bp.template_folder} relative to blueprint, and {app.template_folder} relative to app root."
    )
    
    # Register test blueprint
    app.register_blueprint(test_bp)
    app.logger.info("Test Blueprint registered with prefix /test")

    # --- Basic Error Handling ---
    @app.errorhandler(404)
    def not_found_error(error: HTTPException) -> Tuple[Flask.response_class, int]:
        """Global error handler for 404 Not Found errors.

        This function is registered with Flask to handle all occurrences of
        HTTP 404 errors throughout the application. It ensures that 404 errors
        are returned to the client as a JSON response, conforming to a common
        API error structure. It also logs the occurrence of the 404 error,
        including the path that was not found.

        Args:
            error (HTTPException): The exception object raised by Flask or Werkzeug
                                   for the 404 error. This argument is provided
                                   by Flask when the error handler is invoked.

        Returns:
            Tuple[Flask.response_class, int]: A tuple containing a Flask JSON
                response object and the HTTP status code 404. The JSON response
                includes an "error" key set to "Not Found" and a "message" key
                with a user-friendly explanation.
        """
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
    def internal_server_error(error: HTTPException) -> Tuple[Flask.response_class, int]:
        """Global error handler for 500 Internal Server Error.

        This function is registered with Flask to handle all unhandled exceptions
        that result in an HTTP 500 error. It standardizes the error response
        format to JSON, providing a consistent experience for API clients.
        Crucially, it logs the error details, including the request path and
        a full traceback (`exc_info=True`), which is essential for debugging
        server-side issues.

        Args:
            error (HTTPException): The exception object that led to the 500 error.
                                   This argument is provided by Flask. While often
                                   a generic `HTTPException` for 500, it can be
                                   the original unhandled exception.

        Returns:
            Tuple[Flask.response_class, int]: A tuple containing a Flask JSON
                response object and the HTTP status code 500. The JSON response
                includes an "error" key set to "Internal Server Error" and a
                "message" key with a generic explanation, avoiding exposure of
                sensitive error details to the client.
        """
        app.logger.error(
            f"500 Internal Server Error: {request.path} (Error: {error})",
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
    def index() -> Flask.response_class:
        """Provides a simple root endpoint for the API.

        This route serves as a basic health check or welcome point for the API.
        Accessing the root URL ("/") of the application will return a JSON
        response indicating that the API is running and welcoming the user.

        Args:
            None.

        Returns:
            Flask.response_class: A Flask response object containing a JSON payload.
                The JSON object has a single key "message" with a welcome string.
        """
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
        port=5001,  # Using port 5001 to avoid conflicts with AirPlay
    )
