import pytest
import json
from flask import Flask
from unittest.mock import patch, MagicMock
from src.app import create_app  # Assuming your Flask app factory is in src.app
from src.database.utils import (
    init_db as initialize_db_utils,
    get_engine,
    get_session_local,
)
from src.database.models import Base, Project as ProjectModel


# --- Test Fixtures ---
@pytest.fixture(scope="module")  # Use module scope for app to be faster
def app():
    """Create and configure a new app instance for each test module."""
    # Use an in-memory SQLite database for testing API routes
    test_db_url = "sqlite:///:memory:"

    # Create a Flask app configured for testing
    flask_app = create_app()
    flask_app.config.update(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite:///:memory:",  # Use in-memory SQLite for tests
        }
    )

    # Create an engine instance specifically for tests, using the test DB URL
    engine = get_engine(flask_app.config["DATABASE_URL"])
    flask_app.test_engine = engine  # Attach to app for access in other fixtures
    # Provide this engine instance to the app config so get_engine() in utils can pick it up
    flask_app.config["TEST_ENGINE_INSTANCE"] = engine

    with flask_app.app_context():
        # Initialize the database schema using the test-specific engine
        initialize_db_utils(engine_instance=engine)
        # Note: The tables are created once per module.
        # manage_database_session will handle per-test data cleaning.

    yield flask_app

    # No explicit teardown needed for _engine or _SessionLocal patching, as it's removed.
    # The in-memory database ceases to exist when the connection is closed.


@pytest.fixture
def client(app: Flask):
    """A test client for the app."""
    return app.test_client()


# Automatically use this for each test in this file
@pytest.fixture(autouse=True)  # Ensures this runs for every test function
def manage_database_session(app: Flask):
    """
    Ensure each test has a clean database state (empty tables).
    Relies on the app fixture to have configured the DATABASE_URL for an
    in-memory DB and initialized the schema once.
    This fixture ensures data isolation between tests by clearing data.
    """
    with app.app_context():
        import logging

        logger = logging.getLogger(__name__)
        # Retrieve the test-specific engine from the app fixture
        engine = app.test_engine
        logger.info(f"manage_db_session: Engine URL from app.test_engine: {engine.url}")
        logger.info(
            f"manage_db_session: Sorted tables from Base.metadata: {[table.name for table in Base.metadata.sorted_tables]}"
        )

        # Clear all data from tables before each test
        # This is faster than dropping and recreating tables if the schema is stable
        for table in reversed(Base.metadata.sorted_tables):
            # Use a session to execute delete statements
            # Cannot use engine.execute(table.delete()) directly with SQLAlchemy 2.0 style
            # A session is needed.
            Session = get_session_local(engine_instance=engine)
            db = Session()
            try:
                db.execute(table.delete())
                db.commit()
            except Exception as e:
                db.rollback()
                app.logger.error(f"Error clearing table {table.name}: {e}")
                raise
            finally:
                db.close()

        # Alternative: Drop and recreate all tables (slower but robust if schema changes or complex relations)
        # Base.metadata.drop_all(bind=engine)
        # Base.metadata.create_all(bind=engine)

    yield  # Run the test

    # Teardown after test (optional, if yield above handles it per test)
    # For in-memory DB, data is gone anyway when connections close.
    # If using persistent DB for tests, this is where you'd clean up.
    # For this setup, clearing tables before each test is the primary strategy.


# --- Project Route Tests ---


def test_create_project_success(client):
    response = client.post(
        "/projects",
        json={
            "name": "My First API Project",
            "description": "A project created via API test",
        },
    )
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
    response = client.post("/projects", json={"description": "Project without a name"})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "Project name is required" in data["error"]


def test_get_project_success(client):
    # First, create a project to fetch
    create_resp = client.post("/projects", json={"name": "Fetchable Project"})
    assert create_resp.status_code == 201
    project_id = create_resp.get_json()["id"]

    response = client.get(f"/projects/{project_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == project_id
    assert data["name"] == "Fetchable Project"


def test_get_project_not_found(client):
    response = client.get("/projects/9999")  # Assuming 9999 does not exist
    assert response.status_code == 404
    data = response.get_json()
    assert "error" in data
    assert "Project not found" in data["error"]


def test_list_projects_empty(client):
    response = client.get("/projects")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_list_projects_with_data(client):
    client.post("/projects", json={"name": "Project Alpha"})
    client.post("/projects", json={"name": "Project Beta"})

    response = client.get("/projects")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    project_names = sorted([p["name"] for p in data])
    assert project_names == ["Project Alpha", "Project Beta"]


def test_root_path(client):
    response = client.get("/")
    assert response.status_code == 200
    data = response.get_json()
    assert "message" in data
    assert "Welcome to the Audio" in data["message"]
