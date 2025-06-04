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
from src.database.utils import get_db  # Replaced SessionLocal with get_db
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


# --- Mock Task Progress Simulation Data ---
# In a real app, this state would be in a database or a proper task queue system.
mock_task_progress_db: Dict[str, Dict[str, Any]] = {}
WORKFLOW_STAGES_SIMULATION: List[Dict[str, Any]] = [
    {"id": "noise_reduction", "name": "Noise Reduction", "duration_estimate": 2},
    {"id": "slicing", "name": "Slicing", "duration_estimate": 3},
    {"id": "pitch_labeling", "name": "Pitch & Labeling", "duration_estimate": 2.5}
]


# --- Database Session Management ---
# The get_db_session() helper is removed. Routes will use get_db() directly.

# Note: Flask's typical pattern for request-scoped sessions involves using `g`
# and `app.before_request`/`app.teardown_appcontext`. For simplicity in this module,
# sessions are managed directly within each route handler using the get_db() context manager.


# --- Helper Functions ---
from typing import Any, Dict, List, Optional, Union
from flask import Response


def model_to_dict(model_instance: Optional[Any]) -> Optional[Dict[str, Any]]:
    """Converts a SQLAlchemy model instance into a dictionary.

    This is a generic helper to serialize model instances for JSON responses.
    It iterates over the model's table columns and retrieves their values.
    Currently, it does not deeply serialize relationships to avoid complexity
    and potential circular dependencies in responses.

    Args:
        model_instance: An instance of a SQLAlchemy model.

    Returns:
        A dictionary representation of the model instance,
        or None if `model_instance` is None.
    """
    if model_instance is None:
        return None

    d: Dict[str, Any] = {}
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
def create_project() -> Response:
    """Creates a new project.

    Receives project information as JSON and saves it to the database.

    Args:
        None: Reads 'name' and 'description' (optional) from the JSON
              payload of the request.
              Example: {"name": "My First Project", "description": "A test project"}

    Returns:
        flask.Response: JSON response containing the created project object and
                        HTTP status 201 if successful.
                        JSON response with an error message and HTTP status 400
                        if the 'name' is missing in the payload.
                        JSON response with an error message and HTTP status 500
                        if an internal server error occurs.
    """
    data: Optional[Dict[str, Any]] = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"error": "Project name is required"}), 400

    db_gen = get_db()
    db = next(db_gen)
    try:
        new_project = ProjectModel(name=data["name"], description=data.get("description"))
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
        next(db_gen, None)


@projects_bp.route("/<int:project_id>", methods=["GET"])
def get_project(project_id: int) -> Response:
    """Retrieves a specific project by its ID.

    Fetches a project from the database based on the provided project ID.

    Args:
        project_id (int): The unique identifier of the project to retrieve.

    Returns:
        flask.Response: JSON response containing the project object and HTTP
                        status 200 if found.
                        JSON response with an error message and HTTP status 404
                        if the project is not found.
    """
    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            return jsonify({"error": "Project not found"}), 404
        return jsonify(model_to_dict(project)), 200
    finally:
        next(db_gen, None)


@projects_bp.route("", methods=["GET"])
def list_projects() -> Response:
    """Lists all projects.

    Retrieves all projects from the database.

    Args:
        None.

    Returns:
        flask.Response: JSON response containing a list of all project
                        objects and HTTP status 200.
    """
    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        projects: List[ProjectModel] = db.query(ProjectModel).all()
        return jsonify([model_to_dict(p) for p in projects]), 200
    finally:
        next(db_gen, None)


