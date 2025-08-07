"""
Integration tests for DSPreset settings UI routes.
"""
import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session as SQLAlchemySession

from src.app import create_app
from src.database import utils
from src.database.utils import init_db as initialize_db_utils
from src.database.models import Base, ProjectModel, VirtualInstrumentModel, ProjectType, RecordingModel, SampleModel

from typing import Generator


# --- Test Fixtures ---
@pytest.fixture(scope="function")
def app() -> Generator[Flask, None, None]:
    """Create and configure a new app instance for each test module."""
    flask_app = create_app()
    flask_app.config.update(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "SERVER_NAME": "localhost",
        }
    )

    with flask_app.app_context():
        initialize_db_utils()
        yield flask_app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """A test client for the app."""
    return app.test_client()


@pytest.fixture(scope="function")
def db_session(app: Flask) -> Generator[SQLAlchemySession, None, None]:
    """Provides a SQLAlchemy session with access to the test database."""
    session = utils.SessionLocal()
    yield session
    session.close()


@pytest.fixture(autouse=True)
def manage_database_tables(app: Flask, db_session: SQLAlchemySession) -> None:
    """Clean up database tables after each test."""
    yield
    for table in reversed(Base.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()


# --- Helper functions ---
def create_virtual_instrument_project(db_session: SQLAlchemySession, name: str = "Test VI Project") -> VirtualInstrumentModel:
    """Creates a virtual instrument project for testing."""
    project = VirtualInstrumentModel(
        name=name,
        project_type=ProjectType.VIRTUAL_INSTRUMENT.value,
        base_note=60,
        velocity_layers=1,
        round_robins=1
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project

# --- Tests ---

def test_dspreset_settings_page_loads(client: FlaskClient, db_session: SQLAlchemySession):
    """Test that the DSPreset settings page loads correctly for a virtual instrument project."""
    project = create_virtual_instrument_project(db_session)
    response = client.get(f"/ui/projects/{project.id}/dspreset_settings")
    assert response.status_code == 200
    assert "DSPreset Settings for Test VI Project" in response.data.decode("utf-8")
    assert "Project Name" in response.data.decode("utf-8")
    assert "Author" in response.data.decode("utf-8")
    assert "Base Note" in response.data.decode("utf-8")
    assert "Velocity Layers" in response.data.decode("utf-8")
    assert "Round Robins" in response.data.decode("utf-8")
    assert "Artwork" in response.data.decode("utf-8")

def test_dspreset_settings_page_not_for_sample_pack(client: FlaskClient, db_session: SQLAlchemySession):
    """Test that the DSPreset settings page returns 403 for a sample pack project."""
    project = ProjectModel(name="Test Sample Pack", project_type=ProjectType.SAMPLE_PACK.value)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    response = client.get(f"/ui/projects/{project.id}/dspreset_settings")
    assert response.status_code == 403

def test_update_dspreset_settings(client: FlaskClient, db_session: SQLAlchemySession):
    """Test that the DSPreset settings can be updated."""
    project = create_virtual_instrument_project(db_session)

    response = client.post(
        f"/ui/projects/{project.id}/dspreset_settings",
        data={
            "project_name": "Updated VI Project",
            "author": "Test Author",
            "base_note": "61",
            "velocity_layers": "2",
            "round_robins": "3",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "DSPreset settings updated successfully!" in response.data.decode("utf-8")

    db_session.refresh(project)

    updated_project = db_session.query(VirtualInstrumentModel).filter(VirtualInstrumentModel.id == project.id).first()
    assert updated_project.name == "Updated VI Project"
    assert updated_project.meta_data.get("author") == "Test Author"
    assert updated_project.base_note == 61
    assert updated_project.velocity_layers == 2
    assert updated_project.round_robins == 3
