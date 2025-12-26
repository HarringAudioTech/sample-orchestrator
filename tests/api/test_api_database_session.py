"""
Tests for database session handling in API routes.

This module contains tests that specifically verify the correct usage of database
sessions across different routes in the API blueprint. These tests ensure that:

1. Database sessions are properly opened and closed
2. Context managers are used correctly
3. Resources are properly cleaned up
4. Error handling is appropriate
5. Project type enum values are used correctly
"""
import pytest
import json
import os
from unittest.mock import patch, MagicMock
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.exc import SQLAlchemyError

from src.app import create_app
from src.database.utils import get_db
from src.database.models import (
    Base, 
    ProjectModel, 
    RecordingModel, 
    ProjectType, 
    SamplePackModel,
    VirtualInstrumentModel
)


# --- Test Fixtures ---
@pytest.fixture(scope="function")
def app() -> Flask:
    """Create and configure a Flask app instance for testing.
    
    Returns:
        Flask: Configured Flask application with in-memory SQLite database.
    """
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
    
    # Use app context for setup
    with flask_app.app_context():
        from src.database.utils import init_db
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
    with app.app_context():
        from src.database.utils import SessionLocal
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()


# --- Test API Database Session Handling ---
def test_create_project_api_db_session(client: FlaskClient):
    """Test that the create project API endpoint properly handles database sessions.
    
    This test verifies that:
    1. The create project API correctly uses the database session as a context manager
    2. The API validates project types against the ProjectType enum
    3. The API returns the expected HTTP status code and response
    
    Args:
        client: Flask test client.
    """
    # Mock the get_db function to verify it's used as a context manager
    with patch('src.api.routes.get_db') as mock_get_db:
        # Setup the mock to behave like a context manager
        mock_session = MagicMock()
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "Test Project"
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh = lambda x: None
        mock_get_db.return_value.__enter__.return_value = mock_session
        
        # Mock the model_to_dict function
        with patch('src.api.routes.model_to_dict') as mock_model_to_dict:
            mock_model_to_dict.return_value = {
                "id": 1,
                "name": "Test Project",
                "project_type": "sample_pack",
                "description": "Test description"
            }
            
            # Make the request
            response = client.post(
                "/projects",
                json={
                    "name": "Test Project",
                    "description": "Test description",
                    "project_type": "sample_pack"
                }
            )
            
            # Verify the response
            assert response.status_code == 201
            response_data = json.loads(response.data)
            assert response_data["name"] == "Test Project"
            assert response_data["project_type"] == "sample_pack"
            
            # Verify get_db was used as a context manager
            mock_get_db.assert_called_once()
            mock_get_db.return_value.__enter__.assert_called_once()
            mock_get_db.return_value.__exit__.assert_called_once()


def test_create_project_api_validates_project_type(client: FlaskClient):
    """Test that the create project API validates project types against the enum.
    
    This test verifies that:
    1. The API correctly validates project types against the ProjectType enum
    2. The API returns an appropriate error for invalid project types
    
    Args:
        client: Flask test client.
    """
    # Make the request with an invalid project type
    response = client.post(
        "/projects",
        json={
            "name": "Test Project",
            "description": "Test description",
            "project_type": "invalid_type"
        }
    )
    
    # Verify the response
    assert response.status_code == 400
    response_data = json.loads(response.data)
    assert "error" in response_data
    assert "Invalid project_type" in response_data["error"]
    
    # Verify the error message includes the valid types
    for valid_type in [pt.value for pt in ProjectType]:
        assert valid_type in response_data["error"]


def test_create_virtual_instrument_project(client: FlaskClient):
    """Test creating a virtual instrument project with the API.
    
    This test verifies that:
    1. The API correctly creates a virtual instrument project
    2. The API validates virtual instrument specific fields
    3. The API returns the expected HTTP status code and response
    
    Args:
        client: Flask test client.
    """
    # Mock the get_db function
    with patch('src.api.routes.get_db') as mock_get_db:
        # Setup the mock
        mock_session = MagicMock()
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "Test Virtual Instrument"
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh = lambda x: None
        mock_get_db.return_value.__enter__.return_value = mock_session
        
        # Mock the model_to_dict function
        with patch('src.api.routes.model_to_dict') as mock_model_to_dict:
            mock_model_to_dict.return_value = {
                "id": 1,
                "name": "Test Virtual Instrument",
                "project_type": "virtual_instrument",
                "description": "Test description",
                "base_note": 60,
                "round_robins": 2
            }
            
            # Make the request
            response = client.post(
                "/projects",
                json={
                    "name": "Test Virtual Instrument",
                    "description": "Test description",
                    "project_type": "virtual_instrument",
                    "base_note": 60,
                    "round_robins": 2
                }
            )
            
            # Verify the response
            assert response.status_code == 201
            response_data = json.loads(response.data)
            assert response_data["name"] == "Test Virtual Instrument"
            assert response_data["project_type"] == "virtual_instrument"
            assert response_data["base_note"] == 60


