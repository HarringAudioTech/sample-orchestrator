import pytest
import json
from flask import Flask
from unittest.mock import patch, MagicMock
from src.app import create_app
from src.database.utils import init_db as initialize_db_utils, get_engine, get_session_local
from src.database.models import Base, Project as ProjectModel, Recording as RecordingModel, Sample as SampleModel

# --- Test Fixtures (reuse from other API test files or define new ones) ---
@pytest.fixture(scope="module")
def app():
    test_db_url = "sqlite:///:memory:"
    flask_app = create_app()
    flask_app.config.update({
        "TESTING": True,
        "DATABASE_URL": test_db_url,
    })

    import src.database.utils as db_utils
    engine = get_engine(test_db_url)
    db_utils._engine = engine
    db_utils._SessionLocal = get_session_local(engine_instance=engine)

    with flask_app.app_context():
        initialize_db_utils(engine_instance=engine)
    
    yield flask_app
    
    db_utils._engine = None
    db_utils._SessionLocal = None


@pytest.fixture
def client(app: Flask):
    return app.test_client()

@pytest.fixture(autouse=True)
def manage_database_session(app: Flask):
    # This fixture ensures that each test function in this file runs with a clean database.
    engine = get_engine("sqlite:///:memory:") # Use the app's configured test DB URL
    
    import src.database.utils as db_utils
    original_engine = db_utils._engine
    original_session_local = db_utils._SessionLocal
    
    db_utils._engine = engine
    db_utils._SessionLocal = get_session_local(engine_instance=engine)

    with app.app_context():
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    yield
    with app.app_context():
        Base.metadata.drop_all(bind=engine)

    db_utils._engine = original_engine
    db_utils._SessionLocal = original_session_local


@pytest.fixture
def sample_data(client):
    """Creates a sample project, recording, and sample, returning their IDs."""
    with client.application.app_context():
        db_session = get_session_local(get_engine(client.application.config["DATABASE_URL"]))()
        try:
            project = ProjectModel(name="Sample Project for Samples")
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)

            recording = RecordingModel(
                project_id=project.id, 
                name="Sample Recording for Samples", 
                file_path="sample_rec.wav",
                status="processed", # Assume processed to have samples
                duration_seconds=10.0,
                samplerate=44100,
                channels=1
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
                midi_pitch=60
            )
            sample2 = SampleModel(
                recording_id=recording.id,
                name="Test Sample 2",
                file_path="/path/to/sample2.wav",
                start_time_seconds=3.0,
                end_time_seconds=4.0,
                midi_pitch=62
            )
            db_session.add_all([sample1, sample2])
            db_session.commit()
            db_session.refresh(sample1)
            db_session.refresh(sample2)
            
            return {"project_id": project.id, "recording_id": recording.id, "sample1_id": sample1.id, "sample2_id": sample2.id}
        finally:
            db_session.close()

# --- Sample Route Tests ---

# GET /recordings/<recording_id>/samples
def test_list_recording_samples_success(client, sample_data):
    recording_id = sample_data["recording_id"]
    
    response = client.get(f'/recordings/{recording_id}/samples')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    sample_names = sorted([s["name"] for s in data])
    assert sample_names == ["Test Sample 1", "Test Sample 2"]

def test_list_recording_samples_recording_not_found(client):
    response = client.get('/recordings/7777/samples') # Assuming 7777 does not exist
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert "Recording not found" in data["error"]

def test_list_recording_samples_no_samples(client, sample_data):
    # Create a new recording without samples
    project_id = sample_data["project_id"]
    with client.application.app_context():
        db_session = get_session_local(get_engine(client.application.config["DATABASE_URL"]))()
        try:
            new_recording = RecordingModel(project_id=project_id, name="Empty Samples Rec", file_path="empty.wav", status="processed", duration_seconds=1, samplerate=44100, channels=1)
            db_session.add(new_recording)
            db_session.commit()
            new_recording_id = new_recording.id
        finally:
            db_session.close()

    response = client.get(f'/recordings/{new_recording_id}/samples')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 0


# GET /samples/<sample_id>
def test_get_sample_details_success(client, sample_data):
    sample1_id = sample_data["sample1_id"]
    
    response = client.get(f'/samples/{sample1_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == sample1_id
    assert data["name"] == "Test Sample 1"
    assert data["midi_pitch"] == 60

def test_get_sample_details_not_found(client):
    response = client.get('/samples/6666') # Assuming 6666 does not exist
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert "Sample not found" in data["error"]

# --- Test Root Path (already in test_project_routes.py, but good for completeness if run standalone) ---
def test_root_path_sample_routes(client):
    response = client.get('/')
    assert response.status_code == 200
    data = response.get_json()
    assert "message" in data
    assert "Welcome to the Audio Processing API!" in data["message"]
