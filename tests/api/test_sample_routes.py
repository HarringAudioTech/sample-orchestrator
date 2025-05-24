"""
API tests for sample-related routes.

This module contains tests for listing samples associated with a recording
and retrieving details for individual samples via the Flask API endpoints.
"""

# import json # Not directly used, Flask handles JSON in responses.
from unittest.mock import patch # For mocking database utils if needed by fixtures

from flask import Flask
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app import create_app
# init_db not needed directly here due to fixture setup
from src.database.models import Base, Project as ProjectModel, Recording as RecordingModel, Sample as SampleModel
# Removed get_engine, get_session_local as utils.py was refactored


# --- Test Fixtures ---

@pytest.fixture(scope="module")
def app() -> Flask:
    """
    Create and configure a new Flask app instance for the test module.
    This app will be configured to use an in-memory SQLite database for tests.
    """
    flask_app = create_app()
    flask_app.config.update({
        "TESTING": True,
        # DATABASE_URL will be patched by manage_database_session fixture
    })
    return flask_app

@pytest.fixture
def client(app: Flask): # app is the app fixture
    """
    Provides a test client for the Flask application.
    """
    return app.test_client()

@pytest.fixture(autouse=True)
def manage_database_session(app: Flask): # app is the app fixture
    """
    Manages the database for each test function.
    It patches the database utilities (ENGINE and SESSION_LOCAL) to use an
    in-memory SQLite database, creates all tables before each test, and drops
    them after. This ensures test isolation.
    """
    test_db_url = "sqlite:///:memory:"
    test_engine = create_engine(test_db_url)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    # Patch the module-level ENGINE and SESSION_LOCAL in src.database.utils
    with patch("src.database.utils.ENGINE", test_engine), \
         patch("src.database.utils.SESSION_LOCAL", TestSessionLocal):
        with app.app_context(): # Operations like create_all need app context
            Base.metadata.create_all(bind=test_engine)
        
        yield # Test function runs here
        
        with app.app_context():
            Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def sample_data(app: Flask): # app fixture needed for app_context
    """
    Creates a sample project, recording, and associated samples directly in the
    test database. Returns a dictionary of their IDs for use in tests.
    This fixture uses the patched database session provided by `manage_database_session`.
    """
    with app.app_context():
        # Use the patched SESSION_LOCAL from src.database.utils
        from src.database.utils import SESSION_LOCAL
        db_session = SESSION_LOCAL()
        try:
            project = ProjectModel(name="Sample Project for Samples API Test")
            db_session.add(project)
            db_session.commit()

            recording = RecordingModel(
                project_id=project.id,
                name="Sample Recording for Samples API Test",
                file_path="sample_rec_for_api.wav",
                status="processed", # Assumed processed to have samples
                duration_seconds=10.0,
                samplerate=44100,
                channels=1,
            )
            db_session.add(recording)
            db_session.commit()

            sample1 = SampleModel(
                recording_id=recording.id,
                name="API Test Sample 1",
                file_path="/path/to/api_sample1.wav", # Using dummy paths as file existence is not tested here
                start_time_seconds=1.0,
                end_time_seconds=2.0,
                midi_pitch=60,
            )
            sample2 = SampleModel(
                recording_id=recording.id,
                name="API Test Sample 2",
                file_path="/path/to/api_sample2.wav",
                start_time_seconds=3.0,
                end_time_seconds=4.0,
                midi_pitch=62,
            )
            db_session.add_all([sample1, sample2])
            db_session.commit()
            
            # Refreshing instances to get all fields populated by DB defaults if any (e.g. created_at)
            # is good practice but not strictly necessary if only IDs are used from return.
            # db_session.refresh(project)
            # db_session.refresh(recording)
            # db_session.refresh(sample1)
            # db_session.refresh(sample2)
            
            return {
                "project_id": project.id,
                "recording_id": recording.id,
                "sample1_id": sample1.id,
                "sample2_id": sample2.id
            }
        finally:
            db_session.close()

# --- Sample Route Tests ---

def test_list_recording_samples_success(client, sample_data: dict):
    """
    Test successfully listing all samples for a given recording ID.
    """
    recording_id = sample_data["recording_id"]
    
    response = client.get(f'/recordings/{recording_id}/samples')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    sample_names = sorted([s["name"] for s in data])
    assert sample_names == ["API Test Sample 1", "API Test Sample 2"]

def test_list_recording_samples_recording_not_found(client):
    """
    Test listing samples for a non-existent recording ID; expects a 404 error.
    """
    response = client.get('/recordings/7777/samples') # Use an ID unlikely to exist
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert "Recording not found" in data["error"]

def test_list_recording_samples_no_samples(client, app: Flask, sample_data: dict):
    """
    Test listing samples for a recording that exists but has no associated samples;
    expects an empty list.
    """
    project_id = sample_data["project_id"]
    new_recording_id_for_empty_test = None # More descriptive name
    with app.app_context():
        from src.database.utils import SESSION_LOCAL # Use patched version
        db_session = SESSION_LOCAL()
        try:
            new_empty_recording = RecordingModel(
                project_id=project_id,
                name="Empty Samples Rec Test",
                file_path="empty_rec_for_api.wav", # Unique path
                status="processed",
                duration_seconds=1.0,
                samplerate=44100,
                channels=1,
            )
            db_session.add(new_empty_recording)
            db_session.commit()
            new_recording_id_for_empty_test = new_empty_recording.id
        finally:
            db_session.close()
    
    assert new_recording_id_for_empty_test is not None, \
        "Failed to create recording for no_samples test." # Line wrapped

    response = client.get(f'/recordings/{new_recording_id_for_empty_test}/samples')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert not data # Check if list is empty


def test_get_sample_details_success(client, sample_data: dict):
    """
    Test successfully retrieving details for a specific sample by its ID.
    """
    sample1_id = sample_data["sample1_id"]
    
    response = client.get(f'/samples/{sample1_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == sample1_id
    assert data["name"] == "API Test Sample 1" # Matches name in sample_data fixture
    assert data["midi_pitch"] == 60

def test_get_sample_details_not_found(client):
    """
    Test retrieving a non-existent sample; expects a 404 error.
    """
    response = client.get('/samples/6666') # Use an ID unlikely to exist
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert "Sample not found" in data["error"]

def test_root_path_sample_routes(client): # Renamed to avoid conflict if tests are collected together
    """
    Test the API's root path ("/") for the expected welcome message.
    (Similar test exists in test_project_routes.py, good for module independence).
    """
    response = client.get('/')
    assert response.status_code == 200
    data = response.get_json()
    assert "message" in data
    expected_message = "Welcome to the Audio Processing and Sample Management API!"
    assert expected_message in data["message"]
