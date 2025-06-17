import pytest
import json
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session as SQLAlchemySession
from sqlalchemy.engine import Engine

from src.app import create_app
from src.database.utils import init_db as initialize_db_utils, get_engine, get_session_local
from src.database.models import Base, Project as ProjectModel, Recording as RecordingModel, Sample as SampleModel, SampleMapping, SampleMappingItem

from typing import Generator


# --- Test Fixtures ---
@pytest.fixture(scope="module")
def app() -> Generator[Flask, None, None]:
    flask_app: Flask = create_app()
    flask_app.config.update(
        {
            "TESTING": True,
            "DATABASE_URL": "sqlite:///:memory:",
            "SQLALCHEMY_ECHO": False, # Reduce noise during tests
        }
    )
    engine: Engine = get_engine(flask_app.config["DATABASE_URL"])
    flask_app.config["TEST_ENGINE_INSTANCE"] = engine

    with flask_app.app_context():
        initialize_db_utils(engine_instance=engine)
    yield flask_app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture(autouse=True)
def manage_database_session(app: Flask) -> Generator[SQLAlchemySession, None, None]:
    with app.app_context():
        engine: Engine = app.config["TEST_ENGINE_INSTANCE"]
        SessionLocal = get_session_local(engine_instance=engine)
        db: SQLAlchemySession = SessionLocal()

        try:
            # Clear data from tables before each test
            for table in reversed(Base.metadata.sorted_tables):
                db.execute(table.delete())
            db.commit()
            yield db # Provide the session to the test if needed, though client calls are preferred for API tests
        except Exception as e:
            db.rollback()
            app.logger.error(f"Error in manage_database_session: {e}")
            raise
        finally:
            db.close()


@pytest.fixture
def test_project(manage_database_session: SQLAlchemySession) -> ProjectModel:
    db = manage_database_session
    project = ProjectModel(name="Test Project for Mappings", description="A project to test sample mappings")
    db.add(project)
    db.commit()
    db.refresh(project)
    return project

@pytest.fixture
def test_recording(manage_database_session: SQLAlchemySession, test_project: ProjectModel) -> RecordingModel:
    db = manage_database_session
    recording = RecordingModel(project_id=test_project.id, name="Test Recording", file_path="/fake/path.wav", status="processed")
    db.add(recording)
    db.commit()
    db.refresh(recording)
    return recording

