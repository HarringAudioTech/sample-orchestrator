"""
This module defines the API routes for the Flask application using Blueprints.
It includes routes for managing projects, recordings, and samples.
Each set of routes is organized into its own Blueprint.
"""

import os
from flask import Blueprint, request, jsonify, current_app, flash, redirect, url_for
from werkzeug.utils import secure_filename
from src.core.project import Project as CoreProject
from src.core.project_manager import ProjectManager

# --- Configuration ---
# Default paths for generated samples if not set in app config.
# DEFAULT_UPLOAD_BASE_DIR is now managed by ProjectManager
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
# The get_db_session() helper is removed. Routes will use get_db() directly.

# Note: Flask's typical pattern for request-scoped sessions involves using `g`
# and `app.before_request`/`app.teardown_appcontext`. For simplicity in this module,
# sessions are managed directly within each route handler using the get_db() context manager.


# --- Helper Functions ---
from typing import Any, Dict, List, Optional, Union, Set
from flask import Response


def model_to_dict(model_instance: Optional[Any]) -> Optional[Dict[str, Any]]:
    """Converts a SQLAlchemy model instance into a dictionary.

    This is a generic helper to serialize model instances for JSON responses.
    It uses the __dict__ attribute to get all instance attributes, filtering out
    private attributes and SQLAlchemy internal attributes.

    For ProjectModel, it adds a computed 'is_virtual_instrument' field.

    Args:
        model_instance: An instance of a SQLAlchemy model.

    Returns:
        A dictionary representation of the model instance,
        or None if `model_instance` is None.
    """
    if model_instance is None:
        return None

    # Start with a dictionary of all public attributes
    result = {}
    
    # Get all attributes from the model instance
    for key, value in model_instance.__dict__.items():
        # Skip private attributes and SQLAlchemy internal attributes
        if not key.startswith('_'):
            # Convert datetime objects to ISO format strings
            if hasattr(value, 'isoformat'):
                value = value.isoformat()
            result[key] = value
    
    # Add computed fields for ProjectModel and its subclasses
    if hasattr(model_instance, 'project_type'):
        result['is_virtual_instrument'] = getattr(model_instance, 'project_type', None) == 'virtual_instrument'

    return result


