import pytest
import json
import pytest
import json
from flask import Flask
from flask.testing import FlaskClient  # For typing the client fixture
from unittest.mock import patch, MagicMock  # Keep if used, though not in current file
from sqlalchemy.orm import Session as SQLAlchemySession  # For typing sessions if needed
from sqlalchemy.engine import Engine  # For typing engine if needed

from src.app import create_app  # Assuming your Flask app factory is in src.app
from src.database.utils import (
    init_db as initialize_db_utils,
    get_engine,
    get_session_local,
)
from src.database.models import Base, Project as ProjectModel


from typing import Generator  # For typing fixtures that yield


# --- Test Fixtures ---
@pytest.fixture(scope="module")  # Use module scope for app to be faster
def app() -> Generator[Flask, None, None]:
    """Create and configure a new app instance for each test module.

    Yields:
        The Flask application instance.
    """
    # Use an in-memory SQLite database for testing API routes
    # test_db_url = "sqlite:///:memory:" # Not directly used, DATABASE_URL in config is key

    # Create a Flask app configured for testing
    flask_app: Flask = create_app()
    flask_app.config.update(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite:///:memory:",  # Use in-memory SQLite for tests
        }
    )

    # Create an engine instance specifically for tests, using the test DB URL
    engine: Engine = get_engine(flask_app.config["DATABASE_URL"])
    # Provide this engine instance to the app config so get_engine() in utils can pick it up
    flask_app.config["TEST_ENGINE_INSTANCE"] = engine

    with flask_app.app_context():
        # Initialize the database schema using the test-specific engine
        initialize_db_utils(engine_instance=engine)
        # Note: The tables are created once per module.
        # manage_database_session will handle per-test data cleaning.

    yield flask_app

    # No explicit teardown needed for _engine or _SessionLocal patching, as it's removed.
    # The in-memory database ceases to exist when the connection is closed by tests ending.


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """A test client for the app.

    Args:
        app: The Flask application fixture.

    Returns:
        A Flask test client.
    """
    return app.test_client()


# Automatically use this for each test in this file
@pytest.fixture(autouse=True)
def manage_database_session(app: Flask) -> Generator[None, None, None]:
    """Ensure each test has a clean database state (empty tables).

    Relies on the app fixture to have configured the DATABASE_URL for an
    in-memory DB and initialized the schema once.
    This fixture ensures data isolation between tests by clearing data from tables.

    Args:
        app: The Flask application fixture.

    Yields:
        None.
    """
    with app.app_context():
        import logging  # Keep import local if only used here

        logger = logging.getLogger(__name__)
        # Retrieve the test-specific engine from the app fixture
        engine: Engine = app.config["TEST_ENGINE_INSTANCE"]
        logger.info(f"manage_db_session: Engine URL from app.config: {str(engine.url)}")
        logger.info(
            f"manage_db_session: Sorted tables from Base.metadata: {[table.name for table in Base.metadata.sorted_tables]}"
        )

        # Clear all data from tables before each test
        # This is faster than dropping and recreating tables if the schema is stable
        for table in reversed(Base.metadata.sorted_tables):
            # Use a session to execute delete statements
            SessionLocal = get_session_local(engine_instance=engine)
            db: SQLAlchemySession = SessionLocal()
            try:
                db.execute(table.delete())
                db.commit()
            except Exception as e:
                db.rollback()
                app.logger.error(f"Error clearing table {table.name}: {e}")
                raise
            finally:
                db.close()

        # Alternative: Drop and recreate all tables (slower but robust if schema changes or complex relations)
        # Base.metadata.drop_all(bind=engine)
        # Base.metadata.create_all(bind=engine)

    yield  # Run the test

    # Teardown after test (optional, if yield above handles it per test)
    # For in-memory DB, data is gone anyway when connections close.
    # If using persistent DB for tests, this is where you'd clean up.
    # For this setup, clearing tables before each test is the primary strategy.


# --- Project Route Tests ---


def test_create_project_success(client: FlaskClient) -> None:
    """Test successful project creation."""
    response = client.post(
        "/projects",
        json={
            "name": "My First API Project",
            "description": "A project created via API test",
        },
    )
    assert response.status_code == 201
    data = response.get_json()
    assert "id" in data
    assert data["name"] == "My First API Project"
    assert data["description"] == "A project created via API test"

    # Verify in DB (optional, but good for confidence)
    # This requires getting a session in the test, similar to how routes do.
    # For simplicity, we trust the route's own DB interaction for now,
    # or we'd need to setup db_session fixture like in model tests.

    # Example DB verification (if you set up a db_session fixture for API tests too):
    # project_in_db = db_session.query(ProjectModel).filter(ProjectModel.id == data['id']).first()
    # assert project_in_db is not None
    # assert project_in_db.name == "My First API Project"


def test_create_project_missing_name(client: FlaskClient) -> None:
    """Test project creation failure when name is missing."""
    response = client.post("/projects", json={"description": "Project without a name"})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "Project name is required" in data["error"]


