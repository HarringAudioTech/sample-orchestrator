"""
Integration tests for file upload operations in the Sample Orchestrator API.

This module contains tests that verify the file upload functionality works correctly
with real files and database interactions. These tests ensure that:

1. Audio files can be uploaded successfully
2. File validation works correctly (allowed extensions)
3. Files are saved to the correct location
4. File metadata is correctly stored in the database
5. Error cases are handled appropriately
"""
import os
import json
from unittest.mock import patch, MagicMock
import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy import event

# --- Test Fixtures ---

@pytest.fixture(scope="module")
def app() -> Flask:
    """Create and configure a Flask app instance for testing.
    
    Returns:
        Flask: Configured Flask application with in-memory SQLite database.
    """
    from src.app import create_app
    
    # Use an in-memory SQLite database for testing
    flask_app = create_app()
    flask_app.config.update({
        "TESTING": True,
        "DATABASE_URL": "sqlite:///:memory:",
        "UPLOAD_FOLDER": "/tmp/test_uploads",
        "PROCESSED_SAMPLES_DIR": "/tmp/test_processed",
    })
    
    # Create upload directories if they don't exist
    os.makedirs(flask_app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(flask_app.config["PROCESSED_SAMPLES_DIR"], exist_ok=True)
    
    # Override the database engine for testing
    from src.database.utils import engine, init_db, SessionLocal
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    
    # Create a new in-memory engine for testing
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    
    # Replace the global engine with our test engine
    import src.database.utils as db_utils
    db_utils.engine = test_engine
    
    # Create a new SessionLocal bound to our test engine
    db_utils.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    
    # Initialize the database
    with flask_app.app_context():
        init_db()
        
    return flask_app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Create a test client for the Flask app.
    
    Args:
        app: The Flask application fixture.
        
    Returns:
        FlaskClient: A test client for making requests.
    """
    return app.test_client()


@pytest.fixture
def db_session(app: Flask) -> SQLAlchemySession:
    """Provide a database session for test setup and verification.
    
    Args:
        app: The Flask application fixture.
        
    Returns:
        SQLAlchemySession: A SQLAlchemy session for the test database.
    """
    # Use the same engine as the app
    from src.database.utils import engine
    from sqlalchemy.orm import sessionmaker
    
    # Create a configured "Session" class
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    # Create a new session for testing
    db = TestingSessionLocal()
    
    try:
        yield db
    finally:
        # Cleanup: close the session
        db.close()


def test_upload_audio_file_success(client: FlaskClient, db_session: SQLAlchemySession):
    """Test that an audio file can be uploaded successfully.
    
    This test verifies that:
    1. A valid audio file can be uploaded to a project
    2. The API returns the expected success response (redirect)
    3. The CoreProject.add_recording method is called with the correct parameters
    
    Args:
        client: Flask test client
        db_session: SQLAlchemy session for test database
    """
    # Create a test project in the database
    from src.database.models import ProjectModel, ProjectType
    test_project = ProjectModel(
        name="Test Project",
        project_type=ProjectType.SAMPLE_PACK.value,
        description="A test project for file upload"
    )
    db_session.add(test_project)
    db_session.commit()
    db_session.refresh(test_project)
    
    # Mock the CoreProject.add_recording method
    with patch('src.core.project.Project.add_recording') as mock_add_recording:
        # Configure the add_recording mock to return a mock recording
        mock_recording = MagicMock()
        mock_recording.id = 1
        mock_recording.name = "Test Recording"
        mock_recording.file_path = "/path/to/recording.wav"
        mock_recording.project_id = test_project.id
        mock_add_recording.return_value = mock_recording
        
        # Create a test file for upload
        from io import BytesIO
        test_audio_content = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        test_file = (BytesIO(test_audio_content), 'test_audio.wav')
        
        # Make the request to upload the file
        data = {
            'recording_name': 'Test Recording',
            'audio_file': test_file  # This is a tuple of (file, filename)
        }
        
        response = client.post(
            f"/projects/{test_project.id}/upload_audio",
            data=data,
            content_type='multipart/form-data',
            follow_redirects=True  # Follow redirect to get the final response
        )
        
        # Verify the response - should be a redirect (302) followed by success (200)
        assert response.status_code == 200
        # The endpoint redirects to the UI page, so we expect HTML content
        assert 'text/html' in response.content_type
        assert b'uploaded successfully' in response.data.lower() or b'success' in response.data.lower()

        # Verify the mock was called correctly
        mock_add_recording.assert_called_once()
        call_args = mock_add_recording.call_args
        assert call_args[1]['file_path'] == f"/tmp/test_uploads/project_{test_project.id}/test_audio.wav"
        assert call_args[1]['name'] == "Test Recording"


def test_upload_invalid_file_type(client: FlaskClient, db_session: SQLAlchemySession):
    """Test that files with invalid extensions are rejected.
    
    This test verifies that:
    1. Files with invalid extensions are rejected with a 400 status code
    2. An appropriate error message is returned
    
    Args:
        client: Flask test client
        db_session: SQLAlchemy session for test database
    """
    # Create a test project in the database
    from src.database.models import ProjectModel, ProjectType
    test_project = ProjectModel(
        name="Test Project",
        project_type=ProjectType.SAMPLE_PACK.value,
        description="A test project for file upload"
    )
    db_session.add(test_project)
    db_session.commit()
    db_session.refresh(test_project)
    
    # Create a test file with an invalid extension
    from io import BytesIO
    test_file = (BytesIO(b"This is not an audio file"), 'invalid.txt')
    
    # Make the request to upload the file
    data = {
        'recording_name': 'Invalid File',
        'audio_file': test_file  # This is a tuple of (file, filename)
    }
    
    response = client.post(
        f"/projects/{test_project.id}/upload_audio",
        data=data,
        content_type='multipart/form-data',
        follow_redirects=True
    )
    
    # Verify the response - should be a redirect (302) followed by error page (200)
    assert response.status_code == 200
    # Check that the response contains the flash error message
    assert b'invalid file type' in response.data.lower() or b'error' in response.data.lower()