# --- Project Endpoints ---
@projects_bp.route("", methods=["POST"])
def create_project() -> Response:
    """Creates a new project.

    Receives project information as JSON and saves it to the database.

    Args:
        None: Reads project details from the JSON payload of the request.
              Required fields: 'name', 'project_type' (one of 'sample_pack' or 'virtual_instrument')
              Optional fields: 'description', 'base_note', 'velocity_layers', 'round_robins', 'metadata_json'
              
              Example for sample pack:
              {
                  "name": "Drum Kit",
                  "project_type": "sample_pack",
                  "description": "Acoustic drum samples"
              }
              
              Example for virtual instrument:
              {
                  "name": "Piano",
                  "project_type": "virtual_instrument",
                  "description": "Grand piano virtual instrument",
                  "base_note": 60,
                  "velocity_layers": 3,
                  "round_robins": 2,
                  "metadata_json": {"instrument_type": "piano", "tuning": "A440"}
              }

    Returns:
        flask.Response: JSON response containing the created project object and
                        HTTP status 201 if successful.
                        JSON response with an error message and HTTP status 400
                        if required fields are missing or invalid.
                        JSON response with an error message and HTTP status 500
                        if an internal server error occurs.
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400
        
    # Validate required fields
    if "name" not in data:
        return jsonify({"error": "Project name is required"}), 400
        
    if "project_type" not in data:
        return jsonify({"error": "Project type is required"}), 400
        
    # Validate project_type
    project_type = data.get("project_type")
    if project_type not in ["sample_pack", "virtual_instrument"]:
        return jsonify({"error": "Invalid project_type. Must be 'sample_pack' or 'virtual_instrument'"}), 400
        
    # Validate virtual instrument specific fields if applicable
    if project_type == "virtual_instrument":
        base_note = data.get("base_note")
        if base_note is not None and (not isinstance(base_note, int) or base_note < 0 or base_note > 127):
            return jsonify({"error": "base_note must be a valid MIDI note number (0-127)"}), 400
            
        velocity_layers = data.get("velocity_layers")
        if velocity_layers is not None and (not isinstance(velocity_layers, int) or velocity_layers < 1):
            return jsonify({"error": "velocity_layers must be a positive integer"}), 400
            
        round_robins = data.get("round_robins")
        if round_robins is not None and (not isinstance(round_robins, int) or round_robins < 1):
            return jsonify({"error": "round_robins must be a positive integer"}), 400

    # Extract project data
    name = data.get("name")
    description = data.get("description")
    metadata_json = data.get("metadata_json")

    # Use the context manager pattern for database session handling
    with get_db() as db:
        try:
            # Create project in database with the appropriate subclass based on project_type
            common_args = {
                "name": name,
                "description": description,
                "metadata_json": metadata_json
            }
            
            if project_type == ProjectType.VIRTUAL_INSTRUMENT:
                project = VirtualInstrumentModel(
                    **common_args,
                    base_note=data.get("base_note"),
                    velocity_layers=data.get("velocity_layers"),
                    round_robins=data.get("round_robins")
                )
            else:  # SAMPLE_PACK
                project = SamplePackModel(
                    **common_args
                )
            
            db.add(project)
            db.commit()
            db.refresh(project)

            # Create project directory using the class method
            project_path = ProjectManager.create_project_directory(
                project_id=project.id,
                project_type=project_type,
                app_config=current_app.config
            )

            return jsonify(model_to_dict(project)), 201

        except Exception as e:
            db.rollback()
            current_app.logger.error(f"Error creating project: {str(e)}")
            return jsonify({"error": "Failed to create project"}), 500


@projects_bp.route("/<int:project_id>", methods=["GET"])
def get_project(project_id: int) -> Response:
    """Retrieves a specific project by its ID.

    Fetches a project from the database based on the provided project ID.
    The response includes all project fields, including virtual instrument
    specific fields if the project is of type 'virtual_instrument'.

    Args:
        project_id (int): The unique identifier of the project to retrieve.

    Returns:
        flask.Response: JSON response containing the project object and HTTP
                        status 200 if found.
                        JSON response with an error message and HTTP status 404
                        if the project is not found.
    """
    with get_db() as db:
        try:
            project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            if not project:
                return jsonify({"error": "Project not found"}), 404
                
            # Get the project data as a dictionary
            project_data = model_to_dict(project)
            
            # Add any computed fields if needed
            if project.project_type == "virtual_instrument":
                project_data["is_virtual_instrument"] = True
                # Add any computed virtual instrument specific fields here
            else:
                project_data["is_virtual_instrument"] = False
                
            return jsonify(project_data), 200
            
        except Exception as e:
            current_app.logger.error(f"Error retrieving project {project_id}: {str(e)}")
            return jsonify({"error": "Internal server error"}), 500


@projects_bp.route("", methods=["GET"])
def list_projects() -> Response:
    """Lists all projects.

    Retrieves all projects from the database, including virtual instrument
    specific fields for each project if applicable.

    Args:
        None.

    Query Parameters:
        project_type (str, optional): Filter projects by type ('sample_pack' or 'virtual_instrument')

    Returns:
        flask.Response: JSON response containing a list of all project
                        objects (filtered by type if specified) and HTTP status 200.
    """
    project_type = request.args.get('project_type')
    
    with get_db() as db:
        try:
            # Start with base query
            query = db.query(ProjectModel)
            
            # Apply filter if project_type is specified
            if project_type:
                if project_type not in ["sample_pack", "virtual_instrument"]:
                    return jsonify({"error": "Invalid project_type. Must be 'sample_pack' or 'virtual_instrument'"}), 400
                query = query.filter(ProjectModel.project_type == project_type)
            
            # Execute query and get results
            projects = query.order_by(ProjectModel.created_at.desc()).all()
            
            # Convert projects to dictionary and add computed fields
            result = []
            for project in projects:
                project_data = model_to_dict(project)
                project_data["is_virtual_instrument"] = project.project_type == "virtual_instrument"
                result.append(project_data)
                
            return jsonify(result), 200
            
        except Exception as e:
            current_app.logger.error(f"Error listing projects: {str(e)}")
            return jsonify({"error": "Failed to retrieve projects"}), 500


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

    project_upload_dir = ProjectManager.get_project_upload_dir(project_id, current_app.config)

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


ALLOWED_EXTENSIONS: Set[str] = {'wav', 'aiff', 'wave', 'aif'}

def allowed_file(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@projects_bp.route("/<int:project_id>/upload_audio", methods=["POST"])
def upload_project_audio(project_id: int) -> Response:
    """Handles audio file uploads for a specific project.

    Expects 'multipart/form-data' with 'audio_file' and 'recording_name'.
    Validates file type and saves the file, then adds recording metadata to DB.
    This is similar to 'add_project_recording' but intended for use with
    the UI form that specifies 'audio_file' and 'recording_name'.

    Args:
        project_id (int): The ID of the project to associate the audio with.

    Returns:
        flask.Response: Redirects to the import audio UI page with flash messages.
                        Returns JSON error for critical issues like project not found.
    """
    try:
        # Validate project existence early. If project not found, UI context is lost.
        core_proj = CoreProject(project_id=project_id)
    except ValueError as e:
        current_app.logger.info(f"Project ID {project_id} not found for audio upload: {e}")
        # For this error, a JSON response is appropriate as the page context is invalid.
        return jsonify({"error": f"Project with ID {project_id} not found."}), 404

    redirect_url = url_for('ui_bp.import_project_audio_ui', project_id=project_id)

    if 'audio_file' not in request.files:
        flash("No audio_file part in the request.", "error")
        return redirect(redirect_url)

    file = request.files['audio_file']
    recording_name: Optional[str] = request.form.get("recording_name")

    if not recording_name:
        flash("Recording name ('recording_name') is required in form data.", "error")
        return redirect(redirect_url)
    if not file.filename:
        flash("No selected file (filename is empty).", "error")
        return redirect(redirect_url)

    if not allowed_file(file.filename):
        flash(f"File type not allowed. Allowed extensions: {', '.join(ALLOWED_EXTENSIONS)}", "error")
        return redirect(redirect_url)

    project_upload_dir = ProjectManager.get_project_upload_dir(project_id, current_app.config)

    if not os.path.exists(project_upload_dir):
        try:
            os.makedirs(project_upload_dir)
            current_app.logger.info(f"Created upload directory: {project_upload_dir}")
        except OSError as e:
            current_app.logger.error(
                f"Error creating upload directory {project_upload_dir}: {e}", exc_info=True,
            )
            flash(f"Could not create upload directory: {e.strerror}", "error")
            return redirect(redirect_url)

    filename = secure_filename(file.filename)
    file_path = os.path.join(project_upload_dir, filename)

    try:
        file.save(file_path)
        current_app.logger.info(f"Audio file saved to {file_path} for project {project_id}")
    except Exception as e:
        current_app.logger.error(
            f"Error saving uploaded audio file to {file_path}: {e}", exc_info=True
        )
        flash(f"Could not save uploaded audio file: {str(e)}", "error")
        return redirect(redirect_url)

    try:
        new_recording_model = core_proj.add_recording(file_path=file_path, name=recording_name)
        current_app.logger.info(
            f"Recording '{new_recording_model.name}' (ID: {new_recording_model.id}) "
            f"added to project {project_id} via upload_project_audio endpoint."
        )
        flash(f"Audio '{new_recording_model.name}' uploaded successfully!", "success")
        flash(f"Recording ID: {new_recording_model.id}, Name: {new_recording_model.name}, File: {new_recording_model.file_path}", "info")
        return redirect(redirect_url)
    except FileNotFoundError as e: # Should be rare
        current_app.logger.error(
            f"File not found during add_recording call for {file_path}: {e}", exc_info=True
        )
        if os.path.exists(file_path): # Attempt cleanup
            try: os.remove(file_path)
            except OSError as rm_e: current_app.logger.error(f"Error cleaning up {file_path}: {rm_e}")
        flash(f"File operation error after save: {str(e)}", "error")
        return redirect(redirect_url)
    except Exception as e: # General DB or other core logic errors
        current_app.logger.error(
            f"Error adding recording DB entry for {file_path}: {e}", exc_info=True
        )
        if os.path.exists(file_path): # Attempt cleanup
            try: os.remove(file_path)
            except OSError as rm_e: current_app.logger.error(f"Error cleaning up {file_path}: {rm_e}")
        flash(f"Could not add recording to database: {str(e)}", "error")
        return redirect(redirect_url)


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
        import src.core.stages.decent_sampler_export_stage # noqa: F401

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
