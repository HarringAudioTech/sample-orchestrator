# pylint: disable=too-many-lines
"""
API tests for recording-related routes.

This module contains tests for adding recordings to projects, listing recordings,
retrieving recording details, and processing recordings via the Flask API endpoints.
It uses pytest fixtures for app setup, test client, and isolated database state.
"""

import os
import wave # For creating dummy WAV file
from io import BytesIO
from unittest.mock import patch, ANY # ANY is needed for some mock assertions

from flask import Flask
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app import create_app
from src.database.models import Base, Recording as RecordingModel
# Imports moved from within test functions to top-level
from src.core.workflows import WORKFLOW_REGISTRY, BaseWorkflow, register_workflow, _camel_to_snake
from src.core.stage_runner import STAGE_REGISTRY, register_stage
from src.core.processing_stages import AudioProcessingStage, DATA_TYPE_FILE_PATH, DATA_TYPE_LIST_OF_SAMPLE_DATA


# --- Test Helper Classes (moved from inside tests to module level) ---

class APITestWorkflow(BaseWorkflow):
    """A minimal workflow definition for API testing purposes."""
    @property
    def name(self) -> str: return "api_test_workflow" # pylint: disable=invalid-name
    @property
    def description(self) -> str: return "API Test Workflow"
    @property
    def stages_definition(self) -> list: return []

class APITestChainStage(AudioProcessingStage):
    """A minimal audio processing stage for API chain testing."""
    @property
    def name(self) -> str: return "api_chain_dummy_stage" # pylint: disable=invalid-name
    @property
    def description(self) -> str: return "Dummy stage for API chain tests"
    @property
    def input_type(self) -> str: return DATA_TYPE_FILE_PATH
    @property
    def output_type(self) -> str: return DATA_TYPE_LIST_OF_SAMPLE_DATA
    @property
    def default_params(self) -> dict: return {}
    def process(self, data, params, context=None):
        """Simulates processing and creating a sample file entry."""
        output_dir = context.get("output_sample_dir", "/tmp") if context else "/tmp"
        return [{"sample_id":1, "path":f"{output_dir}/s.wav"}]


# --- Test Fixtures ---

