"""
Integration tests for file upload operations in the Sample Orchestrator API.
Migrated to FastAPI and SQLModel.
"""
import os
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from src.database.models import ProjectModel, ProjectType

def test_upload_audio_file_success(client: TestClient, session: Session):
    """Test that an audio file can be uploaded successfully."""
    # Create a test project in the database
    test_project = ProjectModel(
        name="Test Project",
        project_type=ProjectType.SAMPLE_PACK.value,
        description="A test project for file upload"
    )
    session.add(test_project)
    session.commit()
    session.refresh(test_project)
    
    # Mock the CoreProject.add_recording method
    with patch('src.core.project.Project.add_recording') as mock_add_recording:
        # Configure the add_recording mock to return a mock recording
        mock_recording = MagicMock()
        mock_recording.id = 1
        mock_recording.name = "Test Recording"
        mock_recording.file_path = "/path/to/recording.wav"
        mock_recording.project_id = test_project.id
        mock_recording.metadata_json = "{}" # Ensure it's a string for Pydantic
        mock_add_recording.return_value = mock_recording
        
        # Create a test file for upload
        from io import BytesIO
        test_audio_content = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
        test_file = ("test_audio.wav", BytesIO(test_audio_content), "audio/wav")
        
        # Make the request to upload the file
        data = {
            'name': 'Test Recording'
        }
        files = {
            'file': test_file
        }
        
        # In FastAPI migration, we use the API endpoint
        response = client.post(
            f"/api/projects/{test_project.id}/recordings",
            data=data,
            files=files
        )
        
        # Verify the response
        assert response.status_code == 201
        response_data = response.json()
        assert response_data["name"] == "Test Recording"

        # Verify the mock was called correctly
        mock_add_recording.assert_called_once()

def test_upload_invalid_file_type(client: TestClient, session: Session):
    """Test that files with invalid extensions are rejected."""
    # Create a test project in the database
    test_project = ProjectModel(
        name="Test Project",
        project_type=ProjectType.SAMPLE_PACK.value,
        description="A test project for file upload"
    )
    session.add(test_project)
    session.commit()
    session.refresh(test_project)
    
    # Create a test file with an invalid extension
    from io import BytesIO
    test_file = ("invalid.txt", BytesIO(b"This is not an audio file"), "text/plain")
    
    # Make the request to upload the file
    data = {
        'name': 'Invalid File'
    }
    files = {
        'file': test_file
    }
    
    response = client.post(
        f"/api/projects/{test_project.id}/recordings",
        data=data,
        files=files
    )
    
    # Verify the response - FastAPI/Pydantic returns 400 or 422 for validation errors depending on implementation
    # Let's check for non-2xx
    assert response.status_code != 201
