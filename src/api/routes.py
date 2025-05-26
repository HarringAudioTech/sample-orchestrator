"""
This module defines the API routes for the Flask application using Blueprints.
It includes routes for managing projects, recordings, and samples.
Each set of routes is organized into its own Blueprint.
"""

import os
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from sqlalchemy.orm import Session

# init_db is not directly used in routes
from src.database.utils import SessionLocal
from src.database.models import (
    Project as ProjectModel,
    Recording as RecordingModel,
    Sample as SampleModel,
)
from src.core.project import Project as CoreProject

# --- Configuration ---
# Default paths for uploads and generated samples if not set in app config.
DEFAULT_UPLOAD_BASE_DIR = "data/uploads"
DEFAULT_SAMPLES_BASE_DIR = "data/projects"


# --- Blueprints ---
# Blueprint for project-related operations.
projects_bp = Blueprint("projects", __name__, url_prefix="/projects")
# Blueprint for recording-related operations (those not directly under a
# project).
recordings_bp = Blueprint("recordings", __name__, url_prefix="/recordings")
# Blueprint for sample-related operations (those not directly under a
# recording).
samples_bp = Blueprint("samples", __name__, url_prefix="/samples")


# --- Database Session Management ---
def get_db_session() -> Session:
    """
    Creates and returns a new SQLAlchemy database session.
    This session is intended to be used for a single request or operation.
    The caller is responsible for closing the session.

    Returns:
        Session: A new SQLAlchemy Session instance.
    """
    db = SessionLocal()
    return db


# Note: Flask's typical pattern for request-scoped sessions involves using `g`
# and `app.before_request`/`app.teardown_appcontext`. For simplicity in this module,
# sessions are created and closed directly within each route handler.


# --- Helper Functions ---
def model_to_dict(model_instance) -> dict | None:
    """
    Converts a SQLAlchemy model instance into a dictionary.

    This is a generic helper to serialize model instances for JSON responses.
    It iterates over the model's table columns and retrieves their values.
    Currently, it does not deeply serialize relationships to avoid complexity
    and potential circular dependencies in responses.

    Args:
        model_instance: An instance of a SQLAlchemy model.

    Returns:
        dict | None: A dictionary representation of the model instance,
                     or None if `model_instance` is None.
    """
    if model_instance is None:
        return None

    d = {}
    for column in model_instance.__table__.columns:
        d[column.name] = getattr(model_instance, column.name)

    # Example of how relationships could be handled (currently commented out):
    # if hasattr(model_instance, 'recordings'):
    #     d['recordings_count'] = len(model_instance.recordings) # Or list of IDs
    # if hasattr(model_instance, 'samples'):
    #     d['samples_count'] = len(model_instance.samples)
    return d


# --- Project Endpoints ---
@projects_bp.route("", methods=["POST"])
def create_project():
    """
    Creates a new project.
    Expects a JSON payload with 'name' and optional 'description'.

    Returns:
        JSON: The created project object (201) or an error message (400, 500).
    """
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Project name is required"}), 400

    db: Session = get_db_session()
    try:
        new_project = ProjectModel(
            name=data["name"], description=data.get("description")
        )
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        current_app.logger.info(f"Project created with ID: {new_project.id}")
        return jsonify(model_to_dict(new_project)), 201
    except Exception as e:
        db.rollback()
        current_app.logger.error(f"Error creating project: {e}", exc_info=True)
        return (
            jsonify({"error": "Could not create project due to an internal error"}),
            500,
        )
    finally:
        db.close()


@projects_bp.route("/<int:project_id>", methods=["GET"])
def get_project(project_id: int):
    """
    Retrieves a specific project by its ID.

    Args:
        project_id (int): The ID of the project to retrieve.

    Returns:
        JSON: The project object (200) or an error message (404).
    """
    db: Session = get_db_session()
    try:
        project = db.query(ProjectModel).filter(
            ProjectModel.id == project_id).first()
        if not project:
            return jsonify({"error": "Project not found"}), 404
        return jsonify(model_to_dict(project)), 200
    finally:
        db.close()


