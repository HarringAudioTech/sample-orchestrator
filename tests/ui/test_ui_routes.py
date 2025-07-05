import pytest
import json
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.engine import Engine

from src.app import create_app
from src.database.utils import (
    init_db as initialize_db_utils,
    get_engine,
    get_session_local,
)
from src.database.models import Base, Project as ProjectModel, Recording as RecordingModel

from typing import Generator


# --- Test Fixtures ---
@pytest.fixture(scope="module")
def app() -> Generator[Flask, None, None]:
    """Create and configure a new app instance for each test module."""
    flask_app: Flask = create_app()
    flask_app.config.update(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,  # Disable CSRF for simpler form tests if any
            "SERVER_NAME": "localhost", # Required for url_for to work correctly in tests
        }
    )

    engine: Engine = get_engine(flask_app.config["DATABASE_URL"])
    flask_app.config["TEST_ENGINE_INSTANCE"] = engine

    with flask_app.app_context():
        initialize_db_utils(engine_instance=engine)

    yield flask_app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """A test client for the app."""
    with app.app_context():
        return app.test_client()


@pytest.fixture(scope="function") # Changed to function scope for UI tests if DB state needs to be very specific per test
def db_session(app: Flask) -> Generator[SQLAlchemySession, None, None]:
    """Provides a SQLAlchemy session with access to the test database.
    Ensures the session is closed after the test.
    """
    engine: Engine = app.config["TEST_ENGINE_INSTANCE"]
    SessionLocal_test = get_session_local(engine_instance=engine)
    session: SQLAlchemySession = SessionLocal_test()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def manage_database_tables(app: Flask, db_session: SQLAlchemySession) -> Generator[None, None, None]:
    """Ensure each test has a clean database state (empty tables)."""
    # The app context is already active from the app fixture for initializing the schema
    # For clearing tables, we use the db_session fixture which provides a session
    # from the app's test engine.

    # Clear data from all tables before each test
    for table in reversed(Base.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()

    yield

    # No explicit teardown needed here as db_session fixture handles session closing
    # and in-memory DB data is lost when connection closes.


# --- UI Route Tests ---

def test_dashboard_project_not_exists(client: FlaskClient):
    """Test dashboard returns 404 for a non-existent project."""
    response = client.get("/ui/projects/99999/dashboard")
    assert response.status_code == 404
    # Check for content from the error.html template
    assert b"Error 404" in response.data
    assert b"Project with ID 99999 not found" in response.data
    assert b"Go to Homepage" in response.data # Link from error.html


def test_dashboard_project_exists_no_recordings(client: FlaskClient, db_session: SQLAlchemySession):
    """Test dashboard for an existing project with no recordings."""
    # Create a project
    project = ProjectModel(name="UI Test Project 1", description="No recordings here")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    response = client.get(f"/ui/projects/{project.id}/dashboard")
    assert response.status_code == 200
    response_data = response.data.decode("utf-8")

    assert f"Project Dashboard: {project.name}" in response_data
    assert "No audio files have been imported for this project yet." in response_data
    assert "Imported Audio Files" not in response_data # Table heading should not be present


def test_dashboard_project_exists_with_recordings(client: FlaskClient, db_session: SQLAlchemySession):
    """Test dashboard for an existing project with recordings."""
    # Create a project
    project = ProjectModel(name="UI Test Project 2", description="Has recordings")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    # Create recordings for this project
    rec1 = RecordingModel(
        project_id=project.id,
        name="audio_file_1.wav",
        file_path="/path/to/audio_1.wav",
        filesize=123456,
        duration_seconds=10.5,
        samplerate=44100,
        channels=2,
        status="processed"
    )
    rec2 = RecordingModel(
        project_id=project.id,
        name="long_audio_sample.mp3",
        file_path="/another/path/long_audio_sample.mp3",
        filesize=7890123,
        duration_seconds=185.7,
        samplerate=48000,
        channels=1,
        status="processed"
    )
    rec3 = RecordingModel( # Recording with missing filesize/duration
        project_id=project.id,
        name="incomplete_meta.aif",
        file_path="/path/incomplete.aif",
        filesize=None,
        duration_seconds=None,
        status="pending"
    )
    db_session.add_all([rec1, rec2, rec3])
    db_session.commit()
    db_session.refresh(rec1)
    db_session.refresh(rec2)
    db_session.refresh(rec3)

    response = client.get(f"/ui/projects/{project.id}/dashboard")
    assert response.status_code == 200
    response_data = response.data.decode("utf-8")

    assert f"Project Dashboard: {project.name}" in response_data
    assert "Imported Audio Files" in response_data
    assert "No audio files have been imported for this project yet." not in response_data

    # Check for rec1 details
    assert rec1.name in response_data
    assert str(rec1.filesize) in response_data
    assert str(rec1.duration_seconds) in response_data

    # Check for rec2 details
    assert rec2.name in response_data
    assert str(rec2.filesize) in response_data
    assert str(rec2.duration_seconds) in response_data

    # Check for rec3 details (handling None)
    assert rec3.name in response_data
    assert "N/A" in response_data # Check for how None filesize/duration is rendered

    # Check table structure (presence of <td> tags for specific data points)
    assert f"<td>{rec1.name}</td>" in response_data
    assert f"<td>{rec1.filesize}</td>" in response_data
    assert f"<td>{rec1.duration_seconds}</td>" in response_data

    assert f"<td>{rec3.name}</td>" in response_data
    assert f"<td>N/A</td>" in response_data # For filesize of rec3
    # Assuming duration for rec3 is also N/A if both are None
    # Example: <td>N/A</td><td>N/A</td>

    # Count N/A occurrences for rec3 to be more specific
    # Each None field for rec3 (filesize, duration_seconds) should result in one "N/A"
    # So, for rec3, we expect two "N/A"s in its row.
    # A more robust check might parse the HTML table or count specific row content.
    # This simple check might be fragile if "N/A" appears elsewhere for other reasons.
    # For now, let's assume this level of checking is sufficient:
    expected_na_for_rec3 = 0
    if rec3.filesize is None:
        expected_na_for_rec3 +=1
    if rec3.duration_seconds is None:
        expected_na_for_rec3 +=1

    # This is a bit tricky with simple string contains. A more robust HTML parsing would be better.
    # For this test, checking for one "N/A" is a basic confirmation.
    # More specific would be: assert f"<td>{rec3.name}</td><td>N/A</td><td>N/A</td>" in response_data (if order is fixed)
    # For now, checking "N/A" appears at least `expected_na_for_rec3` times more than other N/A's
    # This is still not ideal. Let's keep it simple:
    assert "<td>N/A</td>" in response_data # At least one N/A from rec3

    assert "No audio files have been imported for this project yet." not in response_data

# Example of how to add a project with a specific ID if needed,
# but usually letting auto-increment is fine for these tests.
# def test_specific_project_id_scenario(client: FlaskClient, db_session: SQLAlchemySession):
#     project = ProjectModel(id=100, name="Fixed ID Project")
#     db_session.add(project)
#     db_session.commit()
#     # ... rest of test ...
#     response = client.get(f"/ui/projects/100/dashboard")
#     assert response.status_code == 200
#     assert b"Fixed ID Project" in response.data

# Consider adding a test for a project that exists but has an ID of 0 if your system allows it,
# or other edge case IDs if relevant. For typical auto-incrementing primary keys, non-positive IDs
# shouldn't occur unless manually inserted or sequences are misconfigured.
# For this app, project_id is int, so positive integers are expected.
# Non-existent check (99999) covers invalid IDs well.
# Test for project ID 0 if it's a possible valid ID:
# def test_dashboard_project_id_zero(client: FlaskClient, db_session: SQLAlchemySession):
#     # Setup project with ID 0 if allowed and makes sense for your DB schema
#     # ...
#     # response = client.get("/ui/projects/0/dashboard")
#     # Assert accordingly
#     pass # Placeholder if ID 0 is not a special case or not allowed.

# Test with a project that has a name that might need HTML escaping (e.g., contains <, >, &)
# to ensure it's rendered safely by Jinja2 (which it does by default).
def test_dashboard_project_name_with_special_chars(client: FlaskClient, db_session: SQLAlchemySession):
    """Test project name with special HTML characters is displayed correctly (escaped)."""
    special_name = "Project with <script>alert('XSS')</script> & \"quotes\"" # Restored original
    project = ProjectModel(name=special_name)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    response = client.get(f"/ui/projects/{project.id}/dashboard")
    assert response.status_code == 200
    response_data = response.data.decode("utf-8")

    # Based on DEBUG_OUTPUT:
    # & -> &amp;
    # < -> &lt;
    # > -> &gt;
    # " -> &#34;  (Note: not &quot;)
    # ' -> &#39;
    escaped_name = "Project with &lt;script&gt;alert(&#39;XSS&#39;)&lt;/script&gt; &amp; &#34;quotes&#34;"

    expected_h1_content = f"<h1>Project Dashboard: {escaped_name}</h1>"
    expected_title_content = f"<title>Dashboard - {escaped_name}</title>"

    # Normalize whitespace for robust comparison
    normalized_response_data = ' '.join(response_data.split())

    # Check for the core escaped string content first
    core_escaped_name_part = escaped_name
    assert core_escaped_name_part in normalized_response_data

    # If the core part is found, then check the full H1 and title structure
    normalized_expected_h1 = ' '.join(expected_h1_content.split())
    normalized_expected_title = ' '.join(expected_title_content.split())

    assert normalized_expected_h1 in normalized_response_data
    assert normalized_expected_title in normalized_response_data

    # Ensure the raw special_name string is NOT present in the response_data
    assert special_name not in response_data
    # Also ensure common problematic substrings from the original raw string are not present if they imply lack of escaping
    assert "<script>alert('XSS')</script>" not in response_data
    assert " & \"quotes\"" not in response_data

# Test project name with non-ASCII characters (Unicode)
def test_dashboard_project_name_with_unicode_chars(client: FlaskClient, db_session: SQLAlchemySession):
    """Test project name with Unicode characters is displayed correctly."""
    unicode_name = "Projet de Test Français (éàçüö)"
    project = ProjectModel(name=unicode_name)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    response = client.get(f"/ui/projects/{project.id}/dashboard")
    assert response.status_code == 200
    response_data = response.data.decode("utf-8") # Ensure decoding as UTF-8

    assert f"Project Dashboard: {unicode_name}" in response_data
    assert f"<title>Dashboard - {unicode_name}</title>" in response_data
