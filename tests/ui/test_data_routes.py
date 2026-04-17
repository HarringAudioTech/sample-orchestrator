"""
Integration tests for data-related UI routes.
Migrated to FastAPI and SQLModel with correct URL prefixes.
"""
import pytest
from sqlmodel import Session
from fastapi.testclient import TestClient

from src.database.models import ProjectModel, RecordingModel, SampleModel, ProjectType

def test_view_recording_not_found(client: TestClient):
    """Test the view recording page returns 404 when recording ID doesn't exist."""
    # Note: project_id is part of the prefix but for a 404 on recording_id, we can use any project_id
    response = client.get("/ui/projects/1/recordings/99999")
    assert response.status_code == 404

def test_view_recording_loads_with_recording(client: TestClient, session: Session):
    """Test the view recording page loads properly when a valid recording ID is provided."""
    project = ProjectModel(name="Test Project", project_type=ProjectType.SAMPLE_PACK.value)
    session.add(project)
    session.commit()

    recording = RecordingModel(name="Test Recording", project_id=project.id, file_path="/path/to/recording.wav")
    session.add(recording)
    session.commit()

    response = client.get(f"/ui/projects/{project.id}/recordings/{recording.id}")
    assert response.status_code == 200
    response_text = response.text
    assert "Test Recording" in response_text

def test_view_recording_shows_samples(client: TestClient, session: Session):
    """Test the view recording page displays samples associated with the recording."""
    project = ProjectModel(name="Test Project", project_type=ProjectType.SAMPLE_PACK.value)
    session.add(project)
    session.commit()

    recording = RecordingModel(name="Test Recording", project_id=project.id, file_path="/path/to/recording.wav")
    session.add(recording)
    session.commit()

    sample1 = SampleModel(name="sample1", recording_id=recording.id, file_path="/path/to/sample1.wav")
    sample2 = SampleModel(name="sample2", recording_id=recording.id, file_path="/path/to/sample2.wav")
    session.add(sample1)
    session.add(sample2)
    session.commit()

    response = client.get(f"/ui/projects/{project.id}/recordings/{recording.id}")
    assert response.status_code == 200
    response_text = response.text
    assert "sample1" in response_text
    assert "sample2" in response_text

def test_view_sample_not_found(client: TestClient):
    """Test the view sample page returns 404 when sample ID doesn't exist."""
    response = client.get("/ui/projects/1/samples/99999")
    assert response.status_code == 404

def test_view_sample_loads_with_sample(client: TestClient, session: Session):
    """Test the view sample page loads properly when a valid sample ID is provided."""
    project = ProjectModel(name="Test Project", project_type=ProjectType.SAMPLE_PACK.value)
    session.add(project)
    session.commit()

    recording = RecordingModel(name="Test Recording", project_id=project.id, file_path="/path/to/recording.wav")
    session.add(recording)
    session.commit()

    sample = SampleModel(name="sample", recording_id=recording.id, file_path="/path/to/sample.wav")
    session.add(sample)
    session.commit()

    response = client.get(f"/ui/projects/{project.id}/samples/{sample.id}")
    assert response.status_code == 200
    response_text = response.text
    assert "sample" in response_text