@projects_bp.route("", methods=["GET"])
def list_projects():
    """
    Lists all projects.

    Returns:
        JSON: A list of project objects (200).
    """
    db: Session = get_db_session()
    try:
        projects = db.query(ProjectModel).all()
        return jsonify([model_to_dict(p) for p in projects]), 200
    finally:
        db.close()


# --- Recording Endpoints (scoped under a project) ---
@projects_bp.route("/<int:project_id>/recordings", methods=["POST"])
def add_project_recording(project_id: int):
    """
    Adds a new recording to a specified project by uploading an audio file.
    Expects 'multipart/form-data' with 'file' (the audio file) and 'name' (recording name).

    Args:
        project_id (int): The ID of the project to add the recording to.

    Returns:
        JSON: The created recording object (201) or an error message (400, 404, 500).
    """
    # Initialize CoreProject first to check if project_id is valid.
    # CoreProject's constructor manages its own session for loading the
    # project model.
    try:
        core_proj = CoreProject(project_id=project_id)
    except ValueError as e:  # Raised if project not found by CoreProject
        return jsonify({"error": str(e)}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["file"]
    recording_name = request.form.get("name")

    if not recording_name:
        return jsonify(
            {"error": "Recording name is required in form data"}), 400
    if file.filename == "":
        return jsonify({"error": "No selected file (filename is empty)"}), 400

    # Determine upload directory from app config or use default
    upload_folder_base = current_app.config.get(
        "UPLOAD_FOLDER", DEFAULT_UPLOAD_BASE_DIR
    )
    # Ensure project-specific subdirectory for uploads
    project_upload_dir = os.path.join(
        upload_folder_base, f"project_{project_id}")

    if not os.path.exists(project_upload_dir):
        try:
            os.makedirs(project_upload_dir)
            current_app.logger.info(
                f"Created upload directory: {project_upload_dir}")
        except OSError as e:
            current_app.logger.error(
                f"Error creating upload directory {project_upload_dir}: {e}",
                exc_info=True,
            )
            return (
                jsonify({"error": f"Could not create upload directory: {e.strerror}"}),
                500,
            )

    filename = secure_filename(file.filename)  # Sanitize filename
    file_path = os.path.join(project_upload_dir, filename)

    try:
        file.save(file_path)
        current_app.logger.info(f"File saved to {file_path}")
    except Exception as e:
        current_app.logger.error(
            f"Error saving uploaded file to {file_path}: {e}", exc_info=True
        )
        return jsonify({"error": f"Could not save uploaded file: {e}"}), 500

    # Use CoreProject instance to add the recording to the database.
    # This method handles its own database session internally.
    try:
        new_recording_model = core_proj.add_recording(
            file_path=file_path, name=recording_name
        )
        current_app.logger.info(
            f"Recording '{
                new_recording_model.name}' (ID: {
                new_recording_model.id}) added to project {project_id}."
        )
        return jsonify(model_to_dict(new_recording_model)), 201
    except (
        FileNotFoundError
    ) as e:  # Should be caught by add_recording, but good as a safeguard
        current_app.logger.error(
            f"File not found during add_recording call: {e}", exc_info=True
        )
        return (
            jsonify({"error": str(e)}),
            400,
        )  # Or 500 if it implies internal state issue
    except Exception as e:
        current_app.logger.error(
            f"Error adding recording DB entry for project {project_id} and file {file_path}: {e}",
            exc_info=True,
        )
        # Attempt to clean up the saved file if DB operation fails
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                current_app.logger.info(
                    f"Cleaned up orphaned file: {file_path}")
            except OSError as rm_e:
                current_app.logger.error(
                    f"Error cleaning up orphaned file {file_path}: {rm_e}",
                    exc_info=True,
                )
        return jsonify(
            {"error": f"Could not add recording to database: {e}"}), 500


