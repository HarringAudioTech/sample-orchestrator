"""
Integration tests for data-related UI routes.
"""
import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session as SQLAlchemySession

from src.app import create_app
from src.database import utils
from src.database.models import Base, ProjectModel, RecordingModel, SampleModel, ProjectType

@pytest.fixture(scope="module")
def app() -> Flask:
    """Create and configure a new app instance for each test module."""
    flask_app = create_app()
    flask_app.config.update({
        "TESTING": True,
        "DATABASE_URL": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SERVER_NAME": "localhost",
    })
    with flask_app.app_context():
        utils.init_db()
    yield flask_app

@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """A test client for the app."""
    return app.test_client()

@pytest.fixture(scope="function")
def db_session(app: Flask) -> SQLAlchemySession:
    """Provides a SQLAlchemy session with access to the test database."""
    with app.app_context():
        session = utils.get_db().__enter__()
        yield session
        session.close()
        # Clean up database after each test
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(table.delete())
        session.commit()


def test_view_recording_not_found(client: FlaskClient):
    """Test the view recording page returns 404 when recording ID doesn't exist."""
    response = client.get("/ui/recordings/99999")
    assert response.status_code == 404

def test_view_recording_loads_with_recording(client: FlaskClient, db_session: SQLAlchemySession):
    """Test the view recording page loads properly when a valid recording ID is provided."""
    project = ProjectModel(name="Test Project", project_type=ProjectType.SAMPLE_PACK)
    db_session.add(project)
    db_session.commit()

    recording = RecordingModel(name="Test Recording", project_id=project.id, file_path="/path/to/recording.wav")
    db_session.add(recording)
    db_session.commit()

    response = client.get(f"/ui/recordings/{recording.id}")
    assert response.status_code == 200
    response_data = response.data.decode("utf-8")
    assert "Recording - Test Recording" in response_data
    assert "Test Recording" in response_data

def test_view_recording_shows_samples(client: FlaskClient, db_session: SQLAlchemySession):
    """Test the view recording page displays samples associated with the recording."""
    project = ProjectModel(name="Test Project", project_type=ProjectType.SAMPLE_PACK)
    db_session.add(project)
    db_session.commit()

    recording = RecordingModel(name="Test Recording", project_id=project.id, file_path="/path/to/recording.wav")
    db_session.add(recording)
    db_session.commit()

    sample1 = SampleModel(name="sample1", recording_id=recording.id, file_path="/path/to/sample1.wav")
    sample2 = SampleModel(name="sample2", recording_id=recording.id, file_path="/path/to/sample2.wav")
    db_session.add_all([sample1, sample2])
    db_session.commit()

    response = client.get(f"/ui/recordings/{recording.id}")
    assert response.status_code == 200
    response_data = response.data.decode("utf-8")
    assert "/path/to/sample1.wav" in response_data
    assert "/path/to/sample2.wav" in response_data

def test_view_sample_not_found(client: FlaskClient):
    """Test the view sample page returns 404 when sample ID doesn't exist."""
    response = client.get("/ui/samples/99999")
    assert response.status_code == 404

def test_view_sample_loads_with_sample(client: FlaskClient, db_session: SQLAlchemySession):
    """Test the view sample page loads properly when a valid sample ID is provided."""
    project = ProjectModel(name="Test Project", project_type=ProjectType.SAMPLE_PACK)
    db_session.add(project)
    db_session.commit()

    recording = RecordingModel(name="Test Recording", project_id=project.id, file_path="/path/to/recording.wav")
    db_session.add(recording)
    db_session.commit()

    sample = SampleModel(name="sample", recording_id=recording.id, file_path="/path/to/sample.wav")
    db_session.add(sample)
    db_session.commit()

    response = client.get(f"/ui/samples/{sample.id}")
    assert response.status_code == 200
    response_data = response.data.decode("utf-8")
    assert f"Sample - {sample.name}" in response_data
    assert "/path/to/sample.wav" in response_data
