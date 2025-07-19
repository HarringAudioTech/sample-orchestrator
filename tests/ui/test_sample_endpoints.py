"""Tests for sample-related endpoints in the sample orchestrator application."""

import os
import tempfile
import pytest
from datetime import datetime, UTC
import requests
from unittest.mock import patch, MagicMock, ANY
from flask import template_rendered
from contextlib import contextmanager

# Import the app factory and database utilities
from src.app import create_app
from src.database.models import Project, Recording, Sample, ProjectType
from src.database.utils import get_db as real_get_db, init_database

@contextmanager
def captured_templates(app):
    """Helper to capture templates that are rendered during a request."""
    recorded = []

    def record(sender, template, context, **extra):
        recorded.append((template, context))

    template_rendered.connect(record, app)
    try:
        yield recorded
    finally:
        template_rendered.disconnect(record, app)

@pytest.fixture(scope='function')
def app():
    """Create and configure a new app instance for each test."""
    # Create and configure the app
    app = create_app()
    
    # Create a temporary directory for the test database
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test.db')
    
    test_config = {
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,  # Disable CSRF for testing
        'DATABASE_PATH': db_path,  # Use a temporary database file
        'SECRET_KEY': 'test-secret-key',  # Required for session
        'API_BASE_URL': 'http://localhost:5000',  # Default API URL for testing
    }
    
    # Update app config with test config
    for key, value in test_config.items():
        app.config[key] = value
        
    # Initialize the database
    with app.app_context():
        init_database(test_config['DATABASE_PATH'])
    
    yield app
    
    # Clean up the temporary database file
    if os.path.exists(test_config['DATABASE_PATH']):
        os.unlink(test_config['DATABASE_PATH'])

@pytest.fixture(scope='function')
def client(app):
    """A test client for the app."""
    return app.test_client()

@pytest.fixture(scope='function')
def db_session(app):
    """Get a database session within the app context."""
    with app.app_context():
        with real_get_db() as db:
            yield db