@projects_bp.route("/<int:project_id>/upload_audio", methods=["POST"])
def upload_audio_and_process(project_id: int) -> Response:
    """
    Handles audio file upload for a specific project, adds it as a recording,
    and initiates a (placeholder) processing workflow.
    """
    db: Optional[Session] = None
    full_file_path: Optional[str] = None  # To track if file was saved for cleanup

    try:
        db_gen = get_db()
        db = next(db_gen)

        # 1. Verify project existence
        project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if not project:
            current_app.logger.warning(f"Upload attempt for non-existent project ID: {project_id}")
            return jsonify({"error": "Project not found"}), 404

        # 2. Handle file upload
        if "file" not in request.files:
            return jsonify({"error": "No file part in the request"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file (filename is empty)"}), 400

        original_filename = file.filename
        # HTML form does not have a 'name' field, so this defaults to original_filename
        recording_name = request.form.get("name", original_filename)

        # Ensure filename is not None before processing
        if not original_filename:
             return jsonify({"error": "Invalid file name"}), 400

        # Path construction
        upload_folder_base = current_app.config.get("UPLOAD_FOLDER", DEFAULT_UPLOAD_BASE_DIR)
        project_upload_dir = os.path.join(upload_folder_base, f"project_{project_id}")

        if not os.path.exists(project_upload_dir):
            try:
                os.makedirs(project_upload_dir)
                current_app.logger.info(f"Created upload directory: {project_upload_dir}")
            except OSError as e:
                current_app.logger.error(
                    f"Error creating upload directory {project_upload_dir}: {e}",
                    exc_info=True,
                )
                return jsonify({"error": f"Could not create upload directory: {e.strerror}"}), 500

        filename_secure = secure_filename(original_filename)
        full_file_path = os.path.join(project_upload_dir, filename_secure)

        try:
            file.save(full_file_path)
            current_app.logger.info(f"File saved to {full_file_path} for project {project_id}")
        except Exception as e:
            current_app.logger.error(
                f"Error saving uploaded file to {full_file_path}: {e}", exc_info=True
            )
            # full_file_path might not be set if secure_filename failed, though unlikely.
            # If it was set and save failed, the file might be partially written or not at all.
            # No specific cleanup needed here for the file itself if save fails.
            return jsonify({"error": f"Could not save uploaded file: {str(e)}"}), 500

        # 3. Add recording to database
        # CoreProject might use its own session, but for consistency and to ensure
        # we use the same session as project validation, we use the one from get_db().
        # However, CoreProject is designed to fetch its own project model.
        # For this specific endpoint, we directly use the db session.

        core_proj = CoreProject(project_id=project_id, db_session=db) # Pass session to CoreProject

        try:
            # Assuming add_recording can now use the passed db_session
            new_recording = core_proj.add_recording(
                file_path=full_file_path,
                name=recording_name
            )
            # No explicit commit needed here if CoreProject.add_recording handles it
            # and uses the passed session. If not, db.commit() would be needed.
            # For now, assuming CoreProject handles its session unit of work.
            # If CoreProject.add_recording uses db.add and db.commit internally with the passed session,
            # then we need to refresh here if we want to use the ID immediately.
            # Let's assume add_recording returns a committed & refreshed object or we don't need immediate refresh for the response.
            # For safety, let's assume add_recording handles its own commit with the provided session.
            # db.refresh(new_recording) # Potentially needed if add_recording doesn't refresh

            current_app.logger.info(
                f"Recording '{new_recording.name}' (ID: {new_recording.id}) "
                f"added to project {project_id} in database."
            )
        except Exception as e:
            current_app.logger.error(
                f"Error adding recording to database for project {project_id}, file {full_file_path}: {e}",
                exc_info=True,
            )
            # Attempt to clean up the saved file if DB operation fails
            if full_file_path and os.path.exists(full_file_path):
                try:
                    os.remove(full_file_path)
                    current_app.logger.info(f"Cleaned up orphaned file: {full_file_path}")
                except OSError as rm_e:
                    current_app.logger.error(
                        f"Error cleaning up orphaned file {full_file_path}: {rm_e}",
                        exc_info=True,
                    )
            return jsonify({"error": "Could not add recording to database"}), 500

        # 4. Initiate workflow (placeholder)
        task_id = f"task_for_recording_{new_recording.id}"
        current_app.logger.info(
            f"Placeholder: Workflow initiation for recording ID {new_recording.id} "
            f"in project {project_id} with task_id {task_id}. "
            f"File: {new_recording.file_path}"
        )
        # In a real scenario, this would likely involve:
        # - Creating a task entry in a database.
        # - Enqueuing a job in a task queue (e.g., Celery, RQ).
        # - The task would then run the actual audio processing pipeline.

        # 5. Return JSON response
        return jsonify({
            "message": "File uploaded successfully and processing initiated.",
            "recording_id": new_recording.id,
            "recording_name": new_recording.name,
            "file_path": new_recording.file_path,
            "task_id": task_id,
            "status_url": f"/projects/{project_id}/tasks/{task_id}/status" # Placeholder URL
        }), 201

    except Exception as e:
        # Catch-all for unexpected errors
        current_app.logger.error(
            f"Unexpected error in upload_audio_and_process for project {project_id}: {e}",
            exc_info=True,
        )
        # Attempt to clean up if file was saved before the error
        if full_file_path and os.path.exists(full_file_path):
            # This check is more crucial here if an error occurred *after* file save
            # but *before* or *during* DB operation where specific cleanup isn't hit.
            # However, the specific cleanup after DB failure is more targeted.
            # This is a general safety net.
            # Consider if this general cleanup is redundant with the one after DB failure.
            # For now, it is harmless.
            pass # Cleanup handled in specific db error block
        return jsonify({"error": "An unexpected server error occurred"}), 500
    finally:
        if db:
            next(db_gen, None) # Close the session


@projects_bp.route("/<int:project_id>/tasks/<string:task_id>/status", methods=["GET"])
def get_task_status(project_id: int, task_id: str) -> Response:
    """
    Simulates fetching the status of a processing task.
    project_id is included for URL consistency but not used in this mock.
    """
    # project_id is not used in this mock version but would be in a real system
    # to scope tasks to projects.
    # current_app.logger.info(f"Request for task status: {task_id} for project {project_id}")

    if task_id not in mock_task_progress_db:
        # Initialize task if first time seeing it
        mock_task_progress_db[task_id] = {
            "current_stage_idx": 0,
            "overall_status": "Pending", # Initial status
            "stages_status": [
                {"name": stage["name"], "status": "Pending"} for stage in WORKFLOW_STAGES_SIMULATION
            ]
        }
        # current_app.logger.info(f"Initialized task {task_id} in mock_task_progress_db.")

    task_state = mock_task_progress_db[task_id]

    # Simulate progress: Advance one step if not completed or failed
    if task_state["overall_status"] not in ["Completed", "Failed"]:
        if task_state["overall_status"] == "Pending":
            task_state["overall_status"] = "Processing"
            # current_app.logger.info(f"Task {task_id} changed from Pending to Processing.")

        current_stage_idx = task_state["current_stage_idx"]

        if current_stage_idx < len(WORKFLOW_STAGES_SIMULATION):
            current_stage_name_for_log = WORKFLOW_STAGES_SIMULATION[current_stage_idx]["name"]
            if task_state["stages_status"][current_stage_idx]["status"] == "Pending":
                task_state["stages_status"][current_stage_idx]["status"] = "In Progress"
                # current_app.logger.info(f"Stage '{current_stage_name_for_log}' for task {task_id} changed to In Progress.")
            else: # If it was "In Progress", now mark it "Completed" and try to move to next
                task_state["stages_status"][current_stage_idx]["status"] = "Completed"
                # current_app.logger.info(f"Stage '{current_stage_name_for_log}' for task {task_id} changed to Completed.")
                task_state["current_stage_idx"] += 1

                if task_state["current_stage_idx"] < len(WORKFLOW_STAGES_SIMULATION):
                    next_stage_name_for_log = WORKFLOW_STAGES_SIMULATION[task_state["current_stage_idx"]]["name"]
                    task_state["stages_status"][task_state["current_stage_idx"]]["status"] = "In Progress"
                    # current_app.logger.info(f"Stage '{next_stage_name_for_log}' for task {task_id} changed to In Progress (as next stage).")
                else:
                    task_state["overall_status"] = "Completed"
                    # current_app.logger.info(f"Task {task_id} changed to Completed (all stages done).")
        else: # Should already be caught by the previous block setting overall_status to "Completed"
             task_state["overall_status"] = "Completed"
             # current_app.logger.info(f"Task {task_id} confirmed Completed (current_stage_idx was already past end).")

    # Calculate overall progress percentage
    total_duration_all_stages = sum(s["duration_estimate"] for s in WORKFLOW_STAGES_SIMULATION)
    current_progress_units = 0.0 # Use float for more precision with half steps
    active_stage_progress_contribution = 0.0

    for i, stage_stat in enumerate(task_state["stages_status"]):
        if stage_stat["status"] == "Completed":
            current_progress_units += WORKFLOW_STAGES_SIMULATION[i]["duration_estimate"]
        elif stage_stat["status"] == "In Progress":
            active_stage_progress_contribution = WORKFLOW_STAGES_SIMULATION[i]["duration_estimate"] / 2.0

    current_progress_units += active_stage_progress_contribution

    progress_percent = (current_progress_units / total_duration_all_stages) * 100 if total_duration_all_stages > 0 else 0

    if task_state["overall_status"] == "Completed":
        progress_percent = 100.0
    elif task_state["overall_status"] == "Pending": # Should show 0 if pending, before any stage is "In Progress"
        progress_percent = 0.0

    current_stage_display_name = "N/A"
    if task_state["overall_status"] == "Processing":
        if task_state["current_stage_idx"] < len(WORKFLOW_STAGES_SIMULATION):
             current_stage_display_name = WORKFLOW_STAGES_SIMULATION[task_state["current_stage_idx"]]["name"]
        else: # This case implies it just completed, but overall_status hasn't flipped to Completed yet in this logic flow
             current_stage_display_name = WORKFLOW_STAGES_SIMULATION[-1]["name"] # Show last stage name
    elif task_state["overall_status"] == "Completed":
        current_stage_display_name = "All Completed"
    elif task_state["overall_status"] == "Pending":
        current_stage_display_name = "Queued"


    # current_app.logger.info(f"Task {task_id} status: {task_state['overall_status']}, current stage: {current_stage_display_name}, progress: {progress_percent}%")

    return jsonify({
        "task_id": task_id,
        "overall_status": task_state["overall_status"],
        "current_stage": current_stage_display_name,
        "progress_percent": round(progress_percent),
        "stages": task_state["stages_status"],
        "results": {"url": f"/projects/{project_id}/results/{task_id}"} if task_state["overall_status"] == "Completed" else None
    }), 200


# --- Recording Endpoints (scoped under a project) ---
@projects_bp.route("/<int:project_id>/recordings", methods=["POST"])
def add_project_recording(project_id: int) -> Response:
    """Adds a new recording to a specified project by uploading an audio file.

    Expects 'multipart/form-data' with 'file' (the audio file) and
    'name' (recording name).

    The uploaded file is saved to a designated upload folder, and metadata
    about the recording is stored in the database.

    Args:
        project_id (int): The unique identifier of the project to which the
                          recording will be added.
                          Reads 'file' (werkzeug.datastructures.FileStorage) and
                          'name' (str) from the multipart/form-data request.

    Returns:
        flask.Response: JSON response containing the created recording object
                        and HTTP status 201 if successful.
                        JSON response with an error message and HTTP status 400
                        if 'file' or 'name' is missing, or if the file has no
                        filename.
                        JSON response with an error message and HTTP status 404
                        if the specified project is not found.
                        JSON response with an error message and HTTP status 500
                        if an internal server error occurs during file saving
                        or database interaction.
    """
    # CoreProject manages its own session for loading the project model and adding recording.
    # No direct db session needed here for *that* part.
    try:
        core_proj = CoreProject(project_id=project_id)  # This might use get_db internally
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["file"]
    recording_name: Optional[str] = request.form.get("name")

    if not recording_name:
        return jsonify({"error": "Recording name is required in form data"}), 400
    if file.filename == "":
        return jsonify({"error": "No selected file (filename is empty)"}), 400

    upload_folder_base = current_app.config.get("UPLOAD_FOLDER", DEFAULT_UPLOAD_BASE_DIR)
    project_upload_dir = os.path.join(upload_folder_base, f"project_{project_id}")

    if not os.path.exists(project_upload_dir):
        try:
            os.makedirs(project_upload_dir)
            current_app.logger.info(f"Created upload directory: {project_upload_dir}")
        except OSError as e:
            current_app.logger.error(
                f"Error creating upload directory {project_upload_dir}: {e}",
                exc_info=True,
            )
            return (
                jsonify({"error": f"Could not create upload directory: {e.strerror}"}),
                500,
            )

    filename = secure_filename(file.filename)
    file_path = os.path.join(project_upload_dir, filename)

    try:
        file.save(file_path)
        current_app.logger.info(f"File saved to {file_path}")
    except Exception as e:
        current_app.logger.error(
            f"Error saving uploaded file to {file_path}: {e}", exc_info=True
        )
        return jsonify({"error": f"Could not save uploaded file: {e}"}), 500

    try:
        # CoreProject.add_recording is expected to use get_db for its session
        new_recording_model = core_proj.add_recording(file_path=file_path, name=recording_name)
        current_app.logger.info(
            f"Recording '{new_recording_model.name}' (ID: {new_recording_model.id}) added to project {project_id}."
        )
        return jsonify(model_to_dict(new_recording_model)), 201
    except FileNotFoundError as e:
        current_app.logger.error(
            f"File not found during add_recording call: {e}", exc_info=True
        )
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(
            f"Error adding recording DB entry for project {project_id} and file {file_path}: {e}",
            exc_info=True,
        )
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                current_app.logger.info(f"Cleaned up orphaned file: {file_path}")
            except OSError as rm_e:
                current_app.logger.error(
                    f"Error cleaning up orphaned file {file_path}: {rm_e}",
                    exc_info=True,
                )
        return jsonify({"error": f"Could not add recording to database: {e}"}), 500


@projects_bp.route("/<int:project_id>/recordings", methods=["GET"])
def list_project_recordings(project_id: int) -> Response:
    """Lists all recordings associated with a specific project.

    Retrieves metadata for all recordings linked to the given project ID.

    Args:
        project_id (int): The unique identifier of the project whose
                          recordings are to be listed.

    Returns:
        flask.Response: JSON response containing a list of recording objects
                        and HTTP status 200 if the project is found.
                        JSON response with an error message and HTTP status 404
                        if the project is not found.
    """
    # CoreProject handles its own session for loading and listing.
    try:
        core_proj = CoreProject(project_id=project_id)  # This might use get_db internally
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    recordings: List[RecordingModel] = core_proj.list_recordings()
    return jsonify([model_to_dict(r) for r in recordings]), 200


# --- Standalone Recording and Sample Endpoints ---


@recordings_bp.route("/<int:recording_id>", methods=["GET"])
def get_recording_details(recording_id: int) -> Response:
    """Retrieves details for a specific recording by its ID.

    Fetches a recording from the database based on its unique identifier.

    Args:
        recording_id (int): The unique identifier of the recording to retrieve.

    Returns:
        flask.Response: JSON response containing the recording object and HTTP
                        status 200 if found.
                        JSON response with an error message and HTTP status 404
                        if the recording is not found.
    """
    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        recording: Optional[RecordingModel] = (
            db.query(RecordingModel).filter(RecordingModel.id == recording_id).first()
        )
        if not recording:
            return jsonify({"error": "Recording not found"}), 404
        return jsonify(model_to_dict(recording)), 200
    finally:
        next(db_gen, None)


@recordings_bp.route("/<int:recording_id>/process", methods=["POST"])
def process_recording_endpoint(recording_id: int) -> Response:
    """Initiates audio processing for a specific recording.

    This endpoint allows processing of a recording using either a predefined
    workflow or an ad-hoc chain of processing stages. The request body
    must be JSON and specify either 'workflow_name' or 'stages_chain'.

    Args:
        recording_id (int): The unique identifier of the recording to be processed.
            The JSON payload can contain:
            - workflow_name (str, optional): Name of a registered workflow to run.
            - stages_chain (List[Dict[str, Any]], optional): A list of stage
              definitions for ad-hoc processing.
            - output_dir_suffix (str, optional): Suffix for the output directory
              where generated samples will be stored. Defaults to
              "default_processing_output".
            Example for workflow:
            `{"workflow_name": "my_slicing_workflow"}`
            Example for ad-hoc chain:
            `{"stages_chain": [{"name": "slicer", "params": {"threshold": -40}}]}`

    Returns:
        flask.Response: JSON response with a success message, recording status,
                        output location, and processing results (HTTP 200).
                        JSON response with an error message (HTTP 400) for
                        invalid request (e.g., missing JSON, bad parameters,
                        workflow/stage not found, file issues).
                        JSON response with an error message (HTTP 404) if the
                        recording or its associated project is not found.
                        JSON response with an error message (HTTP 500) for
                        internal server errors during processing or file system
                        operations.
    """
    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        # --- Imports for this endpoint ---
        from src.core.stage_runner import (
            execute_stage_chain,
            STAGE_REGISTRY,
        )
        from src.core.workflows import WORKFLOW_REGISTRY, BaseWorkflow
        from src.core.processing_stages import DATA_TYPE_FILE_PATH
        import src.core.stages.slicing_stage  # noqa: F401
        import src.core.stages.noise_reduction_stage  # noqa: F401

        json_data: Optional[Dict[str, Any]] = request.get_json()
        if not json_data:
            return jsonify({"error": "Request body must be JSON."}), 400

        workflow_name: Optional[str] = json_data.get("workflow_name")
        stages_chain: Optional[List[Dict[str, Any]]] = json_data.get("stages_chain")
        output_dir_suffix: str = json_data.get(
            "output_dir_suffix", "default_processing_output"
        )

        recording: Optional[RecordingModel] = (
            db.query(RecordingModel).filter(RecordingModel.id == recording_id).first()
        )
        if not recording:
            return jsonify({"error": "Recording not found"}), 404
        if not recording.project_id:
            current_app.logger.error(
                f"Recording {recording_id} is not associated with a project."
            )
            return (
                jsonify(
                    {"error": "Recording is not associated with a project, cannot process."}
                ),
                500,
            )

        project = (
            db.query(ProjectModel).filter(ProjectModel.id == recording.project_id).first()
        )
        if not project:
            current_app.logger.error(
                f"Project {recording.project_id} associated with recording {recording_id} not found."
            )
            return (
                jsonify({"error": f"Associated project {recording.project_id} not found."}),
                500,
            )

        initial_data: Optional[str] = recording.file_path
        initial_data_type: str = DATA_TYPE_FILE_PATH

        if not initial_data or not os.path.exists(initial_data):
            current_app.logger.error(
                f"Recording file path '{initial_data}' for recording {recording_id} not found or is invalid."
            )
            return (
                jsonify(
                    {"error": f"Recording file path not found or invalid: {initial_data}"}
                ),
                400,
            )

        samples_base_dir = current_app.config.get("SAMPLES_BASE_DIR", DEFAULT_SAMPLES_BASE_DIR)
        project_samples_dir = os.path.join(samples_base_dir, f"project_{recording.project_id}")
        recording_samples_dir = os.path.join(project_samples_dir, f"recording_{recording.id}")
        output_sample_dir_for_run = os.path.join(recording_samples_dir, output_dir_suffix)

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
            return jsonify({"error": f"Could not create output directory: {e.strerror}"}), 500

        context = {
            "db_session": db,
            "project_id": recording.project_id,
            "recording_id": recording.id,
            "output_sample_dir": output_sample_dir_for_run,
        }

        processing_result: Any = None
        processing_type: Optional[str] = None

        if workflow_name:
            processing_type = f"workflow '{workflow_name}'"
            WorkflowClass: Optional[type[BaseWorkflow]] = WORKFLOW_REGISTRY.get(workflow_name)
            if not WorkflowClass:
                available_workflows: List[str] = list(WORKFLOW_REGISTRY.keys())
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
                    f"Executing {processing_type} for recording {recording_id}."
                )
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
                    jsonify({"error": f"Failed to execute {processing_type}: {str(e)}"}),
                    500,
                )
        elif stages_chain:
            if not isinstance(stages_chain, list):
                return (
                    jsonify({"error": "'stages_chain' must be a list of stage definitions."}),
                    400,
                )
            processing_type = "ad-hoc stage chain"
            try:
                current_app.logger.info(
                    f"Executing {processing_type} for recording {recording_id}. Chain: {stages_chain}"
                )
                processing_result = execute_stage_chain(
                    initial_data=initial_data,
                    initial_data_type=initial_data_type,
                    chain_definition=stages_chain,
                    context=context,
                )
            except ValueError as e:
                current_app.logger.error(
                    f"Configuration error in {processing_type} for recording {recording_id}: {e}",
                    exc_info=True,
                )
                return (
                    jsonify(
                        {
                            "error": f"Configuration error in stage chain: {str(e)}. Available stages: {list(STAGE_REGISTRY.keys())}"
                        }
                    ),
                    400,
                )
            except TypeError as e:
                current_app.logger.error(
                    f"Type mismatch error in {processing_type} for recording {recording_id}: {e}",
                    exc_info=True,
                )
                return jsonify({"error": f"Type mismatch in stage chain: {str(e)}"}), 400
            except Exception as e:
                current_app.logger.error(
                    f"Error executing {processing_type} for recording {recording_id}: {e}",
                    exc_info=True,
                )
                return (
                    jsonify({"error": f"Failed to execute {processing_type}: {str(e)}"}),
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

        db.refresh(recording)
        return (
            jsonify(
                {
                    "message": f"Processing via {processing_type} completed for recording {recording_id}.",
                    "recording_status": recording.status,
                    "output_location": output_sample_dir_for_run,
                    "result_summary": f"Output type: {type(processing_result).__name__}, items: {len(processing_result) if isinstance(processing_result, list) else 'N/A'}",
                    "result": (
                        processing_result
                        if isinstance(processing_result, (list, dict))
                        else str(processing_result)
                    ),
                }
            ),
            200,
        )
    except Exception as e:
        current_app.logger.error(
            f"Critical error in process_recording_endpoint for recording {recording_id}: {e}",
            exc_info=True,
        )
        return jsonify({"error": f"An unexpected server error occurred: {str(e)}"}), 500
    finally:
        next(db_gen, None)


@recordings_bp.route("/<int:recording_id>/samples", methods=["GET"])
def list_recording_samples(recording_id: int) -> Response:
    """Lists all samples associated with a specific recording.

    Retrieves metadata for all samples linked to the given recording ID.

    Args:
        recording_id (int): The unique identifier of the recording whose
                          samples are to be listed.

    Returns:
        flask.Response: JSON response containing a list of sample objects and
                        HTTP status 200 if the recording is found.
                        JSON response with an error message and HTTP status 404
                        if the recording is not found.
    """
    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        recording: Optional[RecordingModel] = (
            db.query(RecordingModel).filter(RecordingModel.id == recording_id).first()
        )
        if not recording:
            return jsonify({"error": "Recording not found"}), 404
        samples: List[SampleModel] = (
            db.query(SampleModel).filter(SampleModel.recording_id == recording_id).all()
        )
        return jsonify([model_to_dict(s) for s in samples]), 200
    finally:
        next(db_gen, None)


@samples_bp.route("/<int:sample_id>", methods=["GET"])
def get_sample_details(sample_id: int) -> Response:
    """Retrieves details for a specific sample by its ID.

    Fetches a sample from the database based on its unique identifier.

    Args:
        sample_id (int): The unique identifier of the sample to retrieve.

    Returns:
        flask.Response: JSON response containing the sample object and HTTP
                        status 200 if found.
                        JSON response with an error message and HTTP status 404
                        if the sample is not found.
    """
    db_gen = get_db()
    db: Session = next(db_gen)
    try:
        sample: Optional[SampleModel] = (
            db.query(SampleModel).filter(SampleModel.id == sample_id).first()
        )
        if not sample:
            return jsonify({"error": "Sample not found"}), 404
        return jsonify(model_to_dict(sample)), 200
    finally:
        next(db_gen, None)