def test_get_project_success(client: FlaskClient) -> None:
    """Test successfully retrieving an existing project."""
    # First, create a project to fetch
    create_resp = client.post("/projects", json={"name": "Fetchable Project"})
    assert create_resp.status_code == 201
    project_id = create_resp.get_json()["id"]

    response = client.get(f"/projects/{project_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == project_id
    assert data["name"] == "Fetchable Project"


def test_get_project_not_found(client: FlaskClient) -> None:
    """Test retrieving a non-existent project results in 404."""
    response = client.get("/projects/9999")  # Assuming 9999 does not exist
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert "Project not found" in data["error"]


def test_list_projects_empty(client: FlaskClient) -> None:
    """Test listing projects when no projects exist."""
    response = client.get("/projects")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_projects_with_data(client: FlaskClient) -> None:
    """Test listing projects when multiple projects exist."""
    client.post("/projects", json={"name": "Project Alpha"})
    client.post("/projects", json={"name": "Project Beta"})

    response = client.get("/projects")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    project_names = sorted([p["name"] for p in data])
    assert project_names == ["Project Alpha", "Project Beta"]


def test_root_path(client: FlaskClient) -> None:
    """Test the root path of the API returns a welcome message."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.get_json()
    assert "message" in data
    assert "Welcome to the Audio" in data["message"]


# --- Upload Audio and Workflow Trigger Test ---

import io # For BytesIO
from unittest.mock import MagicMock, patch # Already imported patch, adding MagicMock
from src.core.processing_stages import DATA_TYPE_FILE_PATH # For checking call args
# ProjectModel is already imported

# Helper function to create a project directly in the DB for test setup
def _create_project_in_db(db_session: SQLAlchemySession, name: str = "Test Project") -> ProjectModel:
    project = ProjectModel(name=name, description="Test project created by helper")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project

@patch('src.api.routes.os.makedirs') # Mock os.makedirs to avoid actual directory creation
@patch('src.api.routes.WORKFLOW_REGISTRY.get')
def test_upload_audio_and_trigger_workflow(
    mock_workflow_registry_get: MagicMock, # Pytest injects mocks from bottom up
    mock_os_makedirs: MagicMock,
    client: FlaskClient,
    app: Flask # For accessing app.config and db engine
) -> None:
    """Test audio upload successfully triggers the ExampleSlicingWorkflow."""

    # Setup mock workflow
    mock_workflow_instance = MagicMock()
    mock_workflow_instance.name = "mocked_slicing_workflow"
    mock_workflow_instance.run.return_value = {"status": "mock_workflow_completed", "output_files": []}

    # Configure WORKFLOW_REGISTRY.get to return a class that instantiates to mock_workflow_instance
    MockWorkflowClass = MagicMock(return_value=mock_workflow_instance)
    mock_workflow_registry_get.return_value = MockWorkflowClass

    # Get a database session for this test
    engine: Engine = app.config["TEST_ENGINE_INSTANCE"]
    SessionLocal = get_session_local(engine_instance=engine)
    db: SQLAlchemySession = SessionLocal()

    project_id: Optional[int] = None
    try:
        # Create a project directly in the database
        project = _create_project_in_db(db, name="TestProjectForWorkflowUpload")
        project_id = project.id

        # Simulate file upload
        file_data = {'file': (io.BytesIO(b"fake audio content for test"), 'test_audio_sample.wav')}
        response = client.post(
            f'/projects/{project_id}/upload_audio',
            content_type='multipart/form-data',
            data=file_data
        )
        # print("Response data:", response.data) # For debugging if needed
        assert response.status_code == 201
        json_response = response.get_json()

        assert "task_id" in json_response
        assert "recording_id" in json_response
        recording_id = json_response["recording_id"]
        assert json_response["message"] == "File uploaded successfully and processing initiated."

        # Assert workflow registry was called to get the workflow class
        mock_workflow_registry_get.assert_called_once_with("example_slicing_workflow")

        # Assert the MockWorkflowClass (returned by the registry) was instantiated
        MockWorkflowClass.assert_called_once_with() # No args to constructor

        # Assert workflow's run method was called
        mock_workflow_instance.run.assert_called_once()

        # Inspect arguments to the workflow's run method
        args, kwargs = mock_workflow_instance.run.call_args
        # initial_data is the first positional arg if not passed by keyword,
        # but the run signature is (self, initial_data, initial_data_type, context)
        # and execute_stage_chain calls it with keywords.
        # The `workflow_instance.run` in `upload_audio_and_process` calls with keywords.

        assert "initial_data" in kwargs
        uploaded_file_path_arg = kwargs['initial_data']
        assert isinstance(uploaded_file_path_arg, str)
        assert uploaded_file_path_arg.endswith('test_audio_sample.wav')
        # Check it's within the expected upload folder structure
        assert f"project_{project_id}" in uploaded_file_path_arg
        assert app.config.get("UPLOAD_FOLDER", "data/uploads") in uploaded_file_path_arg


        assert kwargs['initial_data_type'] == DATA_TYPE_FILE_PATH

        assert "context" in kwargs
        context_arg = kwargs['context']
        assert context_arg['project_id'] == project_id
        assert context_arg['recording_id'] == recording_id
        assert 'db_session' in context_arg # Check db_session is passed
        assert context_arg['db_session'] is db # Check it's the same session instance (or configured similarly)
                                             # This check might be too strict if session proxying occurs.
                                             # More robust: check type or if it's a Session.

        expected_output_dir_fragment = os.path.join(
            f"project_{project_id}",
            f"recording_{recording_id}",
            "example_slicing_workflow_output"
        )
        assert context_arg['output_sample_dir'].startswith(app.config.get("SAMPLES_BASE_DIR", "data/projects"))
        assert context_arg['output_sample_dir'].endswith(expected_output_dir_fragment)

        # Assert os.makedirs was called for the output directory
        # The call is os.makedirs(output_sample_dir, exist_ok=True)
        mock_os_makedirs.assert_called_once_with(context_arg['output_sample_dir'], exist_ok=True)

    finally:
        db.close()
