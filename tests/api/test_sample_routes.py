import pytest
import json
from flask import Flask
from flask.testing import FlaskClient # For typing the client fixture
from unittest.mock import patch, MagicMock # Keep if used
from sqlalchemy.orm import Session as SQLAlchemySession # For typing sessions
from sqlalchemy.engine import Engine # For typing engine
from typing import Generator, Dict, Any # For typing fixtures and dicts

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
    Sample as SampleModel,
)


# --- Test Fixtures (reuse from other API test files or define new ones) ---
@pytest.fixture(scope="module")
def app() -> Generator[Flask, None, None]:
    """Create and configure a new app instance for each test module.

    Yields:
        The Flask application instance.
    """
    # test_db_url = "sqlite:///:memory:" # Not directly used
    flask_app: Flask = create_app()
    flask_app.config.update(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite:///:memory:",  # Use in-memory SQLite for tests
            # Add other necessary test configs like SAMPLES_BASE_DIR if routes need it
            # "SAMPLES_BASE_DIR": "/tmp/pytest_samples_base_samples_api",
        }
    )

    # Create an engine instance specifically for tests, using the test DB URL
    engine: Engine = get_engine(flask_app.config["DATABASE_URL"])
    # Provide this engine instance to the app config so get_engine() in utils can pick it up
    flask_app.config["TEST_ENGINE_INSTANCE"] = engine

    with flask_app.app_context():
        # Initialize the database schema using the test-specific engine
        initialize_db_utils(engine_instance=engine)

    # Example: if SAMPLES_BASE_DIR is used by sample routes, ensure it exists
    # if "SAMPLES_BASE_DIR" in flask_app.config:
    #     os.makedirs(flask_app.config["SAMPLES_BASE_DIR"], exist_ok=True)

    yield flask_app
    # No explicit teardown needed for _engine or _SessionLocal patching


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """A test client for the app.

    Args:
        app: The Flask application fixture.

    Returns:
        A Flask test client.
    """
    return app.test_client()


@pytest.fixture(autouse=True)
def manage_database_session(app: Flask) -> Generator[None, None, None]:
    """Ensure each test has a clean database state (empty tables).

    Args:
        app: The Flask application fixture.

    Yields:
        None.
    """
    with app.app_context():
        engine: Engine = app.config["TEST_ENGINE_INSTANCE"]
        for table in reversed(Base.metadata.sorted_tables):
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
    yield


@pytest.fixture
def sample_data(app: Flask, client: FlaskClient) -> Dict[str, Any]:
    """Creates a sample project, recording, and samples, returning their IDs.

    Uses the app context to ensure DB operations use the test database.

    Args:
        app: The Flask application fixture.
        client: The Flask test client fixture.

    Returns:
        A dictionary containing IDs of the created project, recording, and samples.
    """
    with client.application.app_context():
        SessionLocal = get_session_local(engine_instance=app.config["TEST_ENGINE_INSTANCE"])
        db_session: SQLAlchemySession = SessionLocal()
        try:
            project = ProjectModel(name="Sample Project for Samples")
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)

            recording = RecordingModel(
                project_id=project.id,
                name="Sample Recording for Samples",
                file_path="sample_rec.wav",
                status="processed",  # Assume processed to have samples
                duration_seconds=10.0,
                samplerate=44100,
                channels=1,
            )
            db_session.add(recording)
            db_session.commit()
            db_session.refresh(recording)

            sample1 = SampleModel(
                recording_id=recording.id,
                name="Test Sample 1",
                file_path="/path/to/sample1.wav",
                start_time_seconds=1.0,
                end_time_seconds=2.0,
                midi_pitch=60,
            )
            sample2 = SampleModel(
                recording_id=recording.id,
                name="Test Sample 2",
                file_path="/path/to/sample2.wav",
                start_time_seconds=3.0,
                end_time_seconds=4.0,
                midi_pitch=62,
            )
            db_session.add_all([sample1, sample2])
            db_session.commit()
            db_session.refresh(sample1)
            db_session.refresh(sample2)

            return {
                "project_id": project.id,
                "recording_id": recording.id,
                "sample1_id": sample1.id,
                "sample2_id": sample2.id,
            }
        finally:
            db_session.close()


# --- Sample Route Tests ---


# GET /recordings/<recording_id>/samples
def test_list_recording_samples_success(client: FlaskClient, sample_data: Dict[str, Any]) -> None:
    """Test successfully listing samples for a recording."""
    recording_id: int = sample_data["recording_id"]

    response = client.get(f"/recordings/{recording_id}/samples")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    sample_names = sorted([s["name"] for s in data])
    assert sample_names == ["Test Sample 1", "Test Sample 2"]


def test_list_recording_samples_recording_not_found(client: FlaskClient) -> None:
    """Test listing samples for a non-existent recording results in 404."""
    response = client.get("/recordings/7777/samples") # Assuming 7777 does not exist
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert "Recording not found" in data["error"]


def test_list_recording_samples_no_samples(app: Flask, client: FlaskClient, sample_data: Dict[str, Any]) -> None:
    """Test listing samples for a recording that has no samples."""
    project_id: int = sample_data["project_id"]
    new_recording_id: int
    with client.application.app_context():
        SessionLocal = get_session_local(engine_instance=app.config["TEST_ENGINE_INSTANCE"])
        db_session: SQLAlchemySession = SessionLocal()
        try:
            new_recording = RecordingModel(
                project_id=project_id,
                name="Empty Samples Rec",
                file_path="empty.wav",
                status="processed",
                duration_seconds=1,
                samplerate=44100,
                channels=1,
            )
            db_session.add(new_recording)
            db_session.commit()
            db_session.refresh(new_recording) # Refresh to get ID
            new_recording_id = new_recording.id
        finally:
            db_session.close()

    response = client.get(f"/recordings/{new_recording_id}/samples")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 0


# GET /samples/<sample_id>
def test_get_sample_details_success(client: FlaskClient, sample_data: Dict[str, Any]) -> None:
    """Test successfully retrieving details for a specific sample."""
    sample1_id: int = sample_data["sample1_id"]

    response = client.get(f"/samples/{sample1_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == sample1_id
    assert data["name"] == "Test Sample 1"
    assert data["midi_pitch"] == 60


def test_get_sample_details_not_found(client: FlaskClient) -> None:
    """Test retrieving a non-existent sample results in 404."""
    response = client.get("/samples/6666")  # Assuming 6666 does not exist
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert "Sample not found" in data["error"]


# --- Test Root Path (already in test_project_routes.py, but good for completeness if run standalone) ---
def test_root_path_sample_routes(client: FlaskClient) -> None:
    """Test the root path of the API returns a welcome message (sample routes context)."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.get_json()
    assert "message" in data
    assert "Welcome to the" in data["message"]