@pytest.fixture
def test_sample(manage_database_session: SQLAlchemySession, test_recording: RecordingModel) -> SampleModel:
    db = manage_database_session
    sample = SampleModel(
        project_id=test_recording.project_id,
        recording_id=test_recording.id,
        name="Test Sample 1",
        file_path="/fake/sample1.wav",
        duration_ms=1000,
        metadata_json='{"key": "C4"}'
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample

@pytest.fixture
def test_sample2(manage_database_session: SQLAlchemySession, test_recording: RecordingModel) -> SampleModel:
    db = manage_database_session
    sample = SampleModel(
        project_id=test_recording.project_id,
        recording_id=test_recording.id,
        name="Test Sample 2",
        file_path="/fake/sample2.wav",
        duration_ms=1500,
        metadata_json='{"key": "D4"}'
    )
    db.add(sample)
    db.commit()
    db.refresh(sample)
    return sample


# --- SampleMapping Route Tests ---

def test_create_sample_mapping_success(client: FlaskClient, test_project: ProjectModel):
    response = client.post(
        f"/projects/{test_project.id}/sample_mappings",
        json={"name": "My Kick Drum Map", "mapping_type": "drum_kit"}
    )
    assert response.status_code == 201
    data = response.get_json()
    assert "id" in data
    assert data["name"] == "My Kick Drum Map"
    assert data["mapping_type"] == "drum_kit"
    assert data["project_id"] == test_project.id

def test_create_sample_mapping_missing_name(client: FlaskClient, test_project: ProjectModel):
    response = client.post(f"/projects/{test_project.id}/sample_mappings", json={})
    assert response.status_code == 400
    data = response.get_json()
    assert "error" in data
    assert "Sample mapping name is required" in data["error"]

def test_create_sample_mapping_invalid_project(client: FlaskClient):
    response = client.post("/projects/9999/sample_mappings", json={"name": "Test Map"})
    assert response.status_code == 404 # Project not found

def test_list_sample_mappings(client: FlaskClient, test_project: ProjectModel, manage_database_session: SQLAlchemySession):
    db = manage_database_session
    mapping1 = SampleMapping(project_id=test_project.id, name="Map Alpha")
    mapping2 = SampleMapping(project_id=test_project.id, name="Map Beta", mapping_type="chromatic")
    db.add_all([mapping1, mapping2])
    db.commit()

    response = client.get(f"/projects/{test_project.id}/sample_mappings")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    names = sorted([m["name"] for m in data])
    assert names == ["Map Alpha", "Map Beta"]

def test_list_sample_mappings_for_invalid_project(client: FlaskClient):
    response = client.get("/projects/9999/sample_mappings")
    assert response.status_code == 404

def test_get_sample_mapping_success(client: FlaskClient, test_project: ProjectModel, manage_database_session: SQLAlchemySession):
    db = manage_database_session
    mapping = SampleMapping(project_id=test_project.id, name="Specific Map")
    db.add(mapping)
    db.commit()

    response = client.get(f"/sample_mappings/{mapping.id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == mapping.id
    assert data["name"] == "Specific Map"

def test_get_sample_mapping_not_found(client: FlaskClient):
    response = client.get("/sample_mappings/8888")
    assert response.status_code == 404

def test_update_sample_mapping_success(client: FlaskClient, test_project: ProjectModel, manage_database_session: SQLAlchemySession):
    db = manage_database_session
    mapping = SampleMapping(project_id=test_project.id, name="Old Name")
    db.add(mapping)
    db.commit()

    response = client.put(
        f"/sample_mappings/{mapping.id}",
        json={"name": "New Updated Name", "mapping_type": "experimental"}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["name"] == "New Updated Name"
    assert data["mapping_type"] == "experimental"

    db.refresh(mapping)
    assert mapping.name == "New Updated Name"

def test_update_sample_mapping_not_found(client: FlaskClient):
    response = client.put("/sample_mappings/8888", json={"name": "New Name"})
    assert response.status_code == 404

def test_delete_sample_mapping_success(client: FlaskClient, test_project: ProjectModel, manage_database_session: SQLAlchemySession):
    db = manage_database_session
    mapping = SampleMapping(project_id=test_project.id, name="To Be Deleted")
    db.add(mapping)
    db.commit()
    mapping_id = mapping.id

    response = client.delete(f"/sample_mappings/{mapping_id}")
    assert response.status_code == 200 # Or 204 if no content returned

    deleted_mapping = db.query(SampleMapping).filter(SampleMapping.id == mapping_id).first()
    assert deleted_mapping is None

def test_delete_sample_mapping_not_found(client: FlaskClient):
    response = client.delete("/sample_mappings/8888")
    assert response.status_code == 404


# --- SampleMappingItem Route Tests ---

@pytest.fixture
def test_sample_mapping(manage_database_session: SQLAlchemySession, test_project: ProjectModel) -> SampleMapping:
    db = manage_database_session
    mapping = SampleMapping(project_id=test_project.id, name="Mapping For Items")
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping

def test_add_sample_mapping_item_success(client: FlaskClient, test_sample_mapping: SampleMapping, test_sample: SampleModel):
    response = client.post(
        f"/sample_mappings/{test_sample_mapping.id}/items",
        json={
            "sample_id": test_sample.id,
            "key_range_start": 60, "key_range_end": 60,
            "velocity_range_start": 100, "velocity_range_end": 127
        }
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["sample_id"] == test_sample.id
    assert data["key_range_start"] == 60
    assert data["sample_mapping_id"] == test_sample_mapping.id

def test_add_sample_mapping_item_mapping_not_found(client: FlaskClient, test_sample: SampleModel):
    response = client.post(
        "/sample_mappings/7777/items",
        json={"sample_id": test_sample.id, "key_range_start": 60}
    )
    assert response.status_code == 404

def test_add_sample_mapping_item_sample_not_found(client: FlaskClient, test_sample_mapping: SampleMapping):
    response = client.post(
        f"/sample_mappings/{test_sample_mapping.id}/items",
        json={"sample_id": 9998, "key_range_start": 60} # Non-existent sample
    )
    assert response.status_code == 404 # Sample not found

def test_add_sample_mapping_item_sample_wrong_project(
    client: FlaskClient,
    test_sample_mapping: SampleMapping,
    manage_database_session: SQLAlchemySession
):
    db = manage_database_session
    # Create another project and a sample in it
    other_project = ProjectModel(name="Other Project")
    db.add(other_project)
    db.commit()
    other_sample = SampleModel(project_id=other_project.id, name="Other Sample", file_path="/s.wav")
    db.add(other_sample)
    db.commit()

    response = client.post(
        f"/sample_mappings/{test_sample_mapping.id}/items",
        json={"sample_id": other_sample.id, "key_range_start": 60}
    )
    assert response.status_code == 400 # Validation error for project mismatch
    data = response.get_json()
    assert "Sample must belong to the same project" in data["error"]


def test_list_sample_mapping_items(client: FlaskClient, test_sample_mapping: SampleMapping, test_sample: SampleModel, test_sample2: SampleModel, manage_database_session: SQLAlchemySession):
    db = manage_database_session
    item1 = SampleMappingItem(sample_mapping_id=test_sample_mapping.id, sample_id=test_sample.id, key_range_start=60)
    item2 = SampleMappingItem(sample_mapping_id=test_sample_mapping.id, sample_id=test_sample2.id, key_range_start=62)
    db.add_all([item1, item2])
    db.commit()

    response = client.get(f"/sample_mappings/{test_sample_mapping.id}/items")
    assert response.status_code == 200
    data = response.get_json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert {item["sample_id"] for item in data} == {test_sample.id, test_sample2.id}

def test_list_sample_mapping_items_mapping_not_found(client: FlaskClient):
    response = client.get("/sample_mappings/7777/items")
    assert response.status_code == 404


@pytest.fixture
def test_sample_mapping_item(manage_database_session: SQLAlchemySession, test_sample_mapping: SampleMapping, test_sample: SampleModel) -> SampleMappingItem:
    db = manage_database_session
    item = SampleMappingItem(
        sample_mapping_id=test_sample_mapping.id,
        sample_id=test_sample.id,
        key_range_start=60, key_range_end=62,
        velocity_range_start=80, velocity_range_end=90
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

def test_get_sample_mapping_item_success(client: FlaskClient, test_sample_mapping_item: SampleMappingItem):
    response = client.get(f"/sample_mapping_items/{test_sample_mapping_item.id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == test_sample_mapping_item.id
    assert data["key_range_start"] == 60
    assert data["velocity_range_end"] == 90

def test_get_sample_mapping_item_not_found(client: FlaskClient):
    response = client.get("/sample_mapping_items/6666")
    assert response.status_code == 404

def test_update_sample_mapping_item_success(client: FlaskClient, test_sample_mapping_item: SampleMappingItem, manage_database_session: SQLAlchemySession):
    db = manage_database_session
    item_id = test_sample_mapping_item.id
    response = client.put(
        f"/sample_mapping_items/{item_id}",
        json={"key_range_end": 65, "velocity_range_start": 70}
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["key_range_end"] == 65
    assert data["velocity_range_start"] == 70

    db.refresh(test_sample_mapping_item)
    assert test_sample_mapping_item.key_range_end == 65
    assert test_sample_mapping_item.velocity_range_start == 70


def test_update_sample_mapping_item_not_found(client: FlaskClient):
    response = client.put("/sample_mapping_items/6666", json={"key_range_end": 65})
    assert response.status_code == 404


def test_delete_sample_mapping_item_success(client: FlaskClient, test_sample_mapping_item: SampleMappingItem, manage_database_session: SQLAlchemySession):
    db = manage_database_session
    item_id = test_sample_mapping_item.id

    response = client.delete(f"/sample_mapping_items/{item_id}")
    assert response.status_code == 200 # Or 204

    deleted_item = db.query(SampleMappingItem).filter(SampleMappingItem.id == item_id).first()
    assert deleted_item is None

def test_delete_sample_mapping_item_not_found(client: FlaskClient):
    response = client.delete("/sample_mapping_items/6666")
    assert response.status_code == 404