@projects_bp.route("/<int:project_id>/recordings", methods=["GET"])
def list_project_recordings(project_id: int):
    """
    Lists all recordings associated with a specific project.

    Args:
        project_id (int): The ID of the project whose recordings are to be listed.

    Returns:
        JSON: A list of recording objects (200) or an error message (404).
    """
    # CoreProject handles its own session for loading and listing.
    try:
        core_proj = CoreProject(project_id=project_id)
    except ValueError as e:  # Project not found
        return jsonify({"error": str(e)}), 404

    recordings = core_proj.list_recordings()
    return jsonify([model_to_dict(r) for r in recordings]), 200


# --- Standalone Recording and Sample Endpoints ---
# These allow accessing recordings or samples directly by their IDs,
# without needing to go through a project first (though they are still linked).


@recordings_bp.route("/<int:recording_id>", methods=["GET"])
def get_recording_details(recording_id: int):
    """
    Retrieves details for a specific recording by its ID.

    Args:
        recording_id (int): The ID of the recording.

    Returns:
        JSON: The recording object (200) or an error message (404).
    """
    db: Session = get_db_session()
    try:
        recording = (db.query(RecordingModel).filter(
            RecordingModel.id == recording_id).first())
        if not recording:
            return jsonify({"error": "Recording not found"}), 404
        return jsonify(model_to_dict(recording)), 200
    finally:
        db.close()


