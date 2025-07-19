"""
This module defines the API routes for the Flask application using Blueprints.
It includes routes for managing projects, recordings, and samples.
Each set of routes is organized into its own Blueprint.

SQLITE ONLY: These routes use the new SQLite-based database models.
Do not attempt to modify for compatibility with other database engines.
"""

import os
from flask import Blueprint, request, jsonify, current_app, flash, redirect, url_for
from werkzeug.utils import secure_filename

# SQLITE ONLY: Import SQLite database models and utilities
from src.database.models import Project, Recording, Sample, model_to_dict
from src.database.utils import get_db

# --- Configuration ---
# SQLITE ONLY: Default paths for generated samples if not set in app config
DEFAULT_SAMPLES_BASE_DIR = "data/projects"


# --- Blueprints ---
# SQLITE ONLY: Blueprint for project-related operations
projects_bp = Blueprint("projects", __name__, url_prefix="/projects")
# SQLITE ONLY: Blueprint for recording-related operations
recordings_bp = Blueprint("recordings", __name__, url_prefix="/recordings")
# SQLITE ONLY: Blueprint for sample-related operations
samples_bp = Blueprint("samples", __name__, url_prefix="/samples")


# --- Helper Functions ---
from typing import Any, Dict, List, Optional, Union, Set
from flask import Response


