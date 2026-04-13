"""
Integration tests for Construction Kit UI routes and manifest fulfillment.
"""
import pytest
import json
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session as SQLAlchemySession
from unittest.mock import MagicMock, patch

from src.app import create_app
from src.database import utils
from src.database.utils import init_db as initialize_db_utils
from src.database.models import (
    Base, 
    ProjectModel, 
    ConstructionKitProjectModel, 
    ProjectType, 
    RecordingModel, 
    SampleModel, 
    ManifestModel, 
    ManifestRuleModel,
    LoopRenderingConfigModel
)

from typing import Generator

# Mock hardware-dependent services at the module level to avoid import errors
import sys
sys.modules['amanuensis'] = MagicMock()
sys.modules['amanuensis.services'] = MagicMock()
sys.modules['amanuensis.services.render_service'] = MagicMock()
sys.modules['amanuensis.services.export_service'] = MagicMock()
sys.modules['amanuensis.ir'] = MagicMock()
sys.modules['pyaudio'] = MagicMock()
sys.modules['patchlab'] = MagicMock()
sys.modules['patchlab.service'] = MagicMock()

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
            "SAMPLES_BASE_DIR": "/tmp/test_samples"
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
def create_construction_kit_project(db_session: SQLAlchemySession, name: str = "Test Kit") -> ConstructionKitProjectModel:
    """Creates a construction kit project for testing."""
    project = ConstructionKitProjectModel(
        name=name,
        project_type=ProjectType.CONSTRUCTION_KIT.value
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


# --- UI Route Tests ---

def test_manifest_builder_page_loads(client: FlaskClient, db_session: SQLAlchemySession):
    """Test that the manifest builder page loads correctly for a construction kit."""
    project = create_construction_kit_project(db_session)
    response = client.get(f"/ui/projects/{project.id}/manifest/builder")
    assert response.status_code == 200
    assert "Manifest Builder" in response.data.decode("utf-8")
    assert project.name in response.data.decode("utf-8")

def test_save_manifest_rules(client: FlaskClient, db_session: SQLAlchemySession):
    """Test saving rules in the manifest builder."""
    project = create_construction_kit_project(db_session)
    
    rules = [
        {
            "name": "Song 1 - Verse - Bass",
            "category": "Bass",
            "target_count": 1,
            "required_tags": {"song": "Song 1", "section": "Verse", "instrument": "bass"}
        }
    ]
    
    response = client.post(
        f"/ui/projects/{project.id}/manifest/builder",
        data={"rules_json": json.dumps(rules)},
        follow_redirects=True
    )
    
    assert response.status_code == 200
    assert "Manifest rules updated successfully!" in response.data.decode("utf-8")
    
    # Verify DB state
    manifest = db_session.query(ManifestModel).filter(ManifestModel.project_id == project.id).first()
    assert manifest is not None
    assert len(manifest.rules) == 1
    assert manifest.rules[0].name == "Song 1 - Verse - Bass"
    assert manifest.rules[0].required_tags == {"song": "Song 1", "section": "Verse", "instrument": "bass"}

def test_manifest_status_fulfillment_matching(client: FlaskClient, db_session: SQLAlchemySession):
    """Test that assets are correctly matched against manifest rules in the status view."""
    # 1. Create project and manifest
    project = create_construction_kit_project(db_session)
    manifest = ManifestModel(project_id=project.id)
    db_session.add(manifest)
    
    rule = ManifestRuleModel(
        manifest=manifest,
        name="Bass Verse",
        category="Bass",
        target_count=1,
        required_tags_json=json.dumps({"instrument": "bass", "section": "verse"})
    )
    db_session.add(rule)
    db_session.commit()
    
    # 2. Add a matching sample
    recording = RecordingModel(project_id=project.id, name="Rec 1", file_path="/tmp/rec1.wav")
    db_session.add(recording)
    db_session.commit()
    
    sample = SampleModel(
        recording_id=recording.id,
        name="Bass Loop 1",
        file_path="/tmp/bass1.wav",
        metadata_json=json.dumps({"instrument": "bass", "section": "verse", "song": "Song 1"})
    )
    db_session.add(sample)
    db_session.commit()
    
    # 3. Check status page
    response = client.get(f"/ui/projects/{project.id}/manifest/status")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Bass Verse" in html
    assert "1 / 1" in html # Fulfillment progress
    assert "Bass Loop 1" in html # Matched asset name

def test_fulfill_rule_action(client: FlaskClient, db_session: SQLAlchemySession):
    """Test triggering fulfillment of a rule."""
    project = create_construction_kit_project(db_session)
    manifest = ManifestModel(project_id=project.id)
    db_session.add(manifest)
    rule = ManifestRuleModel(manifest=manifest, name="Test Rule", required_tags_json="{}", target_count=1)
    db_session.add(rule)
    
    config = LoopRenderingConfigModel(name="Default Render", midi_port="Test Port")
    db_session.add(config)
    db_session.commit()
    
    with patch("src.ui.manifest_routes.LoopOrchestrator") as mock_orch_class:
        mock_orch = MagicMock()
        mock_orch_class.return_value = mock_orch
        mock_orch.fulfill_manifest_rule.return_value = [{"sample_id": 123}]
        
        response = client.post(
            f"/ui/projects/{project.id}/manifest/fulfill/{rule.id}",
            data={"render_config_id": config.id},
            follow_redirects=True
        )
        
        assert response.status_code == 200
        assert "Successfully generated 1 assets" in response.data.decode("utf-8")
        mock_orch.fulfill_manifest_rule.assert_called_once()

def test_export_kit_action(client: FlaskClient, db_session: SQLAlchemySession):
    """Test triggering construction kit export."""
    project = create_construction_kit_project(db_session)
    
    with patch("src.ui.manifest_routes.ConstructionKitExporter") as mock_exporter_class:
        mock_exporter = MagicMock()
        mock_exporter_class.return_value = mock_exporter
        mock_exporter.export_kit.return_value = "/tmp/test_kit.zip"
        
        # We need a dummy zip file for send_file to work or mock send_file
        with patch("src.ui.manifest_routes.send_file") as mock_send_file:
            mock_send_file.return_value = "file_sent"
            
            response = client.post(f"/ui/projects/{project.id}/manifest/export")
            
            assert response.status_code == 200
            assert response.data.decode("utf-8") == "file_sent"
            mock_exporter.export_kit.assert_called_once()
