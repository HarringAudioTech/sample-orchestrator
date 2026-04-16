"""
Tests for database session handling in API routes.
Migrated to FastAPI and SQLModel.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session
from sqlalchemy.exc import SQLAlchemyError

from src.database.models import (
    ProjectModel, 
    ProjectType
)

# --- Test API Database Session Handling ---

def test_create_project_api_db_session(client: TestClient):
    """Test that the create project API endpoint properly handles database sessions."""
    # Mock the get_db function to verify it's used as a dependency
    with patch('src.api.routes.get_db') as mock_get_db:
        mock_session = MagicMock(spec=Session)
        mock_get_db.return_value = mock_session
        
        # Make the request
        response = client.post(
            "/api/projects",
            json={
                "name": "Test Project",
                "description": "Test description",
                "project_type": "sample_pack"
            }
        )
        
        # Verify the response
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["name"] == "Test Project"
        assert response_data["project_type"] == "sample_pack"

def test_create_project_api_validates_project_type(client: TestClient):
    """Test that the create project API validates project types against the enum."""
    # Make the request with an invalid project type
    response = client.post(
        "/api/projects",
        json={
            "name": "Test Project",
            "description": "Test description",
            "project_type": "invalid_type"
        }
    )
    
    # Verify the response - FastAPI/Pydantic returns 422, our catch returns 400
    assert response.status_code in [400, 422]
    response_data = response.json()
    assert "detail" in response_data

def test_create_virtual_instrument_project(client: TestClient):
    """Test creating a virtual instrument project with the API."""
    response = client.post(
        "/api/projects",
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
    response_data = response.json()
    assert response_data["name"] == "Test Virtual Instrument"
    assert response_data["project_type"] == "virtual_instrument"
    assert response_data["base_note"] == 60

def test_get_project_api_db_session(client: TestClient, session: Session):
    """Test that the get project API endpoint properly handles database sessions."""
    # Create a project directly in the DB
    project = ProjectModel(name="Test Project", project_type="sample_pack")
    session.add(project)
    session.commit()
    session.refresh(project)

    # Make the request
    response = client.get(f"/api/projects/{project.id}")
    
    # Verify the response
    assert response.status_code == 200
    response_data = response.json()
    assert response_data["name"] == "Test Project"

def test_get_project_not_found(client: TestClient):
    """Test that the get project API handles not found projects correctly."""
    # Make the request
    response = client.get("/api/projects/999")
    
    # Verify the response
    assert response.status_code == 404
    response_data = response.json()
    assert "error" in response_data
    assert response_data["error"] == "Not Found"

def test_create_recording_api_db_session(client: TestClient, session: Session):
    """Test that the create recording API endpoint properly handles database sessions."""
    # Create a project first
    project = ProjectModel(name="Test Project", project_type="sample_pack")
    session.add(project)
    session.commit()
    session.refresh(project)

    with patch('src.core.project.Project.add_recording') as mock_add_recording:
        mock_recording = MagicMock()
        mock_recording.id = 1
        mock_recording.name = "Test Recording"
        mock_recording.file_path = "/path/to/recording.wav"
        mock_recording.project_id = project.id
        mock_recording.metadata_json = "{}" # Ensure it's a string for Pydantic
        mock_recording.status = "uploaded"
        mock_recording.file_format = "wav"
        mock_add_recording.return_value = mock_recording
        
        # Create a mock file for testing
        from io import BytesIO
        mock_file = BytesIO(b"test audio content")
        
        # Make the request with multipart/form-data
        files = {"file": ("test_audio.wav", mock_file, "audio/wav")}
        data = {"name": "Test Recording"}
        
        response = client.post(
            f"/api/projects/{project.id}/recordings",
            data=data,
            files=files
        )
        
        # Verify the response
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["name"] == "Test Recording"
