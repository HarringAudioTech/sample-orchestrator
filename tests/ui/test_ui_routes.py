"""
Integration tests for UI routes, specifically focused on the dashboard rendering.
Migrated to FastAPI and SQLModel.
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from src.database.models import (
    ProjectModel, 
    RecordingModel, 
    ProjectType, 
    MidiDeviceModel,
    MidiCaptureSessionModel,
    VirtualInstrumentModel
)

# --- UI Route Tests ---

def test_ui_root_route(client: TestClient):
    """Test the UI root route (/) loads properly."""
    response = client.get("/")
    assert response.status_code == 200
    assert "My Projects" in response.text

def test_dashboard_not_found(client: TestClient):
    """Test the dashboard returns 404 when project ID doesn't exist."""
    response = client.get("/projects/99999")
    assert response.status_code == 404

def test_dashboard_loads_with_project(client: TestClient, session: Session):
    """Test the dashboard loads properly when a valid project ID is provided."""
    # Create a test project
    project = ProjectModel(name="Test Project", project_type=ProjectType.SAMPLE_PACK.value)
    session.add(project)
    session.commit()
    session.refresh(project)
    
    response = client.get(f"/projects/{project.id}")
    assert response.status_code == 200
    assert "Test Project" in response.text

def test_dashboard_shows_project_description(client: TestClient, session: Session):
    """Test the dashboard displays project description when available."""
    # Create a test project with a description
    project = ProjectModel(
        name="Project with Description", 
        project_type=ProjectType.SAMPLE_PACK.value, 
        description="This is a test project description"
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    
    response = client.get(f"/projects/{project.id}")
    assert response.status_code == 200
    assert "This is a test project description" in response.text

def test_dashboard_shows_default_description_message(client: TestClient, session: Session):
    """Test the dashboard displays default message when no project description is available."""
    # Create a test project without a description
    project = ProjectModel(name="Project without Description", project_type=ProjectType.SAMPLE_PACK.value)
    session.add(project)
    session.commit()
    session.refresh(project)
    
    response = client.get(f"/projects/{project.id}")
    assert response.status_code == 200
    # Update expectation based on new UI templates
    assert "No description provided" in response.text or "Sonic masterpiece" in response.text

def test_dashboard_shows_recordings(client: TestClient, session: Session):
    """Test the dashboard displays recordings associated with the project."""
    # Create a test project
    project = ProjectModel(name="Project with Recordings", project_type=ProjectType.SAMPLE_PACK.value)
    session.add(project)
    session.commit()
    session.refresh(project)
    
    # Add recordings to the project
    recording1 = RecordingModel(
        name="Test Recording 1", 
        project_id=project.id, 
        file_path="/path/to/recording1.wav"
    )
    recording2 = RecordingModel(
        name="Test Recording 2", 
        project_id=project.id, 
        file_path="/path/to/recording2.wav"
    )
    session.add(recording1)
    session.add(recording2)
    session.commit()
    session.refresh(project)
    
    response = client.get(f"/projects/{project.id}")
    assert response.status_code == 200
    assert "Test Recording 1" in response.text
    assert "Test Recording 2" in response.text

def test_dashboard_xss_protection(client: TestClient, session: Session):
    """Test that the dashboard properly escapes HTML in project names to prevent XSS."""
    # Create a test project with potentially dangerous HTML in the name
    special_name = "Project with <script>alert('XSS')</script> & \"quotes\""
    project = ProjectModel(name=special_name, project_type=ProjectType.SAMPLE_PACK.value)
    session.add(project)
    session.commit()
    session.refresh(project)
    
    response = client.get(f"/projects/{project.id}")
    assert response.status_code == 200
    
    # The raw script tags should not be present in the response
    assert "<script>alert('XSS')</script>" not in response.text
    # Check for escaped version (Jinja2 does this by default)
    assert "&lt;script&gt;" in response.text

def test_dashboard_with_unicode_chars(client: TestClient, session: Session):
    """Test that the dashboard properly handles project names with Unicode characters."""
    # Create a test project with Unicode characters in the name
    unicode_name = "Projet de Test Français (éàçüö)"
    project = ProjectModel(name=unicode_name, project_type=ProjectType.SAMPLE_PACK.value)
    session.add(project)
    session.commit()
    session.refresh(project)
    
    response = client.get(f"/projects/{project.id}")
    assert response.status_code == 200
    assert unicode_name in response.text

def test_create_project_form_loads(client: TestClient):
    """Test that the create project form page loads correctly."""
    response = client.get("/projects/new")
    assert response.status_code == 200
    assert "Create Project" in response.text
    assert "Project Name" in response.text
    assert "<form" in response.text

def test_styleguide_loads(client: TestClient):
    """Test that the styleguide page loads correctly."""
    response = client.get("/styleguide")
    assert response.status_code == 200
    assert "Design System Styleguide" in response.text