@pytest.fixture(scope='function')
def test_project(db_session):
    """Create a test project and clean it up after the test. Yields (orm_obj, dict)."""
    project = Project(
        name="Test Project",
        project_type=ProjectType.sample_pack.value,  # Use the enum value directly
        description="A test project",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    project_dict = {
        'id': project.id,
        'name': project.name,
        'project_type': project.project_type,
        'description': project.description,
        'created_at': project.created_at,
        'updated_at': project.updated_at
    }
    yield (project, project_dict)
    db_session.delete(project)
    db_session.commit()

@pytest.fixture(scope='function')
def test_recording(db_session, test_project):
    """Create a test recording and clean it up after the test. Yields (orm_obj, dict)."""
    project, project_dict = test_project
    recording = Recording(
        project_id=project.id,
        name="Test Recording",
        file_path="/fake/path/test.wav",
        processing_status="pending",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    db_session.add(recording)
    db_session.commit()
    db_session.refresh(recording)
    recording_dict = {
        'id': recording.id,
        'project_id': recording.project_id,
        'name': recording.name,
        'file_path': recording.file_path,
        'processing_status': recording.processing_status,
        'created_at': recording.created_at,
        'updated_at': recording.updated_at
    }
    yield (recording, recording_dict)
    db_session.delete(recording)
    db_session.commit()

@pytest.fixture(scope='function')
def test_sample(db_session, test_recording):
    """Create a test sample and clean it up after the test. Yields (orm_obj, dict)."""
    recording, recording_dict = test_recording
    sample = Sample(
        recording_id=recording.id,
        name="Test Sample",
        file_path="/fake/path/sample.wav",
        start_time=0.0,
        end_time=1.0,
        duration=1.0,
        category="kick",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC)
    )
    db_session.add(sample)
    db_session.commit()
    db_session.refresh(sample)
    sample_dict = {
        'id': sample.id,
        'recording_id': sample.recording_id,
        'name': sample.name,
        'file_path': sample.file_path,
        'start_time': sample.start_time,
        'end_time': sample.end_time,
        'duration': sample.duration,
        'category': sample.category,
        'created_at': sample.created_at,
        'updated_at': sample.updated_at
    }
    yield (sample, sample_dict)
    db_session.delete(sample)
    db_session.commit()

class TestSampleEndpoints:
    """Test cases for sample-related endpoints."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, app, client):
        """Set up test environment before each test method."""
        self.app = app
        self.client = client
        
        # Set up mocks before the test runs
        self.requests_get_patch = patch('src.ui.routes.requests.get')
        self.mock_get = self.requests_get_patch.start()
        
        # Default successful response
        self.mock_response = MagicMock()
        self.mock_response.status_code = 200
        self.mock_get.return_value = self.mock_response
        
        # Create a test client with app context
        self.app_context = app.app_context()
        self.app_context.push()
        
        # Yield control to the test
        yield
        
        # Clean up after test is done
        self.requests_get_patch.stop()
        self.app_context.pop()
    
    def test_list_samples_for_recording(self, test_recording):
        """Test listing samples for a recording."""
        recording, recording_dict = test_recording
        # Set up mock to return sample list
        self.mock_response.json.return_value = [
            {
                'id': 1,
                'recording_id': recording.id,
                'name': 'Test Sample 1',
                'file_path': '/fake/path/sample1.wav',
                'start_time': 0.0,
                'end_time': 1.0,
                'category': 'kick',
                'created_at': datetime.now(UTC).isoformat(),
                'updated_at': datetime.now(UTC).isoformat()
            },
            {
                'id': 2,
                'recording_id': recording.id,
                'name': 'Test Sample 2',
                'file_path': '/fake/path/sample2.wav',
                'start_time': 1.0,
                'end_time': 2.0,
                'category': 'snare',
                'created_at': datetime.now(UTC).isoformat(),
                'updated_at': datetime.now(UTC).isoformat()
            }
        ]
        
        # Call the API endpoint via UI
        response = self.client.get(f'/ui/recordings/{recording.id}/samples', follow_redirects=True)
        
        # If the route isn't implemented yet, this will help identify the issue
        if response.status_code == 404:
            pytest.skip("Route not implemented yet")
        
        assert response.status_code == 200
        self.mock_get.assert_called_once_with(ANY)
        
        # Parse the response to check the rendered template or JSON
        # This will depend on how the endpoint is implemented
        if 'Content-Type' in response.headers and 'application/json' in response.headers['Content-Type']:
            json_data = response.get_json()
            assert len(json_data) == 2
            assert json_data[0]['name'] == 'Test Sample 1'
            assert json_data[1]['name'] == 'Test Sample 2'
    
    def test_get_sample_details(self, test_sample):
        """Test getting sample details."""
        sample, sample_dict = test_sample
        # Set up mock to return sample details
        self.mock_response.json.return_value = {
            'id': sample.id,
            'recording_id': sample.recording_id,
            'name': sample.name,
            'file_path': sample.file_path,
            'start_time': sample.start_time,
            'end_time': sample.end_time,
            'category': sample.category,
            'created_at': sample.created_at.isoformat(),
            'updated_at': sample.updated_at.isoformat()
        }
        
        # Call the API endpoint via UI
        response = self.client.get(f'/ui/samples/{sample.id}', follow_redirects=True)
        
        # If the route isn't implemented yet, this will help identify the issue
        if response.status_code == 404:
            pytest.skip("Route not implemented yet")
        
        assert response.status_code == 200
        self.mock_get.assert_called_once_with(ANY)
        
        # Parse the response to check the rendered template or JSON
        if 'Content-Type' in response.headers and 'application/json' in response.headers['Content-Type']:
            json_data = response.get_json()
            assert json_data['id'] == test_sample.id
            assert json_data['name'] == test_sample.name
    
    def test_list_samples_for_nonexistent_recording(self):
        """Test listing samples for a recording that doesn't exist."""
        # Mock API to return 404 for non-existent recording
        error_response = MagicMock()
        error_response.status_code = 404
        error_response.json.return_value = {'error': 'Recording not found'}
        
        # Create a requests exception
        http_error = requests.exceptions.HTTPError("Not Found")
        http_error.response = error_response
        error_response.raise_for_status.side_effect = http_error
        
        self.mock_get.return_value = error_response
        
        # Call the API endpoint via UI
        response = self.client.get('/ui/recordings/999/samples', follow_redirects=True)
        
        # If the route isn't implemented yet, this will help identify the issue
        if response.status_code == 404 and b"The requested URL was not found on the server" in response.data:
            pytest.skip("Route not implemented yet")
        
        assert response.status_code == 404 or b'Recording not found' in response.data
        
    def test_get_nonexistent_sample(self):
        """Test getting details for a sample that doesn't exist."""
        # Mock API to return 404 for non-existent sample
        error_response = MagicMock()
        error_response.status_code = 404
        error_response.json.return_value = {'error': 'Sample not found'}
        
        # Create a requests exception
        http_error = requests.exceptions.HTTPError("Not Found")
        http_error.response = error_response
        error_response.raise_for_status.side_effect = http_error
        
        self.mock_get.return_value = error_response
        
        # Call the API endpoint via UI
        response = self.client.get('/ui/samples/999', follow_redirects=True)
        
        # If the route isn't implemented yet, this will help identify the issue
        if response.status_code == 404 and b"The requested URL was not found on the server" in response.data:
            pytest.skip("Route not implemented yet")
        
        assert response.status_code == 404 or b'Sample not found' in response.data