# --- Project Endpoints ---
@projects_bp.route("", methods=["POST"])
def create_project() -> Response:
    """Creates a new project using SQLite database.

    SQLITE ONLY: This route creates projects in the SQLite database.

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
                  "base_note": "C4",
                  "velocity_layers": 3,
                  "round_robins": 2
              }

    Returns:
        flask.Response: JSON response containing the created project object and
                        HTTP status 201 if successful.
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
        velocity_layers = data.get("velocity_layers")
        if velocity_layers is not None and (not isinstance(velocity_layers, int) or velocity_layers < 1):
            return jsonify({"error": "velocity_layers must be a positive integer"}), 400
            
        round_robins = data.get("round_robins")
        if round_robins is not None and (not isinstance(round_robins, int) or round_robins < 1):
            return jsonify({"error": "round_robins must be a positive integer"}), 400

    # SQLITE ONLY: Use SQLite database session
    with get_db() as db:
        try:
            # Create project using new SQLite model
            project = Project(
                name=data.get("name"),
                description=data.get("description"),
                project_type=project_type,
                base_note=data.get("base_note"),
                velocity_layers=data.get("velocity_layers", 1),
                round_robins=data.get("round_robins", 1),
                metadata_json=data.get("metadata_json")
            )
            
            db.add(project)
            db.commit()
            db.refresh(project)

            # Create project directory structure
            project_dir = os.path.join(current_app.config.get("SAMPLES_BASE_DIR", DEFAULT_SAMPLES_BASE_DIR), f"project_{project.id}")
            subdirs = ["samples/raw", "samples/processed", "samples/mapped", "exports", "metadata", "presets"]
            
            for subdir in subdirs:
                full_path = os.path.join(project_dir, subdir)
                os.makedirs(full_path, exist_ok=True)
            
            current_app.logger.info(f"Created project directory structure: {project_dir}")

            return jsonify(model_to_dict(project)), 201

        except Exception as e:
            current_app.logger.error(f"Error creating project: {str(e)}")
            return jsonify({"error": "Failed to create project"}), 500


@projects_bp.route("/<int:project_id>", methods=["GET"])
def get_project(project_id: int) -> Response:
    """Retrieves a specific project by its ID from SQLite database.

    SQLITE ONLY: This route fetches projects from the SQLite database.

    Args:
        project_id (int): The unique identifier of the project to retrieve.

    Returns:
        flask.Response: JSON response containing the project object and HTTP
                        status 200 if found.
    """
    with get_db() as db:
        try:
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return jsonify({"error": "Project not found"}), 404
                
            return jsonify(model_to_dict(project)), 200
            
        except Exception as e:
            current_app.logger.error(f"Error retrieving project {project_id}: {str(e)}")
            return jsonify({"error": "Internal server error"}), 500


@projects_bp.route("", methods=["GET"])
def list_projects() -> Response:
    """Lists all projects from SQLite database.

    SQLITE ONLY: This route lists projects from the SQLite database.

    Query Parameters:
        project_type (str, optional): Filter projects by type ('sample_pack' or 'virtual_instrument')

    Returns:
        flask.Response: JSON response containing a list of all project objects.
    """
    project_type = request.args.get('project_type')
    
    with get_db() as db:
        try:
            # Start with base query
            query = db.query(Project)
            
            # Apply filter if project_type is specified
            if project_type:
                if project_type not in ["sample_pack", "virtual_instrument"]:
                    return jsonify({"error": "Invalid project_type. Must be 'sample_pack' or 'virtual_instrument'"}), 400
                query = query.filter(Project.project_type == project_type)
            
            # Execute query and get results
            projects = query.order_by(Project.created_at.desc()).all()
            
            # Convert projects to dictionary
            result = [model_to_dict(project) for project in projects]
                
            return jsonify(result), 200
            
        except Exception as e:
            current_app.logger.error(f"Error listing projects: {str(e)}")
            return jsonify({"error": "Failed to retrieve projects"}), 500


# --- Recording Endpoints (scoped under a project) ---
@projects_bp.route("/<int:project_id>/recordings", methods=["POST"])
def add_project_recording(project_id: int) -> Response:
    """Adds a new recording to a specified project by uploading an audio file.

    SQLITE ONLY: This route uses SQLite database for storing recording metadata.

    Expects 'multipart/form-data' with 'file' (the audio file) and
    'name' (recording name).

    Args:
        project_id (int): The unique identifier of the project to which the
                          recording will be added.

    Returns:
        flask.Response: JSON response containing the created recording object
                        and HTTP status 201 if successful.
    """
    # Validate project exists
    with get_db() as db:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return jsonify({"error": "Project not found"}), 404

    if "file" not in request.files:
        return jsonify({"error": "No file part in the request"}), 400

    file = request.files["file"]
    recording_name: Optional[str] = request.form.get("name")

    if not recording_name:
        return jsonify({"error": "Recording name is required in form data"}), 400
    if file.filename == "":
        return jsonify({"error": "No selected file (filename is empty)"}), 400

    # Create upload directory for project
    upload_base = current_app.config.get("UPLOAD_FOLDER", "data/uploads")
    project_upload_dir = os.path.join(upload_base, f"project_{project_id}")

    if not os.path.exists(project_upload_dir):
        try:
            os.makedirs(project_upload_dir)
            current_app.logger.info(f"Created upload directory: {project_upload_dir}")
        except OSError as e:
            current_app.logger.error(f"Error creating upload directory {project_upload_dir}: {e}")
            return jsonify({"error": f"Could not create upload directory"}), 500

    filename = secure_filename(file.filename)
    file_path = os.path.join(project_upload_dir, filename)

    try:
        file.save(file_path)
        current_app.logger.info(f"File saved to {file_path}")
    except Exception as e:
        current_app.logger.error(f"Error saving uploaded file to {file_path}: {e}")
        return jsonify({"error": "Could not save uploaded file"}), 500

    try:
        # SQLITE ONLY: Create recording in SQLite database
        with get_db() as db:
            recording = Recording(
                project_id=project_id,
                name=recording_name,
                file_path=file_path,
                processing_status="pending"
            )
            
            db.add(recording)
            db.commit()
            db.refresh(recording)

            current_app.logger.info(f"Recording '{recording.name}' (ID: {recording.id}) added to project {project_id}")
            return jsonify(model_to_dict(recording)), 201
            
    except Exception as e:
        current_app.logger.error(f"Error adding recording to database: {e}")
        # Clean up uploaded file if database operation failed
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                current_app.logger.info(f"Cleaned up orphaned file: {file_path}")
            except OSError:
                pass
        return jsonify({"error": "Could not add recording to database"}), 500


@projects_bp.route("/<int:project_id>/recordings", methods=["GET"])
def list_project_recordings(project_id: int) -> Response:
    """Lists all recordings associated with a specific project.

    SQLITE ONLY: This route lists recordings from the SQLite database.

    Args:
        project_id (int): The unique identifier of the project whose
                          recordings are to be listed.

    Returns:
        flask.Response: JSON response containing a list of recording objects.
    """
    with get_db() as db:
        try:
            # Verify project exists
            project = db.query(Project).filter(Project.id == project_id).first()
            if not project:
                return jsonify({"error": "Project not found"}), 404

            # Get recordings for this project
            recordings = db.query(Recording).filter(Recording.project_id == project_id).all()
            return jsonify([model_to_dict(r) for r in recordings]), 200
            
        except Exception as e:
            current_app.logger.error(f"Error listing recordings for project {project_id}: {str(e)}")
            return jsonify({"error": "Failed to retrieve recordings"}), 500


ALLOWED_EXTENSIONS: Set[str] = {'wav', 'aiff', 'wave', 'aif'}

def allowed_file(filename: str) -> bool:
    """Check if uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@projects_bp.route("/<int:project_id>/upload_audio", methods=["POST"])