@recordings_bp.route("/<int:recording_id>/process", methods=["POST"])
def process_recording_endpoint(recording_id: int):
    """
    Initiates audio processing for a specific recording using a specified workflow
    or an ad-hoc chain of processing stages.

    Request JSON Body can contain:
    - `workflow_name` (str, optional): The name of a registered workflow to execute.
    - `stages_chain` (list[dict], optional): An ad-hoc list of stage definitions
      (e.g., `[{"stage_name": "slicing", "params": {}}]`).
    - `output_dir_suffix` (str, optional): A suffix to append to the default
      output directory for samples generated by this processing run.

    If neither `workflow_name` nor `stages_chain` is provided, a 400 error is returned.
    If both are provided, `workflow_name` takes precedence.

    Args:
        recording_id (int): The ID of the recording to process.

    Returns:
        JSON: A message indicating processing status and results, or an error message.
    """
    db: Session = get_db_session()
    try:
        # --- Imports for this endpoint ---
        from src.core.stage_runner import (
            execute_stage_chain,
            STAGE_REGISTRY,
        )  # Import STAGE_REGISTRY for error messages
        from src.core.workflows import WORKFLOW_REGISTRY, BaseWorkflow
        from src.core.processing_stages import DATA_TYPE_FILE_PATH

        # Ensure all necessary stage modules are imported so they register themselves
        # This is typically done at app startup or by importing the main 'stages' package/module
        # For example, if SlicingStage is in src.core.stages.slicing_stage:
        import src.core.stages.slicing_stage  # noqa: F401 (ensures SlicingStage is registered)
        import src.core.stages.noise_reduction_stage  # noqa: F401 (ensures NoiseReductionStage is registered)

        # --- Request Data ---
        json_data = request.get_json()
        if not json_data:
            return jsonify({"error": "Request body must be JSON."}), 400

        workflow_name = json_data.get("workflow_name")
        stages_chain = json_data.get("stages_chain")
        output_dir_suffix = json_data.get(
            "output_dir_suffix", "default_processing_output"
        )

        # --- Fetch Recording and Project ---
        recording = (db.query(RecordingModel).filter(
            RecordingModel.id == recording_id).first())
        if not recording:
            return jsonify({"error": "Recording not found"}), 404
        if not recording.project_id:
            current_app.logger.error(
                f"Recording {recording_id} is not associated with a project."
            )
            return (
                jsonify(
                    {
                        "error": "Recording is not associated with a project, cannot process."
                    }
                ),
                500,
            )

        # Project query not strictly needed if project_id is on recording, but
        # good for validation
        project = (
            db.query(ProjectModel)
            .filter(ProjectModel.id == recording.project_id)
            .first()
        )
        if not project:
            current_app.logger.error(
                f"Project {
                    recording.project_id} associated with recording {recording_id} not found.")
            return (
                jsonify(
                    {"error": f"Associated project {recording.project_id} not found."}
                ),
                500,
            )

        # --- Prepare for Processing ---
        initial_data = recording.file_path
        initial_data_type = DATA_TYPE_FILE_PATH

        if not initial_data or not os.path.exists(initial_data):
            current_app.logger.error(
                f"Recording file path '{initial_data}' for recording {recording_id} not found or is invalid.")
            return (
                jsonify(
                    {
                        "error": f"Recording file path not found or invalid: {initial_data}"
                    }
                ),
                400,
            )

        samples_base_dir = current_app.config.get(
            "SAMPLES_BASE_DIR", DEFAULT_SAMPLES_BASE_DIR
        )
        # Ensure project-specific base directory exists
        project_samples_dir = os.path.join(
            samples_base_dir, f"project_{recording.project_id}"
        )
        # Then recording-specific directory
        recording_samples_dir = os.path.join(
            project_samples_dir, f"recording_{recording.id}"
        )
        # Finally, the specific output suffix directory for this run
        output_sample_dir_for_run = os.path.join(
            recording_samples_dir, output_dir_suffix
        )

        try:
            os.makedirs(output_sample_dir_for_run, exist_ok=True)
            current_app.logger.info(
                f"Ensured output directory exists: {output_sample_dir_for_run}"
            )
        except OSError as e:
            current_app.logger.error(
                f"Error creating output directory {output_sample_dir_for_run}: {e}",
                exc_info=True,
            )
            return (
                jsonify({"error": f"Could not create output directory: {e.strerror}"}),
                500,
            )

        context = {
            "db_session": db,  # Pass the active session
            "project_id": recording.project_id,
            "recording_id": recording.id,
            "output_sample_dir": output_sample_dir_for_run,
        }

        processing_result = None
        processing_type = None

        # --- Execute Workflow or Stage Chain ---
        if workflow_name:
            processing_type = f"workflow '{workflow_name}'"
            WorkflowClass = WORKFLOW_REGISTRY.get(workflow_name)
            if not WorkflowClass:
                available_workflows = list(WORKFLOW_REGISTRY.keys())
                return (
                    jsonify(
                        {
                            "error": f"Workflow '{workflow_name}' not found. Available workflows: {available_workflows}"
                        }
                    ),
                    400,
                )
            try:
                workflow_instance = WorkflowClass()
                current_app.logger.info(
                    f"Executing {processing_type} for recording {recording_id}.")
                processing_result = workflow_instance.run(
                    initial_data=initial_data,
                    initial_data_type=initial_data_type,
                    context=context,
                )
            except Exception as e:
                current_app.logger.error(
                    f"Error executing {processing_type} for recording {recording_id}: {e}",
                    exc_info=True,
                )
                return (
                    jsonify(
                        {
                            "error": f"Failed to execute {processing_type}: {
                                str(e)}"
                        }
                    ),
                    500,
                )

        elif stages_chain:
            if not isinstance(stages_chain, list):
                return (
                    jsonify(
                        {"error": "'stages_chain' must be a list of stage definitions."}
                    ),
                    400,
                )
            processing_type = "ad-hoc stage chain"
            try:
                current_app.logger.info(
                    f"Executing {processing_type} for recording {recording_id}. Chain: {stages_chain}")
                processing_result = execute_stage_chain(
                    initial_data=initial_data,
                    initial_data_type=initial_data_type,
                    chain_definition=stages_chain,
                    context=context,
                )
            except ValueError as e:  # E.g. stage not found, missing stage_name
                current_app.logger.error(
                    f"Configuration error in {processing_type} for recording {recording_id}: {e}",
                    exc_info=True,
                )
                return (
                    jsonify(
                        {
                            "error": f"Configuration error in stage chain: {
                                str(e)}. Available stages: {
                                list(
                                    STAGE_REGISTRY.keys())}"
                        }
                    ),
                    400,
                )
            except TypeError as e:  # E.g. type mismatch between stages
                current_app.logger.error(
                    f"Type mismatch error in {processing_type} for recording {recording_id}: {e}",
                    exc_info=True,
                )
                return (
                    jsonify({"error": f"Type mismatch in stage chain: {str(e)}"}),
                    400,
                )
            except Exception as e:
                current_app.logger.error(
                    f"Error executing {processing_type} for recording {recording_id}: {e}",
                    exc_info=True,
                )
                return (
                    jsonify(
                        {
                            "error": f"Failed to execute {processing_type}: {
                                str(e)}"
                        }
                    ),
                    500,
                )
        else:
            return (
                jsonify(
                    {
                        "error": "Either 'workflow_name' or 'stages_chain' must be provided in the request body."
                    }
                ),
                400,
            )

        # --- Response ---
        # The status of the recording model in `db` session might have been updated by stages.
        # Refresh it to get the latest state if it was modified by a stage using the same session.
        # If stages create their own sessions, this refresh won't capture those changes unless they also update this session's object.
        # The SlicingStage is designed to use the passed-in db_session.
        db.refresh(recording)

        return (
            jsonify(
                {
                    "message": f"Processing via {processing_type} completed for recording {recording_id}.",
                    "recording_status": recording.status,  # Show updated status
                    "output_location": output_sample_dir_for_run,
                    "result_summary": f"Output type: {type(processing_result).__name__}, items: {len(processing_result) if isinstance(processing_result, list) else 'N/A'}",
                    "result": (
                        processing_result
                        if isinstance(processing_result, (list, dict))
                        else str(processing_result)
                    ),  # Avoid sending complex objects directly
                }
            ),
            200,
        )

    except (
        Exception
    ) as e:  # Catch-all for unexpected errors before specific processing logic
        current_app.logger.error(
            f"Critical error in process_recording_endpoint for recording {recording_id}: {e}",
            exc_info=True,
        )
        return jsonify(
            {"error": f"An unexpected server error occurred: {str(e)}"}), 500
    finally:
        db.close()