@pytest.fixture(scope="module")
def app() -> Flask:
    """
    Create and configure a new Flask app instance for the test module.
    Sets up test-specific upload and samples directories.
    """
    flask_app = create_app()
    upload_folder = str(flask_app.config.get('UPLOAD_FOLDER', "/tmp/pytest_uploads_recordings_api"))
    samples_base_dir = str(flask_app.config.get('SAMPLES_BASE_DIR', "/tmp/pytest_samples_base_recordings_api"))

    flask_app.config.update({
        "TESTING": True,
        "UPLOAD_FOLDER": upload_folder,
        "SAMPLES_BASE_DIR": samples_base_dir
    })
    
    os.makedirs(flask_app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(flask_app.config['SAMPLES_BASE_DIR'], exist_ok=True)

    yield flask_app

@pytest.fixture
def client(app: Flask):
    """
    Provides a test client for the Flask application.
    """
    return app.test_client()

@pytest.fixture(autouse=True)
def manage_database_session(app: Flask):
    """
    Manages the database for each test function.
    Patches database utilities (ENGINE, SESSION_LOCAL) for an in-memory SQLite DB,
    creates tables before each test, and drops them after, ensuring test isolation.
    """
    test_db_url = "sqlite:///:memory:"
    test_engine = create_engine(test_db_url)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    with patch("src.database.utils.ENGINE", test_engine), \
         patch("src.database.utils.SESSION_LOCAL", TestSessionLocal):
        with app.app_context():
            Base.metadata.create_all(bind=test_engine)
        
        yield
        
        with app.app_context():
            Base.metadata.drop_all(bind=test_engine)

@pytest.fixture
def sample_project(client) -> int:
    """
    Creates a sample project using the API and returns its ID.
    Ensures a project context exists for tests that require it.
    """
    response = client.post('/projects', json={"name": "Test Project for Recordings API"})
    assert response.status_code == 201, "Failed to create sample project for tests."
    return response.get_json()["id"]

# --- Recording Route Tests ---

DUMMY_AUDIO_PATH_FOR_API_TESTS = "tests/fixtures/dummy_api_test_audio.wav" # Module constant

@pytest.fixture(scope="module", autouse=True)
def ensure_dummy_audio_file_for_api_module():
    """
    Ensure the dummy audio WAV file is available for tests in this module.
    This is module-scoped and runs automatically once per test session for this module.
    """
    os.makedirs(os.path.dirname(DUMMY_AUDIO_PATH_FOR_API_TESTS), exist_ok=True)
    if not os.path.exists(DUMMY_AUDIO_PATH_FOR_API_TESTS):
        with wave.open(DUMMY_AUDIO_PATH_FOR_API_TESTS, 'wb') as wf:
            wf.setnchannels(1) # Mono
            wf.setsampwidth(2) # 16-bit
            wf.setframerate(44100) # Standard sample rate
            wf.writeframes(b'\x00\x00' * 44100) # 1 second of silence
        # Use print for fixtures, or inject logger if absolutely necessary
        print(f"Created global dummy audio for API tests: {DUMMY_AUDIO_PATH_FOR_API_TESTS}")

@pytest.fixture
def test_recording_for_processing(app: Flask, sample_project: int) -> int:
    """
    Creates a test recording in the database, associated with `sample_project`,
    using the dummy audio file. Returns the recording ID.
    """
    project_id = sample_project
    abs_dummy_audio_path = os.path.abspath(DUMMY_AUDIO_PATH_FOR_API_TESTS)
    assert os.path.exists(abs_dummy_audio_path), ( # Wrapped for line length
        f"Dummy audio file missing at {abs_dummy_audio_path}")

    recording_id = None
    with app.app_context(): # Ensure DB operations occur within Flask app context
        # Since manage_database_session patches utils, routes will use the test DB.
        # For direct DB access in fixtures/tests, use the patched utils:
        from src.database.utils import SESSION_LOCAL # Use patched version
        db_session = SESSION_LOCAL()
        try:
            new_rec = RecordingModel(
                project_id=project_id, name="API Processable Rec",
                file_path=abs_dummy_audio_path, status="pending",
                duration_seconds=1.0, samplerate=44100, channels=1
            )
            db_session.add(new_rec)
            db_session.commit()
            recording_id = new_rec.id
        finally:
            db_session.close()
    assert recording_id is not None, "Failed to create recording for processing test."
    return recording_id


@patch('src.core.project.Project.add_recording')
def test_add_project_recording_success(mock_add_recording, client, sample_project: int):
    """
    Test successfully adding a recording to a project.
    Mocks `CoreProject.add_recording` to isolate API layer behavior.
    """
    project_id = sample_project
    upload_folder = client.application.config['UPLOAD_FOLDER']
    mock_file_path = os.path.join(upload_folder, f"project_{project_id}", "test_audio.wav")

    mock_recording_instance = RecordingModel(
        id=1, project_id=project_id, name="Test Uploaded Recording", 
        file_path=mock_file_path, status="pending",
        duration_seconds=1.0, samplerate=44100, channels=1
    )
    mock_add_recording.return_value = mock_recording_instance
    
    form_data = {
        'name': 'Test Uploaded Recording',
        'file': (BytesIO(b"dummy wav data"), 'test_audio.wav')
    }
    
    project_specific_upload_dir = os.path.join(upload_folder, f"project_{project_id}")
    os.makedirs(project_specific_upload_dir, exist_ok=True)

    response = client.post(
        f'/projects/{project_id}/recordings',
        data=form_data,
        content_type='multipart/form-data'
    )
    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data["name"] == "Test Uploaded Recording"
    mock_add_recording.assert_called_once_with(
        file_path=ANY, name='Test Uploaded Recording'
    )

@patch('src.core.project.Project.list_recordings')
def test_list_project_recordings_success(
    mock_list_recordings, client, sample_project: int
):
    """
    Test successfully listing recordings for a project.
    Mocks `CoreProject.list_recordings` to isolate API layer behavior.
    """
    project_id = sample_project
    mock_recordings_list = [
        RecordingModel(
            id=1, name="Rec A", project_id=project_id, file_path="a.wav", status="pending",
            duration_seconds=1.0, samplerate=44100, channels=1
        ),
        RecordingModel(
            id=2, name="Rec B", project_id=project_id, file_path="b.wav", status="processed",
            duration_seconds=2.0, samplerate=48000, channels=2
        )
    ]
    mock_list_recordings.return_value = mock_recordings_list
    
    response = client.get(f'/projects/{project_id}/recordings')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2
    mock_list_recordings.assert_called_once()

def test_get_recording_details_success(client, sample_project: int):
    """
    Test successfully retrieving details for a specific recording.
    Creates a recording directly in the DB for this test.
    """
    project_id = sample_project
    recording_id = None
    with client.application.app_context():
        from src.database.utils import SESSION_LOCAL # Use the patched version
        
        db_session = SESSION_LOCAL()
        try:
            new_rec = RecordingModel(
                project_id=project_id, name="Detail Test Rec", file_path="detail.wav",
                status="pending", duration_seconds=3.0, samplerate=44100, channels=1
            )
            db_session.add(new_rec)
            db_session.commit()
            recording_id = new_rec.id
        finally:
            db_session.close()
    
    assert recording_id is not None, "Failed to create test recording in DB"

    response = client.get(f'/recordings/{recording_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data["name"] == "Detail Test Rec"
    assert data["id"] == recording_id

@patch('src.core.workflows.BaseWorkflow.run') # Patching the specific method
def test_process_recording_with_workflow_success(
    mock_workflow_run, client, test_recording_for_processing: int
):
    """
    Test successfully processing a recording with a named workflow.
    Mocks the workflow's `run` method to isolate API logic.
    """
    recording_id = test_recording_for_processing
    mock_workflow_run.return_value = {
        "status": "workflow_completed", "details": "Mocked workflow output"
    }

    workflow_key = _camel_to_snake(APITestWorkflow.__name__)
    
    original_workflow_registry = WORKFLOW_REGISTRY.copy()
    WORKFLOW_REGISTRY.clear()
    register_workflow(APITestWorkflow)

    response = client.post(f'/recordings/{recording_id}/process', json={
        "workflow_name": workflow_key, 
        "output_dir_suffix": "api_workflow_test"
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert f"Processing via workflow '{workflow_key}' completed" in data["message"]
    assert data["output_location"].endswith("api_workflow_test")
    assert data["result"]["status"] == "workflow_completed"
    
    mock_workflow_run.assert_called_once()
    call_context = mock_workflow_run.call_args.kwargs['context']
    assert call_context['recording_id'] == recording_id
    # Wrapped for line length and clarity
    expected_output_dir_suffix = os.path.join(
        f"recording_{recording_id}", "api_workflow_test"
    )
    assert call_context['output_sample_dir'].endswith(expected_output_dir_suffix)

    WORKFLOW_REGISTRY.clear()
    WORKFLOW_REGISTRY.update(original_workflow_registry)

@patch('src.core.stage_runner.execute_stage_chain') # Patching the specific function
def test_process_recording_with_stages_chain_success(
    mock_execute_chain, client, test_recording_for_processing: int
):
    """
    Test successfully processing a recording with an ad-hoc stage chain.
    Mocks `execute_stage_chain` to isolate API logic.
    """
    recording_id = test_recording_for_processing
    mock_execute_chain.return_value = [{"sample_id": 1, "path": "/mocked/sample.wav"}]

    original_stage_registry = STAGE_REGISTRY.copy()
    STAGE_REGISTRY.clear()
    register_stage(APITestChainStage)

    stages_chain_payload = [{"stage_name": "api_chain_dummy_stage", "params": {}}]
    
    response = client.post(f'/recordings/{recording_id}/process', json={
        "stages_chain": stages_chain_payload,
        "output_dir_suffix": "api_chain_test"
    })
    
    assert response.status_code == 200
    data = response.get_json()
    assert "Processing via ad-hoc stage chain completed" in data["message"]
    assert data["output_location"].endswith("api_chain_test")
    assert len(data["result"]) == 1
    
    mock_execute_chain.assert_called_once()
    call_context = mock_execute_chain.call_args.kwargs['context']
    assert call_context['recording_id'] == recording_id
    assert mock_execute_chain.call_args.kwargs['chain_definition'] == stages_chain_payload

    STAGE_REGISTRY.clear()
    STAGE_REGISTRY.update(original_stage_registry)


def test_process_recording_no_workflow_or_chain(
    client, test_recording_for_processing: int
):
    """
    Test POST /recordings/<id>/process fails (400) if neither 'workflow_name'
    nor 'stages_chain' is provided in the JSON payload.
    """
    recording_id = test_recording_for_processing
    response = client.post(
        f'/recordings/{recording_id}/process',
        json={"output_dir_suffix": "test_failure"}
    )
    assert response.status_code == 400
    json_data = response.get_json()
    assert "error" in json_data
    assert "Either 'workflow_name' or 'stages_chain' must be provided" in json_data["error"]

def test_process_recording_unknown_workflow_name(
    client, test_recording_for_processing: int
):
    """
    Test POST /recordings/<id>/process fails (400) if a 'workflow_name' is
    provided that does not exist in the WORKFLOW_REGISTRY.
    """
    recording_id = test_recording_for_processing
    response = client.post(
        f'/recordings/{recording_id}/process',
        json={"workflow_name": "non_existent_workflow_api"}
    )
    assert response.status_code == 400
    json_data = response.get_json()
    assert "error" in json_data
    assert "Workflow 'non_existent_workflow_api' not found" in json_data["error"]

@patch('src.api.routes.os.makedirs', side_effect=OSError("Simulated permission error"))
def test_process_recording_output_dir_creation_fails(
    mock_os_makedirs_in_route, client, test_recording_for_processing: int # Renamed mock
):
    """
    Test POST /recordings/<id>/process error handling (500) when `os.makedirs`
    for the output sample directory fails (e.g., due to permissions).
    Mocks `os.makedirs` as called from within `src.api.routes`.
    """
    recording_id = test_recording_for_processing
    
    workflow_key = _camel_to_snake(APITestWorkflow.__name__)
    original_workflow_registry = WORKFLOW_REGISTRY.copy()
    WORKFLOW_REGISTRY.clear()
    if workflow_key not in WORKFLOW_REGISTRY: 
        register_workflow(APITestWorkflow)

    response = client.post(
        f'/recordings/{recording_id}/process',
        json={"workflow_name": workflow_key} 
    )
    
    assert response.status_code == 500
    json_data = response.get_json()
    assert "error" in json_data
    assert "Could not create output directory: Simulated permission error" in json_data["error"]
    mock_os_makedirs_in_route.assert_called_once()

    WORKFLOW_REGISTRY.clear()
    WORKFLOW_REGISTRY.update(original_workflow_registry)

def test_process_recording_invalid_recording_file_path(
    app: Flask, client, sample_project: int # app fixture needed for app_context
):
    """
    Test POST /recordings/<id>/process fails (400) if the recording's
    associated audio `file_path` attribute points to a non-existent file.
    """
    project_id = sample_project
    recording_id_invalid_path = None
    with app.app_context():
        from src.database.utils import SESSION_LOCAL # Use patched
        db = SESSION_LOCAL()
        try:
            rec = RecordingModel(
                project_id=project_id, name="Rec Invalid Path",
                file_path="/invalid/path/does/not/exist.wav", status="pending",
                duration_seconds=1.0, samplerate=44100, channels=1
            )
            db.add(rec)
            db.commit()
            recording_id_invalid_path = rec.id
        finally:
            db.close()
    
    assert recording_id_invalid_path is not None, "Failed to create rec with invalid path."
    
    workflow_key = _camel_to_snake(APITestWorkflow.__name__)
    if workflow_key not in WORKFLOW_REGISTRY:
        register_workflow(APITestWorkflow)

    response = client.post(
        f'/recordings/{recording_id_invalid_path}/process',
        json={"workflow_name": workflow_key}
    )
    assert response.status_code == 400
    json_data = response.get_json()
    assert "error" in json_data
    assert "Recording file path not found or invalid" in json_data["error"]
