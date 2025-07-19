"""Tests for project-related endpoints in the sample orchestrator application."""

import os
import tempfile
import pytest
from datetime import datetime, UTC
import requests
from unittest.mock import patch, MagicMock, ANY, create_autospec
from flask import url_for, template_rendered
from contextlib import contextmanager

# Import the app factory and database utilities
from src.app import create_app
from src.database.models import Project, Recording, ProjectType
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
def test_project(app):
    """Create a test project and clean it up after the test.
    
    Yields:
        tuple: (project, project_dict) where project is the ORM object (for DB ops) and project_dict is a dict for UI/template context.
    """
    with app.app_context():
        with real_get_db() as db:
            project = Project(
                name="Test Project",
                project_type=ProjectType.SAMPLE_PACK.value,  # Use the enum value directly
                description="A test project",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            db.add(project)
            db.commit()
            db.refresh(project)
            
            # Create a dictionary with the project data we'll need in tests
            project_data = {
                'id': project.id,
                'name': project.name,
                'description': project.description,
                'project_type': project.project_type,
                'created_at': project.created_at,
                'updated_at': project.updated_at
            }
            
    # Yield both the ORM object and the dict
    yield project, project_data
    
    # Clean up in a new session
    with app.app_context():
        with real_get_db() as db:
            # Re-query the project to ensure it's in the current session
            project = db.query(Project).get(project_data['id'])
            if project:
                db.delete(project)
                db.commit()

class TestProjectListAndDetails:
    """Test cases for project listing and detail views."""
    
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
        
        # Push application context
        self.app_context = app.app_context()
        self.app_context.push()
        
        # Create a new database session for the test
        self.db_session = real_get_db().__enter__()
        
        # Ensure any previous transactions are rolled back
        self.db_session.rollback()
        
        # Yield control to the test
        yield
        
        # Clean up after test is done
        try:
            # Rollback any uncommitted changes
            self.db_session.rollback()
            # Close the session
            self.db_session.close()
        except Exception as e:
            logger.error(f"Error during test teardown: {e}")
            raise
        finally:
            # Make sure to stop patches and pop context even if there's an error
            self.requests_get_patch.stop()
            self.app_context.pop()
    
    def test_dashboard_no_projects(self):
        """Test dashboard when no projects exist."""
        # Set up mock to return empty list
        self.mock_response.json.return_value = []
        
        with captured_templates(self.app) as templates:
            response = self.client.get('/ui/', follow_redirects=True)
            
        assert response.status_code == 200
        assert len(templates) == 1
        assert templates[0][0].name == 'dashboard.html'
        
        # Verify no projects are displayed
        template, context = templates[0]
        assert context['project'] is None
        
    def test_dashboard_with_projects(self, test_project):
        """Test dashboard when projects exist."""
        project, project_dict = test_project
        # Set up mock to return test project data
        self.mock_response.json.return_value = [{
            'id': project_dict['id'],
            'name': project_dict['name'],
            'description': project_dict['description'],
            'project_type': project_dict['project_type'],
            'created_at': project_dict['created_at'].isoformat(),
            'updated_at': project_dict['updated_at'].isoformat()
        }]
        
        with captured_templates(self.app) as templates:
            response = self.client.get('/ui/', follow_redirects=True)
            
        assert response.status_code == 200
        assert len(templates) == 1
        assert templates[0][0].name == 'dashboard.html'
        
        # Verify the project is displayed
        template, context = templates[0]
        assert context['project'] is not None
        assert context['project']['id'] == project_dict['id']
        assert context['project']['name'] == project_dict['name']
        
        # For testing purposes, we don't need to actually access the SQLAlchemy object's properties
        # Just verify that the projects list exists and contains items
        assert len(context['projects']) > 0
        
        # The dashboard route uses direct database queries, not API calls
        # So we should not expect any API calls here
        
    def test_project_detail_view(self, test_project):
        """Test project detail view."""
        project, project_dict = test_project
        # Set up mock to return test project data
        self.mock_response.json.return_value = {
            'id': project_dict['id'],
            'name': project_dict['name'],
            'description': project_dict['description'],
            'project_type': project_dict['project_type'],
            'created_at': project_dict['created_at'].isoformat(),
            'updated_at': project_dict['updated_at'].isoformat()
        }
        
        with captured_templates(self.app) as templates:
            response = self.client.get(f'/ui/projects/{project_dict["id"]}', follow_redirects=True)
            
        assert response.status_code == 200
        assert len(templates) == 1
        assert templates[0][0].name == 'project_detail.html'
        
        # Verify project data is passed to template
        template, context = templates[0]
        assert context['project'] is not None
        assert context['project']['id'] == project_dict['id']
        assert context['project']['name'] == project_dict['name']
        
    def test_project_with_invalid_id(self):
        """Test project detail view with invalid project ID."""
        # Mock API to return 404 for non-existent project
        error_response = MagicMock()
        error_response.status_code = 404
        error_response.json.return_value = {'error': 'Project not found'}

        # Create a requests exception
        http_error = requests.exceptions.HTTPError("Not Found")
        http_error.response = error_response
        error_response.raise_for_status.side_effect = http_error

        self.mock_get.return_value = error_response

        response = self.client.get('/ui/projects/999', follow_redirects=True)
        assert response.status_code == 200
                # UI contract: error banner in rendered HTML, not JSON
        assert 'project not found' in response.data.decode('utf-8').lower()
        # Optionally, check for the error banner or template name if using captured_templates
        
    def test_create_project_form(self):
        """Test project creation form."""
        with captured_templates(self.app) as templates:
            response = self.client.get('/ui/projects/new', follow_redirects=True)
            
        assert response.status_code == 200
        assert len(templates) == 1
        assert templates[0][0].name == 'create_project.html'
    
    def test_create_project_submit_success(self):
        """Test successful project creation form submission."""
        # Set up post patch
        with patch('src.ui.routes.requests.post') as mock_post:
            # Configure mock response
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {
                'id': 123,
                'name': 'New Test Project',
                'description': 'Test project description',
                'project_type': ProjectType.SAMPLE_PACK.value,
                'created_at': datetime.now(UTC).isoformat(),
                'updated_at': datetime.now(UTC).isoformat()
            }
            mock_post.return_value = mock_response
            
            # Submit form data
            form_data = {
                'project_name': 'New Test Project',
                'project_description': 'Test project description'
            }
            
            with captured_templates(self.app) as templates:
                response = self.client.post('/ui/projects/create', 
                                         data=form_data,
                                         follow_redirects=True)
            
            # Verify API was called correctly
            api_url = f"{self.app.config['API_BASE_URL'].rstrip('/')}/projects"
            mock_post.assert_called_once_with(
                api_url, 
                json={
                    'name': form_data['project_name'],
                    'description': form_data['project_description']
                }
            )
            
            # Should redirect to dashboard
            assert response.status_code == 200
            assert len(templates) == 1
            assert templates[0][0].name == 'dashboard.html'
            
            # Check that the flash message is in the response
            assert b'Project &#39;New Test Project&#39; created successfully!' in response.data
            
            # Check session for flash messages
            with self.client.session_transaction() as session:
                print("\n=== Session Data ===")
                print(dict(session))
                print("===================\n")
            
            # Check flash message appears in response (using HTML-escaped single quote)
            assert b'Project &#39;New Test Project&#39; created successfully!' in response.data
    
    def test_create_project_submit_missing_name(self):
        """Test project creation with missing name."""
        with patch('src.ui.routes.requests.post') as mock_post:
            # Submit form with missing name
            form_data = {
                'project_name': '',  # Missing required field
                'project_description': 'Test project description'
            }
            
            with captured_templates(self.app) as templates:
                response = self.client.post('/ui/projects/create', 
                                         data=form_data,
                                         follow_redirects=True)
            
            # Should redirect back to form
            assert response.status_code == 200
            assert len(templates) == 1
            assert templates[0][0].name == 'create_project.html'
            
            # API should not be called
            mock_post.assert_not_called()
            
            # Check error message
            assert b'Project name is required' in response.data
    
    def test_create_project_submit_api_error(self):
        """Test project creation with API error."""
        with patch('src.ui.routes.requests.post') as mock_post:
            # Mock API error
            mock_post.side_effect = requests.exceptions.RequestException('API Error')
            
            # Submit form data
            form_data = {
                'project_name': 'New Test Project',
                'project_description': 'Test project description'
            }
            
            with captured_templates(self.app) as templates:
                response = self.client.post('/ui/projects/create', 
                                         data=form_data,
                                         follow_redirects=True)
            
            # Should redirect back to form
            assert response.status_code == 200
            assert len(templates) == 1
            assert templates[0][0].name == 'create_project.html'
            
            # Check error message
            assert b'Failed to create project' in response.data
            
    def test_import_project_audio_ui_success(self, test_project):
        """Test audio import UI page renders correctly."""
        project, project_dict = test_project
        # Set up mock to return test project data
        self.mock_response.json.return_value = {
            'id': project_dict['id'],
            'name': project_dict['name'],
            'description': project_dict['description'],
            'project_type': project_dict['project_type']
        }
        
        with captured_templates(self.app) as templates:
            response = self.client.get(f'/ui/projects/{project_dict["id"]}/import_audio',
                                     follow_redirects=True)
            
        assert response.status_code == 200
        assert len(templates) == 1
        assert templates[0][0].name == 'import_audio.html'
        
        # Verify project info is passed to template
        template, context = templates[0]
        assert context['project']['id'] == project_dict['id']
        assert context['project']['name'] == project_dict['name']
        assert 'error' not in context or context['error'] is None
        assert 'success_message' not in context or context['success_message'] is None
        
    def test_import_project_audio_ui_not_found(self):
        """Test audio import UI with invalid project ID."""
        with captured_templates(self.app) as templates:
            response = self.client.get('/ui/projects/9999/import_audio', follow_redirects=True)
        assert response.status_code == 200
        assert len(templates) == 1
        assert templates[0][0].name == 'import_audio.html'
        template, context = templates[0]
        assert 'error' in context and context['error'] is not None
        assert 'not found' in context['error'].lower()
        
    def test_process_recording_ui_success(self, test_project, client):
        """Test recording processing UI page renders correctly with valid IDs."""
        project, project_dict = test_project
        # Create a test recording in the database
        with real_get_db() as db:
            recording = Recording(
                project_id=project_dict['id'],
                file_path="/path/to/test_recording.wav",
                name="Test Recording",
                duration_seconds=120.5,
                sample_rate=44100,
                channels=2,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            db.add(recording)
            db.commit()
            db.refresh(recording)
            recording_id = recording.id
        
        # Use client to request the UI route
        with captured_templates(self.app) as templates:
            response = client.get(f'/ui/projects/{project_dict["id"]}/recordings/{recording_id}/process', follow_redirects=True)
        assert response.status_code == 200
        assert len(templates) == 1
        assert templates[0][0].name == 'process_recording.html'
        template, context = templates[0]
        assert isinstance(context['project'], dict)
        assert isinstance(context['recording'], dict)
        assert context['project']['id'] == project_dict['id']
        assert context['recording']['id'] == recording_id
        assert context['recording']['name'] == 'Test Recording'
        assert 'Select a Workflow' in response.data.decode('utf-8')
        assert 'Run Workflow' in response.data.decode('utf-8')
        # Clean up test recording
        try:
            with real_get_db() as db:
                db_recording = db.query(Recording).filter(Recording.id == recording_id).first()
                if db_recording:
                    db.delete(db_recording)
                    db.commit()
        except Exception as e:
            print(f"Error cleaning up test recording: {e}")
    
    def test_process_recording_ui_project_not_found(self):
        """Test recording processing UI with invalid project ID."""
        with captured_templates(self.app) as templates:
            response = self.client.get('/ui/projects/9999/recordings/1/process', follow_redirects=True)
        assert response.status_code == 200
        assert len(templates) == 1
        assert templates[0][0].name == 'process_recording.html'
        template, context = templates[0]
        assert 'error' in context and context['error'] is not None
        assert 'not found' in context['error'].lower()
    
    def test_process_recording_ui_recording_not_found(self, test_project):
        """Test recording processing UI with invalid recording ID."""
        project, project_dict = test_project
        with captured_templates(self.app) as templates:
            response = self.client.get(f'/ui/projects/{project_dict["id"]}/recordings/9999/process', follow_redirects=True)
        assert response.status_code == 200
        assert len(templates) == 1
        assert templates[0][0].name == 'process_recording.html'
        template, context = templates[0]
        assert 'error' in context and context['error'] is not None
        assert 'not found' in context['error'].lower()
        
    def test_process_recording_ui_recording_wrong_project(self, test_project, client):
        """Test recording processing UI with a recording that does not belong to the project."""
        project, project_dict = test_project
        # Create a second project and recording
        with real_get_db() as db:
            project2 = Project(
                name="Other Project",
                project_type=ProjectType.SAMPLE_PACK.value,
                description="Unrelated project",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            db.add(project2)
            db.commit()
            db.refresh(project2)
            recording = Recording(
                project_id=project2.id,
                file_path="/path/to/other_recording.wav",
                name="Other Recording",
                duration_seconds=60.0,
                sample_rate=44100,
                channels=2,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            db.add(recording)
            db.commit()
            db.refresh(recording)
            recording_id = recording.id
        
        with captured_templates(self.app) as templates:
            response = client.get(f'/ui/projects/{project_dict["id"]}/recordings/{recording_id}/process', follow_redirects=True)
        assert response.status_code == 200
        assert len(templates) == 1
        assert templates[0][0].name == 'process_recording.html'
        template, context = templates[0]
        assert 'error' in context and context['error'] is not None
        assert 'not found in project' in context['error'].lower()

    
    def test_process_recording_submit_api_error(self, test_project):
        """Test recording processing with API error."""
        project, project_dict = test_project
        # Create a test recording
        with real_get_db() as db:
            recording = Recording(
                project_id=project_dict['id'],
                file_path="/path/to/test_recording.wav",
                name="Test Recording",
                duration_seconds=120.5,
                sample_rate=44100,
                channels=2,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            db.add(recording)
            db.commit()
            recording_id = recording.id
        
        try:
            # Set up mock for API POST request
            with patch('src.ui.routes.requests.post') as mock_post:
                # Configure mock error response
                error_response = MagicMock()
                error_response.status_code = 500
                error_response.json.return_value = {
                    'error': 'Processing failed due to server error'
                }
                
                # Create a requests exception
                http_error = requests.exceptions.HTTPError("Internal Server Error")
                http_error.response = error_response
                error_response.raise_for_status.side_effect = http_error
                
                mock_post.return_value = error_response
                
                # Submit form data
                form_data = {
                    'workflow_name': 'standard_workflow',
                    'instrument_name': 'Piano',
                    'instrument_author': 'Test Author'
                }
                
                response = self.client.post(
                    f'/ui/projects/{project_dict["id"]}/recordings/{recording_id}/process',
                    data=form_data,
                    follow_redirects=True
                )
                
                # Error message should be shown
                assert b'error' in response.data.lower() or b'failed' in response.data.lower()
        finally:
            # Clean up test recording
            with real_get_db() as db:
                db_recording = db.query(Recording).filter(Recording.id == recording_id).first()
                if db_recording:
                    db.delete(db_recording)
                    db.commit()

        """Test recording processing with missing workflow name."""
        project, project_dict = test_project
        # Create a test recording
        with real_get_db() as db:
            recording = Recording(
                project_id=project_dict['id'],
                file_path="/path/to/test_recording.wav",
                name="Test Recording",
                duration_seconds=120.5,
                sample_rate=44100,
                channels=2,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )
            db.add(recording)
            db.commit()
            db.refresh(recording)
            recording_id = recording.id
        
        # Submit form data missing workflow_name
        form_data = {
            'instrument_name': 'Piano',
            'instrument_author': 'Test Author'
        }
        response = self.client.post(
            f'/ui/projects/{project_dict["id"]}/recordings/{recording_id}/process',
            data=form_data,
            follow_redirects=True
        )
        assert response.status_code == 200
        assert b'error' in response.data.lower()
        with real_get_db() as db:
            db_recording = db.query(Recording).filter(Recording.id == recording_id).first()
            if db_recording:
                db.delete(db_recording)
                db.commit()
                db_recording = db.query(Recording).get(recording_id)
                if db_recording:
                    db.delete(db_recording)
                    db.commit()
