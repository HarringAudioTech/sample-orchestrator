"""
API tests for project-related routes.

This module contains tests for creating, retrieving, and listing projects
via the Flask API endpoints. It uses pytest fixtures to set up a test
application instance and a test client.
"""

# import json # Standard library - Not directly used, Flask handles JSON in responses.
from unittest.mock import patch # Standard library (for mocking database utils)

from flask import Flask # Third-party
import pytest # Third-party
from sqlalchemy import create_engine # Third-party (for test DB engine)
from sqlalchemy.orm import sessionmaker # Third-party (for test DB session)

from src.app import create_app # Local application
from src.database.models import Base # ProjectModel not directly used in tests, but Base is for setup
# Removed: get_engine, get_session_local as utils.py was refactored
# Removed: ProjectModel, MagicMock as they are not used directly in this version of tests


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
        # Note: The DATABASE_URL for the app's utils will be patched by
        # the manage_database_session fixture for each test.
    })
    return flask_app

@pytest.fixture
def client(app: Flask): # app parameter is the app fixture
    """
    Provides a test client for the Flask application.
    """
    return app.test_client()

@pytest.fixture(autouse=True)
def manage_database_session(app: Flask): # app parameter is the app fixture
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
        with app.app_context():
            Base.metadata.create_all(bind=test_engine) # Create tables
        
        yield # Run the test function
        
        with app.app_context():
            Base.metadata.drop_all(bind=test_engine) # Drop tables after test


# --- Project Route Tests ---

def test_create_project_success(client):
    """
    Test successful creation of a new project via POST /projects.
    """
    response = client.post('/projects', json={
        "name": "My First API Project",
        "description": "A project created via API test"
    })
    assert response.status_code == 201
    data = response.get_json()
    assert "id" in data
    assert data["name"] == "My First API Project"
    assert data["description"] == "A project created via API test"
    # DB verification can be added here if a test DB session is made
    # available to the test function, but for API tests, checking response is primary.

def test_create_project_missing_name(client):
    """
    Test project creation failure when 'name' is missing in the request payload.
    """
    response = client.post('/projects', json={
        "description": "Project without a name" # 'name' field is intentionally missing
    })
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "Project name is required" in data["error"]

def test_get_project_success(client):
    """
    Test successfully retrieving an existing project by its ID.
    """
    # First, create a project to fetch
    create_response = client.post('/projects', json={"name": "Fetchable Project"})
    assert create_response.status_code == 201, "Project creation failed for get test."
    project_id = create_response.get_json()["id"]

    response = client.get(f'/projects/{project_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == project_id
    assert data["name"] == "Fetchable Project"

def test_get_project_not_found(client):
    """
    Test retrieving a non-existent project; expects a 404 error.
    """
    response = client.get('/projects/9999') # Use an ID unlikely to exist
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert "Project not found" in data["error"]

def test_list_projects_empty(client):
    """
    Test listing projects when the database has no projects; expects an empty list.
    """
    response = client.get('/projects')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert not data # Check if list is empty

def test_list_projects_with_data(client):
    """
    Test listing projects when multiple projects exist.
    """
    client.post('/projects', json={"name": "Project Alpha"})
    client.post('/projects', json={"name": "Project Beta"})

    response = client.get('/projects')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    project_names = sorted([p["name"] for p in data])
    assert project_names == ["Project Alpha", "Project Beta"]

def test_root_path(client):
    """
    Test the API's root path ("/") for the expected welcome message.
    """
    response = client.get('/')
    assert response.status_code == 200
    data = response.get_json()
    assert "message" in data
    expected_message = "Welcome to the Audio Processing and Sample Management API!"
    assert expected_message in data["message"]
