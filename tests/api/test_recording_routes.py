import pytest
import json
import os
from io import BytesIO
from flask import Flask
from unittest.mock import patch, MagicMock, ANY
from src.app import create_app
from src.database.utils import (
    init_db as initialize_db_utils,
    get_engine,
    get_session_local,
)
from src.database.models import (
    Base,
    Project as ProjectModel,
    Recording as RecordingModel,
)
from src.core.project import Project as CoreProject  # Original mock target


# --- Test Fixtures (reuse from test_project_routes or define new ones if needed) ---
@pytest.fixture(scope="module")
def app():
    test_db_url = "sqlite:///:memory:"
    flask_app = create_app()
    flask_app.config.update(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite:///:memory:",  # Use in-memory SQLite for tests
            "UPLOAD_FOLDER": "/tmp/pytest_uploads_recordings_api",
            "SAMPLES_BASE_DIR": "/tmp/pytest_samples_base_recordings_api",
        }
    )

    # Create an engine instance specifically for tests, using the test DB URL
    engine = get_engine(flask_app.config["DATABASE_URL"])
    flask_app.test_engine = engine  # Attach to app for access in other fixtures

    with flask_app.app_context():
        # Initialize the database schema using the test-specific engine
        initialize_db_utils(engine_instance=engine)
        # Note: The tables are created once per module.
        # manage_database_session will handle per-test data cleaning.

    # Ensure test-specific folders exist
    os.makedirs(flask_app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(flask_app.config["SAMPLES_BASE_DIR"], exist_ok=True)

    yield flask_app
    # No explicit teardown needed for _engine or _SessionLocal patching


@pytest.fixture
def client(app: Flask):
    return app.test_client()


@pytest.fixture(autouse=True)  # Ensures this runs for every test function
def manage_database_session(app: Flask):
    """
    Ensure each test has a clean database state (empty tables).
    Relies on the app fixture to have configured the DATABASE_URL for an
    in-memory DB and initialized the schema once.
    This fixture ensures data isolation between tests by clearing data.
    """
    with app.app_context():
        # Retrieve the test-specific engine from the app fixture
        engine = app.test_engine

        # Clear all data from tables before each test
        for table in reversed(Base.metadata.sorted_tables):
            Session = get_session_local(engine_instance=engine)
            db = Session()
            try:
                db.execute(table.delete())
                db.commit()
            except Exception as e:
                db.rollback()
                app.logger.error(f"Error clearing table {table.name}: {e}")
                raise
            finally:
                db.close()
    yield
    # No explicit teardown for table data needed here, as in-memory DB is ephemeral
    # or next test will clear tables again.


@pytest.fixture
def sample_project(client):
    """Creates a sample project and returns its ID."""
    response = client.post("/projects", json={"name": "Test Project for Recordings API"})
    assert response.status_code == 201
    return response.get_json()["id"]


# --- Existing Recording Route Tests ---


@patch("src.core.project.Project.add_recording")
def test_add_project_recording_success(mock_add_recording, client, sample_project):
    project_id = sample_project
    mock_recording_instance = RecordingModel(
        id=1,
        project_id=project_id,
        name="Test Uploaded Recording",
        file_path=f"{
            client.application.config['UPLOAD_FOLDER']}/project_{project_id}/test_audio.wav",
        status="pending",
        duration_seconds=1.0,
        samplerate=44100,
        channels=1,
    )
    mock_add_recording.return_value = mock_recording_instance
    data = {
        "name": "Test Uploaded Recording",
        "file": (BytesIO(b"dummy"), "test_audio.wav"),
    }

    project_upload_dir = os.path.join(
        client.application.config["UPLOAD_FOLDER"], f"project_{project_id}"
    )
    os.makedirs(project_upload_dir, exist_ok=True)

    response = client.post(
        f"/projects/{project_id}/recordings",
        data=data,
        content_type="multipart/form-data",
    )
    assert response.status_code == 201
    json_data = response.get_json()
    assert json_data["name"] == "Test Uploaded Recording"
    mock_add_recording.assert_called_once()


# ... (other existing tests for add_project_recording variations) ...


@patch("src.core.project.Project.list_recordings")
def test_list_project_recordings_success(mock_list_recordings, client, sample_project):
    project_id = sample_project
    mock_list_recordings.return_value = [
        RecordingModel(
            id=1,
            name="Rec A",
            project_id=project_id,
            file_path="a.wav",
            status="pending",
            duration_seconds=1,
            samplerate=44100,
            channels=1,
        ),
        RecordingModel(
            id=2,
            name="Rec B",
            project_id=project_id,
            file_path="b.wav",
            status="processed",
            duration_seconds=2,
            samplerate=48000,
            channels=2,
        ),
    ]
    response = client.get(f"/projects/{project_id}/recordings")
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 2
    mock_list_recordings.assert_called_once()


