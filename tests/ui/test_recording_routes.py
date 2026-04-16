"""
Integration tests for Recording UI routes.
"""
import pytest
from sqlmodel import Session, select
from fastapi.testclient import TestClient

from src.database.models import ProjectModel, RecordingModel

# --- Helper functions ---
def create_project_with_recording(session: Session, project_name: str = "Test Project", recording_name: str = "Test Recording") -> RecordingModel:
    """Creates a project with a recording for testing."""
    project = ProjectModel(name=project_name, project_type="sample_pack")
    session.add(project)
    session.commit()
    session.refresh(project)
    
    recording = RecordingModel(name=recording_name, file_path="/path/to/recording", project_id=project.id)
    session.add(recording)
    session.commit()
    session.refresh(recording)
    return recording

# --- Tests ---

def test_view_recording_page_loads(client: TestClient, session: Session):
    """Test that the view recording page loads correctly."""
    recording = create_project_with_recording(session)
    project_id = recording.project_id
    recording_id = recording.id

    response = client.get(f"/ui/projects/{project_id}/recordings/{recording_id}")
    assert response.status_code == 200
    response_text = response.text
    assert "Recording: Test Recording" in response_text
    assert "Recording Details" in response_text
    assert "ID:" in response_text
    assert "Name:" in response_text
    assert "File Path:" in response_text
    assert "Status:" in response_text
    assert "Created At:" in response_text
    assert "Samples" in response_text
    assert "No samples found for this recording." in response_text
