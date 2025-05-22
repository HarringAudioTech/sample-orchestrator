import pytest
import json
from flask import Flask
from unittest.mock import patch, MagicMock
from src.app import create_app # Assuming your Flask app factory is in src.app
from src.database.utils import init_db as initialize_db_utils, get_engine, get_session_local
from src.database.models import Base, Project as ProjectModel

# --- Test Fixtures ---
@pytest.fixture(scope="module") # Use module scope for app to be faster
def app():
    """Create and configure a new app instance for each test module."""
    # Use an in-memory SQLite database for testing API routes
    test_db_url = "sqlite:///:memory:"
    
    # Create a Flask app configured for testing
    flask_app = create_app() # Your actual app factory
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": test_db_url, # If your app uses this config key
        "DATABASE_URL": test_db_url # If your app uses this for your custom utils
    })

    # Override database utilities to use the test database
    # This is crucial if your routes directly call get_db or SessionLocal from utils
    engine = get_engine(test_db_url)
    
    # Re-initialize global engine and SessionLocal in utils for the test app context
    # This is a bit of a hack due to the global nature of _engine and _SessionLocal in utils.py
    # A better approach would be for utils.py to accept app.config for DB URL.
    import src.database.utils as db_utils
    db_utils._engine = engine 
    db_utils._SessionLocal = get_session_local(engine_instance=engine)

    with flask_app.app_context():
        initialize_db_utils(engine_instance=engine) # Create tables in the in-memory DB

    yield flask_app

    # Teardown: if there's any global state to clean for the app, do it here.
    # For in-memory DB, it's usually gone when the engine/connection closes.
    # Resetting the globals in utils for safety if other test modules use default DB.
    db_utils._engine = None
    db_utils._SessionLocal = None


@pytest.fixture
def client(app: Flask):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture(autouse=True) # Automatically use this for each test in this file
def manage_database_session(app: Flask):
    """Ensure each test has a fresh database session and tables are clean."""
    engine = get_engine("sqlite:///:memory:") # Always get a fresh in-memory engine for full isolation
    
    # Re-assign globals in utils for this specific test function's context
    import src.database.utils as db_utils
    original_engine = db_utils._engine
    original_session_local = db_utils._SessionLocal
    
    db_utils._engine = engine
    db_utils._SessionLocal = get_session_local(engine_instance=engine)

    with app.app_context(): # Ensure operations are within app context
      Base.metadata.drop_all(bind=engine) # Drop all tables
      Base.metadata.create_all(bind=engine) # Create all tables

    yield # Run the test

    # Teardown after test: drop all tables to ensure no state leaks
    with app.app_context():
      Base.metadata.drop_all(bind=engine)
    
    # Restore original engine and session local if they were set
    db_utils._engine = original_engine
    db_utils._SessionLocal = original_session_local


# --- Project Route Tests ---

def test_create_project_success(client):
    response = client.post('/projects', json={
        "name": "My First API Project",
        "description": "A project created via API test"
    })
    assert response.status_code == 201
    data = response.get_json()
    assert "id" in data
    assert data["name"] == "My First API Project"
    assert data["description"] == "A project created via API test"

    # Verify in DB (optional, but good for confidence)
    # This requires getting a session in the test, similar to how routes do.
    # For simplicity, we trust the route's own DB interaction for now,
    # or we'd need to setup db_session fixture like in model tests.
    
    # Example DB verification (if you set up a db_session fixture for API tests too):
    # project_in_db = db_session.query(ProjectModel).filter(ProjectModel.id == data['id']).first()
    # assert project_in_db is not None
    # assert project_in_db.name == "My First API Project"


def test_create_project_missing_name(client):
    response = client.post('/projects', json={
        "description": "Project without a name"
    })
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "Project name is required" in data["error"]

def test_get_project_success(client):
    # First, create a project to fetch
    create_resp = client.post('/projects', json={"name": "Fetchable Project"})
    assert create_resp.status_code == 201
    project_id = create_resp.get_json()["id"]

    response = client.get(f'/projects/{project_id}')
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == project_id
    assert data["name"] == "Fetchable Project"

def test_get_project_not_found(client):
    response = client.get('/projects/9999') # Assuming 9999 does not exist
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert "Project not found" in data["error"]

def test_list_projects_empty(client):
    response = client.get('/projects')
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 0

def test_list_projects_with_data(client):
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
    response = client.get('/')
    assert response.status_code == 200
    data = response.get_json()
    assert "message" in data
    assert "Welcome to the Audio Processing API!" in data["message"]