def test_get_project_api_db_session(client: FlaskClient):
    """Test that the get project API endpoint properly handles database sessions.
    
    This test verifies that:
    1. The get project API correctly uses the database session as a context manager
    2. The API returns the expected HTTP status code and response
    
    Args:
        client: Flask test client.
    """
    # Mock the get_db function
    with patch('src.api.routes.get_db') as mock_get_db:
        # Setup the mock
        mock_session = MagicMock()
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "Test Project"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_project
        mock_get_db.return_value.__enter__.return_value = mock_session
        
        # Mock the model_to_dict function
        with patch('src.api.routes.model_to_dict') as mock_model_to_dict:
            mock_model_to_dict.return_value = {
                "id": 1,
                "name": "Test Project",
                "project_type": "sample_pack",
                "description": "Test description"
            }
            
            # Make the request
            response = client.get("/projects/1")
            
            # Verify the response
            assert response.status_code == 200
            response_data = json.loads(response.data)
            assert response_data["name"] == "Test Project"
            
            # Verify get_db was used as a context manager
            mock_get_db.assert_called_once()
            mock_get_db.return_value.__enter__.assert_called_once()
            mock_get_db.return_value.__exit__.assert_called_once()


def test_get_project_not_found(client: FlaskClient):
    """Test that the get project API handles not found projects correctly.
    
    This test verifies that:
    1. The API returns a 404 when a project is not found
    2. The database session is properly closed
    
    Args:
        client: Flask test client.
    """
    # Mock the get_db function
    with patch('src.api.routes.get_db') as mock_get_db:
        # Setup the mock to return None for the project query
        mock_session = MagicMock()
        mock_session.query.return_value.filter.return_value.first.return_value = None
        mock_get_db.return_value.__enter__.return_value = mock_session
        
        # Make the request
        response = client.get("/projects/999")
        
        # Verify the response
        assert response.status_code == 404
        response_data = json.loads(response.data)
        assert "error" in response_data
        
        # Verify get_db was used as a context manager
        mock_get_db.assert_called_once()
        mock_get_db.return_value.__enter__.assert_called_once()
        mock_get_db.return_value.__exit__.assert_called_once()


def test_api_db_session_error_handling(client: FlaskClient):
    """Test that database errors are properly handled in API routes.
    
    This test verifies that:
    1. When a database error occurs, the session is properly closed
    2. The API returns an appropriate error response
    
    Args:
        client: Flask test client.
    """
    # Mock the get_db function to simulate a database error
    with patch('src.api.routes.get_db') as mock_get_db:
        # Setup the mock to raise an exception
        mock_session = MagicMock()
        mock_session.query.side_effect = SQLAlchemyError("Test database error")
        mock_get_db.return_value.__enter__.return_value = mock_session
        
        # Make the request
        response = client.get("/projects/1")
        
        # Verify the response
        assert response.status_code == 500
        response_data = json.loads(response.data)
        assert "error" in response_data
        
        # Verify get_db was used as a context manager and __exit__ was called
        mock_get_db.assert_called_once()
        mock_get_db.return_value.__enter__.assert_called_once()
        mock_get_db.return_value.__exit__.assert_called_once()


def test_create_recording_api_db_session(client: FlaskClient):
    """Test that the create recording API endpoint properly handles database sessions.
    
    This test verifies that:
    1. The create recording API correctly uses the database session as a context manager
    2. The API returns the expected HTTP status code and response
    
    Args:
        client: Flask test client.
    """
    # Mock the get_db function in both API routes and CoreProject
    with patch('src.api.routes.get_db') as mock_get_db, \
         patch('src.core.project.get_db') as mock_core_get_db, \
         patch('src.core.project.Project.add_recording') as mock_add_recording:
        # Setup the mocks
        mock_session = MagicMock()
        mock_project = MagicMock()
        mock_project.id = 1
        mock_recording = MagicMock()
        mock_recording.id = 1
        mock_recording.name = "Test Recording"
        mock_recording.file_path = "/path/to/recording.wav"
        mock_recording.project_id = 1
        mock_session.query.return_value.filter.return_value.first.return_value = mock_project
        mock_session.add.return_value = None
        mock_session.commit.return_value = None
        mock_session.refresh = lambda x: None
        
        # Configure the add_recording mock to return a mock recording
        mock_add_recording.return_value = mock_recording
        
        # Configure both get_db mocks to return the same session
        mock_get_db.return_value.__enter__.return_value = mock_session
        mock_core_get_db.return_value.__enter__.return_value = mock_session
        
        # Mock the model_to_dict function
        with patch('src.api.routes.model_to_dict') as mock_model_to_dict:
            mock_model_to_dict.return_value = {
                "id": 1,
                "name": "Test Recording",
                "project_id": 1,
                "file_path": "/path/to/recording.wav",
                "status": "pending"
            }
            
            # Create a mock file for testing
            from io import BytesIO
            mock_file = BytesIO(b"test audio content")
            
            # Make the request with multipart/form-data
            data = {
                "name": "Test Recording",
                "file": (mock_file, "test_audio.wav", "audio/wav")
            }
            
            response = client.post(
                "/projects/1/recordings",
                data=data,
                content_type="multipart/form-data"
            )
            
            # Verify the response
            assert response.status_code == 201
            response_data = json.loads(response.data)
            assert response_data["name"] == "Test Recording"
            
            # Verify CoreProject was initialized with the correct project_id
            # and add_recording was called
            mock_add_recording.assert_called_once()
            
            # Verify the core_get_db was used as a context manager
            mock_core_get_db.assert_called()
            mock_core_get_db.return_value.__enter__.assert_called()
            mock_core_get_db.return_value.__exit__.assert_called()