@recordings_bp.route("/<int:recording_id>/samples", methods=["GET"])
def list_recording_samples(recording_id: int):
    """
    Lists all samples associated with a specific recording.

    Args:
        recording_id (int): The ID of the recording whose samples are to be listed.

    Returns:
        JSON: A list of sample objects (200) or an error message (404).
    """
    db: Session = get_db_session()
    try:
        # First, verify the recording exists to provide a clear 404 if not.
        recording = (db.query(RecordingModel).filter(
            RecordingModel.id == recording_id).first())
        if not recording:
            return jsonify({"error": "Recording not found"}), 404

        # Then, query for its samples.
        samples = (db.query(SampleModel).filter(
            SampleModel.recording_id == recording_id).all())
        return jsonify([model_to_dict(s) for s in samples]), 200
    finally:
        db.close()


@samples_bp.route("/<int:sample_id>", methods=["GET"])
def get_sample_details(sample_id: int):
    """
    Retrieves details for a specific sample by its ID.

    Args:
        sample_id (int): The ID of the sample.

    Returns:
        JSON: The sample object (200) or an error message (404).
    """
    db: Session = get_db_session()
    try:
        sample = db.query(SampleModel).filter(
            SampleModel.id == sample_id).first()
        if not sample:
            return jsonify({"error": "Sample not found"}), 404
        return jsonify(model_to_dict(sample)), 200
    finally:
        db.close()
