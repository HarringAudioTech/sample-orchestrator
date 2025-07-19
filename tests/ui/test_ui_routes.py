"""Tests for the UI routes in the sample orchestrator application."""

import os
import tempfile
import pytest
from datetime import datetime, timezone, UTC
import requests
from unittest.mock import patch, MagicMock, ANY, create_autospec
from flask import url_for, template_rendered, request, current_app, session, g
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session, Session

# Import the app factory and database utilities
from src.app import create_app
from src.database.models import Project, Recording, Base, MidiDevice, MidiCaptureSession, MidiFile, ProjectType
from src.database.utils import get_db as real_get_db, init_database, get_engine
from src.ui.routes import _ensure_consistent_context

# Set up test configuration
def create_test_config():
    """Create a test configuration with a temporary database file."""
    # Create a temporary directory for the test database
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test.db')
    
    return {
        'TESTING': True,
        'WTF_CSRF_ENABLED': False,  # Disable CSRF for testing
        'DATABASE_PATH': db_path,  # Use a temporary database file
        'SECRET_KEY': 'test-secret-key',  # Required for session
    }

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
    test_config = create_test_config()
    
    # Update app config with test config
    for key, value in test_config.items():
        app.config[key] = value
        
    # Initialize the database
    with app.app_context():
        # Initialize the database with test config
        init_database(test_config['DATABASE_PATH'])
    
    yield app
    
    # Clean up the temporary database file
    if os.path.exists(test_config['DATABASE_PATH']):
        os.unlink(test_config['DATABASE_PATH'])

@pytest.fixture(scope='function')
def client(app):
    """A test client for the app."""
    return app.test_client()

class TestProjectCreation:
    """Test cases for project creation functionality."""
    
    @pytest.fixture(autouse=True)
    def setup_method(self, app, client):
        """Set up test environment before each test method."""
        self.app = app
        self.client = client
        
        # Set up mocks before the test runs
        self.requests_post_patch = patch('src.ui.routes.requests.post')
        self.mock_post = self.requests_post_patch.start()
        
        # Default successful response
        self.mock_response = MagicMock()
        self.mock_response.status_code = 201
        self.mock_response.json.return_value = {'id': 1, 'name': 'Test Project'}
        self.mock_post.return_value = self.mock_response
        
        # Set up database within the app context
        with app.app_context():
            with real_get_db() as db:
                # Clear any existing data
                db.query(Project).delete()
                
                # Create a test project with timezone-aware datetimes
                now = datetime.now(UTC)
                self.test_project = Project(
                    id=1,
                    name="Test Project",
                    project_type=ProjectType.sample_pack.value,  # Use enum value
                    description="A test project",
                    created_at=now,
                    updated_at=now
                )
                db.add(self.test_project)
                db.commit()
        
        # Create a test client with app context
        self.app_context = app.app_context()
        self.app_context.push()
        
        # Yield control to the test
        yield
        
        # Clean up after test is done
        self.requests_post_patch.stop()
        
        # Clean up the database within the app context
        with app.app_context():
            with real_get_db() as db:
                db.query(Project).delete()
                db.commit()
        
        # Pop the app context
        self.app_context.pop()
    
    def make_request(self, method, url, **kwargs):
        """Helper method to make requests with proper context."""
        with self.app.test_request_context():
            with self.app.app_context():
                return getattr(self.client, method.lower())(url, **kwargs)

    def test_create_project_success(self):
        """Test successful project creation."""
        # Test data with project type from enum
        data = {
            'project_name': 'New Project',
            'project_description': 'A new test project',
            'project_type': ProjectType.sample_pack.value  # Use enum value
        }

        # Mock the get_db function to return our test database session
        with patch('src.database.utils.get_db') as mock_get_db:
            # Create a real database session for testing
            with real_get_db() as db:
                mock_get_db.return_value = db
                
                # Make the request using our helper
                response = self.make_request(
                    'post',
                    '/ui/projects/create',
                    data=data,
                    follow_redirects=True
                )

        # Assertions
        assert response.status_code == 200
        # Verify we're on the dashboard page for the new project
        assert b'<title>Dashboard - Test Project' in response.data
        self.mock_post.assert_called_once()
        
        # Verify the project name is in the dashboard
        assert b'Test Project' in response.data

    def test_create_project_missing_name(self):
        """Test project creation with missing project name."""
        # Test data with missing project name
        data = {
            'project_name': '',
            'project_description': 'A test project with no name'
        }

        # Mock the get_db function to return our test database session
        with patch('src.database.utils.get_db') as mock_get_db:
            # Create a real database session for testing
            with real_get_db() as db:
                mock_get_db.return_value = db
                
                # Make the request using our helper
                response = self.make_request(
                    'post',
                    '/ui/projects/create',
                    data=data,
                    follow_redirects=True
                )

        # Assertions
        assert response.status_code == 200
        assert b'Project name is required' in response.data or b'This field is required' in response.data

    def test_create_project_api_error(self):
        """Test project creation when the API returns an error."""
        # Mock an API error response
        self.mock_response.status_code = 400
        self.mock_response.json.return_value = {'error': 'Project with this name already exists'}
        
        # Create a requests exception with the mock response
        from requests.exceptions import HTTPError
        http_error = HTTPError("Bad Request")
        http_error.response = self.mock_response
        self.mock_response.raise_for_status.side_effect = http_error
        
        # Test data
        data = {
            'project_name': 'Duplicate Project',
            'project_description': 'A duplicate project'
        }

        # Get the real database session
        from src.database.utils import get_db as real_get_db
        
        # Mock the get_db function to return our test database session
        with patch('src.database.utils.get_db') as mock_get_db:
            # Create a real database session for testing
            with real_get_db() as db:
                mock_get_db.return_value = db
                
                # Make the request using our helper
                with captured_templates(self.app) as templates:
                    response = self.make_request(
                        'post',
                        '/ui/projects/create',
                        data=data,
                        follow_redirects=True
                    )

        # Assertions
        assert response.status_code == 200
        assert b'Project with this name already exists' in response.data or b'Error creating project' in response.data
        
        # Verify we were redirected back to the create project form
        assert len(templates) == 1
        assert templates[0][0].name == 'create_project.html'
        assert b'Create New Project' in response.data

    def test_create_project_network_error(self):
        """Test project creation when there's a network error."""
        # Test data
        data = {
            'project_name': 'Network Error Project',
            'project_description': 'This should fail with a network error'
        }

        # Mock the API to raise a connection error
        self.mock_post.side_effect = requests.exceptions.ConnectionError("Network Error")
        
        # Mock the get_db function to return our test database session
        with patch('src.database.utils.get_db') as mock_get_db:
            # Create a real database session for testing
            with real_get_db() as db:
                mock_get_db.return_value = db
                
                # Make the request using our helper
                with captured_templates(self.app) as templates:
                    response = self.make_request(
                        'post',
                        '/ui/projects/create',
                        data=data,
                        follow_redirects=True
                    )

        # Assertions
        assert response.status_code == 200
        assert b'Failed to create project' in response.data or b'Error creating project' in response.data
        assert len(templates) == 1
        assert templates[0][0].name == 'create_project.html'
        assert b'Create New Project' in response.data
