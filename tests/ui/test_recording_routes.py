"""
Integration tests for Recording UI routes.
"""
import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session as SQLAlchemySession

from src.app import create_app
from src.database import utils
from src.database.utils import init_db as initialize_db_utils
from src.database.models import Base, ProjectModel, RecordingModel, SampleModel

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
def create_project_with_recording(db_session: SQLAlchemySession, project_name: str = "Test Project", recording_name: str = "Test Recording") -> RecordingModel:
    """Creates a project with a recording for testing."""
    project = ProjectModel(name=project_name, project_type="sample_pack")
    recording = RecordingModel(name=recording_name, file_path="/path/to/recording", project=project)
    db_session.add(project)
    db_session.add(recording)
    db_session.commit()
    db_session.refresh(recording)
    return recording

# --- Tests ---

def test_view_recording_page_loads(client: FlaskClient, db_session: SQLAlchemySession):
    """Test that the view recording page loads correctly."""
    recording = create_project_with_recording(db_session)
    project_id = recording.project_id
    recording_id = recording.id

    response = client.get(f"/ui/projects/{project_id}/recordings/{recording_id}")
    assert response.status_code == 200
    response_data = response.data.decode("utf-8")
    assert "Recording: Test Recording" in response_data
    assert "Recording Details" in response_data
    assert "ID:" in response_data
    assert "Name:" in response_data
    assert "File Path:" in response_data
    assert "Status:" in response_data
    assert "Created At:" in response_data
    assert "Samples" in response_data
    assert "No samples found for this recording." in response_data
