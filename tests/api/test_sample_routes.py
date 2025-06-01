import pytest
import json
from flask import Flask
from unittest.mock import patch, MagicMock
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
def app():
    test_db_url = "sqlite:///:memory:"
    flask_app = create_app()
    flask_app.config.update(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite:///:memory:",  # Use in-memory SQLite for tests
            # Add other necessary test configs like SAMPLES_BASE_DIR if routes need it
            # "SAMPLES_BASE_DIR": "/tmp/pytest_samples_base_samples_api",
        }
    )

    # Create an engine instance specifically for tests, using the test DB URL
    engine = get_engine(flask_app.config["DATABASE_URL"])
    flask_app.test_engine = engine  # Attach to app for access in other fixtures
    # Provide this engine instance to the app config so get_engine() in utils can pick it up
    flask_app.config["TEST_ENGINE_INSTANCE"] = engine

    with flask_app.app_context():
        # Initialize the database schema using the test-specific engine
        initialize_db_utils(engine_instance=engine)
        # Note: The tables are created once per module.
        # manage_database_session will handle per-test data cleaning.

    # Example: if SAMPLES_BASE_DIR is used by sample routes, ensure it exists
    # if "SAMPLES_BASE_DIR" in flask_app.config:
    #     os.makedirs(flask_app.config["SAMPLES_BASE_DIR"], exist_ok=True)

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
            Session = get_session_local(engine_instance=engine)  # Use test engine
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
    # No explicit teardown for table data needed here for in-memory DB.


@pytest.fixture
def sample_data(app, client):  # Added app fixture
    """
    Creates a sample project, recording, and samples, returning their IDs.
    Uses the app context to ensure DB operations use the test database.
    """
    with client.application.app_context():
        # get_session_local() will use the engine configured for the app context (in-memory)
        db_session = get_session_local(
            engine_instance=app.test_engine
        )()  # Use app.test_engine
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
def test_list_recording_samples_success(client, sample_data):
    recording_id = sample_data["recording_id"]

    response = client.get(f"/recordings/{recording_id}/samples")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    sample_names = sorted([s["name"] for s in data])
    assert sample_names == ["Test Sample 1", "Test Sample 2"]


def test_list_recording_samples_recording_not_found(client):
    # Assuming 7777 does not exist
    response = client.get("/recordings/7777/samples")
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert "Recording not found" in data["error"]


def test_list_recording_samples_no_samples(app, client, sample_data):  # Added app fixture
    # Create a new recording without samples
    project_id = sample_data["project_id"]
    with client.application.app_context():
        db_session = get_session_local(
            engine_instance=app.test_engine
        )()  # Use app.test_engine
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
            new_recording_id = new_recording.id
        finally:
            db_session.close()

    response = client.get(f"/recordings/{new_recording_id}/samples")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 0


# GET /samples/<sample_id>
def test_get_sample_details_success(client, sample_data):
    sample1_id = sample_data["sample1_id"]

    response = client.get(f"/samples/{sample1_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == sample1_id
    assert data["name"] == "Test Sample 1"
    assert data["midi_pitch"] == 60


def test_get_sample_details_not_found(client):
    response = client.get("/samples/6666")  # Assuming 6666 does not exist
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert "Sample not found" in data["error"]


# --- Test Root Path (already in test_project_routes.py, but good for completeness if run standalone) ---
def test_root_path_sample_routes(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.get_json()
    assert "message" in data
    assert "Welcome to the Audio Processing API!" in data["message"]