# ... (other existing tests for list_project_recordings variations) ...


def test_get_recording_details_success(app, client, sample_project): # Added app fixture
    project_id = sample_project
    with client.application.app_context():
        db_session = get_session_local(engine_instance=app.test_engine)() # Use app.test_engine
        rec = RecordingModel(
            project_id=project_id,
            name="Detail Test Rec",
            file_path="detail.wav",
            status="pending",
            duration_seconds=3,
            samplerate=44100,
            channels=1,
        )
        db_session.add(rec)
        db_session.commit()
        recording_id = rec.id
        db_session.close()
    response = client.get(f"/recordings/{recording_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["name"] == "Detail Test Rec"


# ... (other existing tests for get_recording_details variations) ...


# --- Updated Tests for POST /recordings/<recording_id>/process ---

DUMMY_AUDIO_PATH_FOR_API_TESTS = "tests/fixtures/dummy_audio.wav"


# Ensure this runs once per session
@pytest.fixture(scope="session", autouse=True)
def ensure_global_dummy_audio_exists_for_api():
    # This fixture ensures the dummy audio file is available for all tests in this module.
    # It's session-scoped to run once.
    os.makedirs(os.path.dirname(DUMMY_AUDIO_PATH_FOR_API_TESTS), exist_ok=True)
    if not os.path.exists(DUMMY_AUDIO_PATH_FOR_API_TESTS):
        # Create a minimal valid WAV file
        with wave.open(DUMMY_AUDIO_PATH_FOR_API_TESTS, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(44100)
            wf.writeframes(b"\x00\x00" * 10)  # Very short silence
        print(
            f"Created global dummy audio file for API tests: {DUMMY_AUDIO_PATH_FOR_API_TESTS}"
        )


@pytest.fixture
def test_recording_for_processing(app, client, sample_project):
    project_id = sample_project
    abs_dummy_audio_path = os.path.abspath(DUMMY_AUDIO_PATH_FOR_API_TESTS)
    assert os.path.exists(
        abs_dummy_audio_path
    ), f"Dummy audio file missing at {abs_dummy_audio_path}"

    with app.app_context():
        db_session = get_session_local(engine_instance=app.test_engine)() # Use app.test_engine
        try:
            rec = RecordingModel(
                project_id=project_id,
                name="API Processable Rec",
                file_path=abs_dummy_audio_path,
                status="pending",
                duration_seconds=1.0,
                samplerate=44100,
                channels=1,
            )
            db_session.add(rec)
            db_session.commit()
            recording_id = rec.id
        finally:
            db_session.close()
    return recording_id


@patch("src.core.workflows.BaseWorkflow.run")
def test_process_recording_with_workflow_success(
    mock_workflow_run, client, test_recording_for_processing
):
    recording_id = test_recording_for_processing
    mock_workflow_run.return_value = {
        "status": "workflow_completed",
        "details": "Mocked workflow output",
    }

    from src.core.workflows import (
        WORKFLOW_REGISTRY,
        BaseWorkflow,
        register_workflow,
        _camel_to_snake,
    )

    class APITestWorkflow(BaseWorkflow):  # Define a workflow class for testing
        @property
        def name(self) -> str:
            return "api_test_workflow"

        @property
        def description(self) -> str:
            return "API Test Workflow"

        @property
        def stages_definition(self) -> list:
            return []

    workflow_key = _camel_to_snake(APITestWorkflow.__name__)  # "api_test_workflow"

    # Manage registry carefully for this test
    original_registry = WORKFLOW_REGISTRY.copy()
    WORKFLOW_REGISTRY.clear()
    register_workflow(APITestWorkflow)  # Register our test workflow

    response = client.post(
        f"/recordings/{recording_id}/process",
        json={"workflow_name": workflow_key, "output_dir_suffix": "api_workflow_test"},
    )

    assert response.status_code == 200
    data = response.get_json()
    assert (
        f"Processing via workflow '{workflow_key}' completed" in data["message"]
    )  # Key is used in message
    assert data["output_location"].endswith("api_workflow_test")
    assert data["result"]["status"] == "workflow_completed"

    mock_workflow_run.assert_called_once()
    call_args_kwargs = mock_workflow_run.call_args[1]  # kwargs from the call
    assert call_args_kwargs["initial_data"].endswith(DUMMY_AUDIO_PATH_FOR_API_TESTS)
    assert "db_session" in call_args_kwargs["context"]
    assert call_args_kwargs["context"]["recording_id"] == recording_id

    WORKFLOW_REGISTRY.clear()
    WORKFLOW_REGISTRY.update(original_registry)


@patch("src.core.stage_runner.execute_stage_chain")
def test_process_recording_with_stages_chain_success(
    mock_execute_chain, client, test_recording_for_processing
):
    recording_id = test_recording_for_processing
    mock_execute_chain.return_value = [{"sample_id": 1, "path": "/mocked/sample.wav"}]

    # Ensure dummy stage used in chain is registered for this test
    from src.core.stage_runner import STAGE_REGISTRY, register_stage
    from src.core.processing_stages import (
        AudioProcessingStage,
        DATA_TYPE_FILE_PATH,
        DATA_TYPE_LIST_OF_SAMPLE_DATA,
    )

    class APITestChainStage(AudioProcessingStage):
        @property
        def name(self) -> str:
            return "api_chain_dummy_stage"

        @property
        def description(self) -> str:
            return "Dummy stage for API chain tests"

        @property
        def input_type(self) -> str:
            return DATA_TYPE_FILE_PATH

        @property
        def output_type(self) -> str:
            return DATA_TYPE_LIST_OF_SAMPLE_DATA

        @property
        def default_params(self) -> dict:
            return {}

        def process(self, data, params, context=None):
            return [{"sample_id": 1, "path": f"{context['output_sample_dir']}/s.wav"}]

    original_stage_registry = STAGE_REGISTRY.copy()
    STAGE_REGISTRY.clear()
    register_stage(APITestChainStage)

    stages_chain_payload = [{"stage_name": "api_chain_dummy_stage", "params": {}}]

    response = client.post(
        f"/recordings/{recording_id}/process",
        json={
            "stages_chain": stages_chain_payload,
            "output_dir_suffix": "api_chain_test",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert "Processing via ad-hoc stage chain completed" in data["message"]
    assert data["output_location"].endswith("api_chain_test")
    assert len(data["result"]) == 1

    mock_execute_chain.assert_called_once()
    call_args_kwargs = mock_execute_chain.call_args[1]
    assert call_args_kwargs["initial_data"].endswith(DUMMY_AUDIO_PATH_FOR_API_TESTS)
    assert call_args_kwargs["chain_definition"] == stages_chain_payload

    STAGE_REGISTRY.clear()
    STAGE_REGISTRY.update(original_stage_registry)


def test_process_recording_no_workflow_or_chain_api(client, test_recording_for_processing):
    recording_id = test_recording_for_processing
    response = client.post(
        f"/recordings/{recording_id}/process",
        json={"output_dir_suffix": "test_failure"},
    )
    assert response.status_code == 400
    assert (
        "Either 'workflow_name' or 'stages_chain' must be provided"
        in response.get_json()["error"]
    )


def test_process_recording_unknown_workflow_name_api(client, test_recording_for_processing):
    recording_id = test_recording_for_processing
    response = client.post(
        f"/recordings/{recording_id}/process",
        json={"workflow_name": "non_existent_workflow_api"},
    )
    assert response.status_code == 400
    assert "Workflow 'non_existent_workflow_api' not found" in response.get_json()["error"]


@patch(
    "src.api.routes.os.makedirs",
    side_effect=OSError("Simulated permission denied in API test"),
)
def test_process_recording_output_dir_creation_fails_api(
    mock_makedirs, client, test_recording_for_processing
):
    recording_id = test_recording_for_processing
    # Need a workflow to be registered for this test to pass the initial
    # checks in the endpoint
    from src.core.workflows import (
        WORKFLOW_REGISTRY,
        ExampleSlicingWorkflow,
        register_workflow,
        _camel_to_snake,
    )

    workflow_key = _camel_to_snake(ExampleSlicingWorkflow.__name__)
    if (
        workflow_key not in WORKFLOW_REGISTRY
    ):  # Ensure it's registered if test isolation clears it
        register_workflow(ExampleSlicingWorkflow)

    response = client.post(
        f"/recordings/{recording_id}/process", json={"workflow_name": workflow_key}
    )
    assert response.status_code == 500
    assert (
        "Could not create output directory: Simulated permission denied in API test"
        in response.get_json()["error"]
    )


def test_process_recording_invalid_recording_file_path(app, client, sample_project):
    with app.app_context():
        db = get_session_local(engine_instance=app.test_engine)() # Use app.test_engine
        rec = RecordingModel(
            project_id=sample_project,
            name="Rec Invalid Path",
            file_path="/invalid/path/does/not/exist.wav",
            status="pending",
            duration_seconds=1,
            samplerate=44100,
            channels=1,
        )
        db.add(rec)
        db.commit()
        rec_id = rec.id
        db.close()

    response = client.post(
        f"/recordings/{rec_id}/process",
        json={"workflow_name": "example_slicing_workflow"},
    )  # Assuming example_slicing_workflow is registered
    assert response.status_code == 400
    assert "Recording file path not found or invalid" in response.get_json()["error"]
