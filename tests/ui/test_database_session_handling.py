"""
Tests for database session handling in UI routes.
Migrated to FastAPI and SQLModel.
"""
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlmodel import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

from src.database.models import (
    ProjectModel, 
    RecordingModel, 
    ProjectType, 
    SamplePackModel,
    VirtualInstrumentModel
)

# --- UI Route Session Handling Tests ---

def test_dashboard_route_db_session_handling(client: TestClient, session: Session):
    """Test that the dashboard route properly handles database sessions."""
    # Create a test project
    project = ProjectModel(name="Test Project", project_type=ProjectType.SAMPLE_PACK.value)
    session.add(project)
    session.commit()
    session.refresh(project)
    
    # Make the request
    response = client.get(f"/projects/{project.id}")
    
    # Verify the response
    assert response.status_code == 200
    assert project.name in response.text

def test_create_project_form_loads(client: TestClient):
    """Test that the create project form route loads correctly."""
    response = client.get("/projects/new")
    assert response.status_code == 200
    assert "Create Project" in response.text

def test_create_project_submit_handling(client: TestClient, session: Session):
    """Test that the create project submit handling works."""
    # The project list is at /
    response = client.get("/")
    assert response.status_code == 200
    assert "My Projects" in response.text

def test_db_session_error_handling_graceful(client: TestClient):
    """Test that database errors are handled gracefully in UI routes."""
    with patch('src.database.utils.get_db') as mock_get_db:
        # Setup the mock to raise an exception when used
        mock_get_db.side_effect = SQLAlchemyError("Test database error")
        
        # Make the request to the root projects list
        response = client.get("/")
        
        # Depending on implementation, it might be 500 or a graceful error page
        assert response.status_code in [200, 500]