def upload_project_audio(project_id: int) -> Response:
    """Handles audio file uploads for a specific project via UI form.

    SQLITE ONLY: This route uses SQLite database for recording metadata.
    
    Expects 'multipart/form-data' with 'audio_file' and 'recording_name'.
    Intended for use with the web UI.

    Args:
        project_id (int): The ID of the project to associate the audio with.

    Returns:
        flask.Response: Redirects to the import audio UI page with flash messages.
    """
    # Validate project exists first
    with get_db() as db:
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            return jsonify({"error": f"Project with ID {project_id} not found."}), 404

    # For UI redirects - this would need the UI blueprint to exist
    # For now, just return JSON responses
    if 'audio_file' not in request.files:
        return jsonify({"error": "No audio_file part in the request"}), 400

    file = request.files['audio_file']
    recording_name: Optional[str] = request.form.get("recording_name")

    if not recording_name:
        return jsonify({"error": "Recording name ('recording_name') is required"}), 400
    if not file.filename:
        return jsonify({"error": "No selected file (filename is empty)"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": f"File type not allowed. Allowed extensions: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    # Create upload directory for project
    upload_base = current_app.config.get("UPLOAD_FOLDER", "data/uploads")
    project_upload_dir = os.path.join(upload_base, f"project_{project_id}")

    if not os.path.exists(project_upload_dir):
        try:
            os.makedirs(project_upload_dir)
            current_app.logger.info(f"Created upload directory: {project_upload_dir}")
        except OSError as e:
            current_app.logger.error(f"Error creating upload directory {project_upload_dir}: {e}")
            return jsonify({"error": "Could not create upload directory"}), 500

    filename = secure_filename(file.filename)
    file_path = os.path.join(project_upload_dir, filename)

    try:
        file.save(file_path)
        current_app.logger.info(f"Audio file saved to {file_path} for project {project_id}")
    except Exception as e:
        current_app.logger.error(f"Error saving uploaded audio file to {file_path}: {e}")
        return jsonify({"error": "Could not save uploaded audio file"}), 500

    try:
        # SQLITE ONLY: Create recording in SQLite database
        with get_db() as db:
            recording = Recording(
                project_id=project_id,
                name=recording_name,
                file_path=file_path,
                processing_status="pending"
            )
            
            db.add(recording)
            db.commit()
            db.refresh(recording)

            current_app.logger.info(f"Recording '{recording.name}' (ID: {recording.id}) added to project {project_id}")
            return jsonify({
                "message": f"Audio '{recording.name}' uploaded successfully!",
                "recording": model_to_dict(recording)
            }), 201
            
    except Exception as e:
        current_app.logger.error(f"Error adding recording to database: {e}")
        # Clean up uploaded file if database operation failed
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        return jsonify({"error": "Could not add recording to database"}), 500


# --- Standalone Recording and Sample Endpoints ---

@recordings_bp.route("/<int:recording_id>", methods=["GET"])
def get_recording_details(recording_id: int) -> Response:
    """Retrieves details for a specific recording by its ID.

    SQLITE ONLY: This route fetches recordings from the SQLite database.

    Args:
        recording_id (int): The unique identifier of the recording to retrieve.

    Returns:
        flask.Response: JSON response containing the recording object.
    """
    with get_db() as db:
        try:
            recording = db.query(Recording).filter(Recording.id == recording_id).first()
            if not recording:
                return jsonify({"error": "Recording not found"}), 404
            return jsonify(model_to_dict(recording)), 200
        except Exception as e:
            current_app.logger.error(f"Error retrieving recording {recording_id}: {str(e)}")
            return jsonify({"error": "Internal server error"}), 500


@recordings_bp.route("/<int:recording_id>/process", methods=["POST"])
def process_recording_endpoint(recording_id: int) -> Response:
    """Initiates audio processing for a specific recording.

    SQLITE ONLY: This endpoint processes recordings using the SQLite database.

    Args:
        recording_id (int): The unique identifier of the recording to be processed.
            JSON payload can contain:
            - workflow_name (str, optional): Name of a registered workflow to run.
            - stages_chain (List[Dict[str, Any]], optional): List of stage definitions.
            - output_dir_suffix (str, optional): Output directory suffix.

    Returns:
        flask.Response: JSON response with processing results.
    """
    with get_db() as db:
        try:
            # Import audio processing modules
            from src.core.stage_runner import execute_stage_chain, STAGE_REGISTRY
            from src.core.workflows import WORKFLOW_REGISTRY, BaseWorkflow
            from src.core.processing_stages import DATA_TYPE_FILE_PATH
            
            # Import specific stages to ensure they're registered
            try:
                import src.core.stages.slicing_stage  # noqa: F401
                import src.core.stages.noise_reduction_stage  # noqa: F401
                import src.core.stages.decent_sampler_export_stage  # noqa: F401
            except ImportError as e:
                current_app.logger.warning(f"Some processing stages could not be imported: {e}")

            json_data = request.get_json()
            if not json_data:
                return jsonify({"error": "Request body must be JSON"}), 400

            workflow_name = json_data.get("workflow_name")
            stages_chain = json_data.get("stages_chain")
            output_dir_suffix = json_data.get("output_dir_suffix", "default_processing_output")

            # Get recording and validate
            recording = db.query(Recording).filter(Recording.id == recording_id).first()
            if not recording:
                return jsonify({"error": "Recording not found"}), 404

            if not recording.project_id:
                return jsonify({"error": "Recording is not associated with a project"}), 500

            # Get associated project
            project = db.query(Project).filter(Project.id == recording.project_id).first()
            if not project:
                return jsonify({"error": f"Associated project {recording.project_id} not found"}), 500

            # Validate file exists
            if not recording.file_path or not os.path.exists(recording.file_path):
                return jsonify({"error": f"Recording file not found: {recording.file_path}"}), 400

            # Set up output directory
            samples_base_dir = current_app.config.get("SAMPLES_BASE_DIR", DEFAULT_SAMPLES_BASE_DIR)
            output_sample_dir = os.path.join(
                samples_base_dir, 
                f"project_{recording.project_id}",
                f"recording_{recording.id}",
                output_dir_suffix
            )

            try:
                os.makedirs(output_sample_dir, exist_ok=True)
                current_app.logger.info(f"Created output directory: {output_sample_dir}")
            except OSError as e:
                current_app.logger.error(f"Error creating output directory: {e}")
                return jsonify({"error": "Could not create output directory"}), 500

            # Set up processing context
            context = {
                "db_session": db,
                "project_id": recording.project_id,
                "recording_id": recording.id,
                "output_sample_dir": output_sample_dir,
            }

            # Execute processing
            if workflow_name:
                workflow_class = WORKFLOW_REGISTRY.get(workflow_name)
                if not workflow_class:
                    available = list(WORKFLOW_REGISTRY.keys())
                    return jsonify({
                        "error": f"Workflow '{workflow_name}' not found. Available: {available}"
                    }), 400

                workflow_instance = workflow_class()
                processing_result = workflow_instance.run(
                    initial_data=recording.file_path,
                    initial_data_type=DATA_TYPE_FILE_PATH,
                    context=context
                )
                processing_type = f"workflow '{workflow_name}'"

            elif stages_chain:
                if not isinstance(stages_chain, list):
                    return jsonify({"error": "'stages_chain' must be a list"}), 400

                processing_result = execute_stage_chain(
                    initial_data=recording.file_path,
                    initial_data_type=DATA_TYPE_FILE_PATH,
                    chain_definition=stages_chain,
                    context=context
                )
                processing_type = "ad-hoc stage chain"

            else:
                return jsonify({
                    "error": "Either 'workflow_name' or 'stages_chain' must be provided"
                }), 400

            # Update recording status
            recording.processing_status = "completed"
            db.commit()

            return jsonify({
                "message": f"Processing via {processing_type} completed for recording {recording_id}",
                "recording_status": recording.processing_status,
                "output_location": output_sample_dir,
                "result_summary": f"Output type: {type(processing_result).__name__}",
                "result": processing_result if isinstance(processing_result, (list, dict)) else str(processing_result)
            }), 200

        except Exception as e:
            current_app.logger.error(f"Error processing recording {recording_id}: {e}")
            return jsonify({"error": f"Processing failed: {str(e)}"}), 500


@recordings_bp.route("/<int:recording_id>/samples", methods=["GET"])
def list_recording_samples(recording_id: int) -> Response:
    """Lists all samples associated with a specific recording.

    SQLITE ONLY: This route lists samples from the SQLite database.

    Args:
        recording_id (int): The unique identifier of the recording whose
                          samples are to be listed.

    Returns:
        flask.Response: JSON response containing a list of sample objects and
                        HTTP status 200 if the recording is found.
                        JSON response with an error message and HTTP status 404
                        if the recording is not found.
    """
    with get_db() as db:
        try:
            recording = db.query(Recording).filter(Recording.id == recording_id).first()
            if not recording:
                return jsonify({"error": "Recording not found"}), 404
                
            samples = db.query(Sample).filter(Sample.recording_id == recording_id).all()
            return jsonify([model_to_dict(s) for s in samples]), 200
            
        except Exception as e:
            current_app.logger.error(f"Error listing samples for recording {recording_id}: {str(e)}")
            return jsonify({"error": "Failed to retrieve samples"}), 500


@samples_bp.route("/<int:sample_id>", methods=["GET"])
def get_sample_details(sample_id: int) -> Response:
    """Retrieves details for a specific sample by its ID.

    SQLITE ONLY: This route fetches samples from the SQLite database.

    Args:
        sample_id (int): The unique identifier of the sample to retrieve.

    Returns:
        flask.Response: JSON response containing the sample object and HTTP
                        status 200 if found.
                        JSON response with an error message and HTTP status 404
                        if the sample is not found.
    """
    with get_db() as db:
        try:
            sample = db.query(Sample).filter(Sample.id == sample_id).first()
            if not sample:
                return jsonify({"error": "Sample not found"}), 404
            return jsonify(model_to_dict(sample)), 200
        except Exception as e:
            current_app.logger.error(f"Error retrieving sample {sample_id}: {str(e)}")
            return jsonify({"error": "Internal server error"}), 500
