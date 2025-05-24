# pylint: disable=too-many-lines
"""
Unit tests for the SQLAlchemy database models.

This module tests the creation, updating, deletion, and relationships
of the Project, Recording, Sample, SampleMapping, and SampleMappingItem models.
It uses an in-memory SQLite database for isolated testing.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session # sessionmaker removed as it's not directly used here
# Import all models for testing
from src.database.models import (
    Base, Project, Recording, Sample, SampleMapping, SampleMappingItem
)
from src.database.utils import init_db as initialize_db_utils
from src.database.utils import get_db # Renamed get_db_utils to get_db

# --- Test Database Fixtures ---
@pytest.fixture(scope="function")
def test_engine():
    """
    Creates an in-memory SQLite engine for function-scoped tests.
    Initializes the database schema using this engine.
    """
    engine = create_engine("sqlite:///:memory:")
    initialize_db_utils(engine_instance=engine) # Uses the new module-level ENGINE if not passed
    return engine

@pytest.fixture(scope="function")
def db_session(test_engine) -> Session: # Type hint for clarity
    """
    Provides a SQLAlchemy session for function-scoped tests, ensuring it's
    closed after the test. Uses the `test_engine` fixture.
    Correctly handles the `get_db` generator.
    """
    session_generator = get_db(engine_instance=test_engine)
    session_instance: Session = next(session_generator)
    try:
        yield session_instance
    finally:
        # The get_db generator is responsible for closing the session.
        # Exhausting the generator ensures its finally block is executed.
        next(session_generator, None)

# --- Helper Fixtures for Model Creation (to reduce duplicate code) ---

@pytest.fixture
def created_project(db_session: Session) -> Project:
    """
    Creates a sample Project instance, commits it to the database,
    and returns the refreshed instance.
    """
    project = Project(name="Test Project Fixture", description="A project created by a fixture.")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project

@pytest.fixture
def created_recording(db_session: Session, created_project: Project) -> Recording:
    """
    Creates a sample Recording instance, linked to `created_project`,
    commits it, and returns the refreshed instance.
    """
    recording = Recording(
        project_id=created_project.id,
        name="Test Recording Fixture",
        file_path="/fixture/path/recording.wav",
        duration_seconds=180.0,
        samplerate=48000,
        channels=2,
        status="processed"
    )
    db_session.add(recording)
    db_session.commit()
    db_session.refresh(recording)
    return recording

@pytest.fixture
def created_sample(db_session: Session, created_recording: Recording) -> Sample:
    """
    Creates a sample Sample instance, linked to `created_recording`,
    commits it, and returns the refreshed instance.
    """
    sample = Sample(
        recording_id=created_recording.id,
        name="Test Sample Fixture",
        file_path="/fixture/path/sample.wav", # Ensure unique file_path if constraint exists
        start_time_seconds=5.0,
        end_time_seconds=10.0,
        sample_type="loop",
        midi_pitch=64,
        metadata_json='{"fixture_key": "fixture_value"}'
    )
    db_session.add(sample)
    db_session.commit()
    db_session.refresh(sample)
    return sample

# --- Model Tests ---

# Project Model Tests
def test_create_project(db_session: Session):
    """Test creating and persisting a Project model instance."""
    project = Project(name="Test Project", description="A test description")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    assert project.id is not None
    assert project.name == "Test Project"
    assert project.description == "A test description"
    assert project.created_at is not None, "created_at should be set by server_default"
    assert project.updated_at is not None, "updated_at should be set by server_default"

    retrieved_project = db_session.query(Project).filter(Project.id == project.id).first()
    assert retrieved_project is not None
    assert retrieved_project.name == "Test Project"

def test_update_project(created_project: Project, db_session: Session):
    """Test updating attributes of an existing Project model instance."""
    project = created_project # Use the fixture

    project.name = "Updated Project Name"
    project.description = "Now with a description"
    # Note: updated_at should auto-update if `onupdate=func.now()` is working
    original_updated_at = project.updated_at 
    db_session.commit()
    db_session.refresh(project)

    updated_project = db_session.query(Project).filter(Project.id == project.id).first()
    assert updated_project is not None, "Updated project should still exist."
    assert updated_project.name == "Updated Project Name"
    assert updated_project.description == "Now with a description"
    # This assertion might be tricky due to microseconds precision differences.
    # Consider checking if it's greater than original_updated_at.
    assert updated_project.updated_at > original_updated_at, \
        "updated_at should change on update."


def test_delete_project(created_project: Project, db_session: Session):
    """Test deleting a Project model instance from the database."""
    project = created_project
    project_id = project.id # Get ID before deletion

    db_session.delete(project)
    db_session.commit()

    deleted_project = db_session.query(Project).filter(Project.id == project_id).first()
    assert deleted_project is None, "Project should be deleted from the database."

# Recording Model Tests
def test_create_recording(db_session: Session, created_project: Project):
    """Test creating and persisting a Recording model instance."""
    project = created_project

    recording = Recording(
        project_id=project.id,
        name="Test Recording",
        file_path="/path/to/recording.wav",
        duration_seconds=120.5,
        samplerate=44100,
        channels=2,
        status="pending",
    )
    db_session.add(recording)
    db_session.commit()
    db_session.refresh(recording)

    assert recording.id is not None
    assert recording.project_id == project.id
    assert recording.name == "Test Recording"
    assert recording.file_path == "/path/to/recording.wav"
    assert recording.status == "pending"
    assert recording.project is not None, "Recording should have a project relationship."
    assert recording.project.name == project.name # Test relationship back to project

def test_update_recording_status(created_recording: Recording, db_session: Session):
    """Test updating the status of an existing Recording model instance."""
    recording = created_recording # Use the fixture

    recording.status = "processed"
    db_session.commit()
    db_session.refresh(recording)
    
    updated_recording = db_session.query(Recording).filter(Recording.id == recording.id).first()
    assert updated_recording is not None, "Updated recording should exist."
    assert updated_recording.status == "processed"

# Sample Model Tests
def test_create_sample(db_session: Session, created_recording: Recording):
    """Test creating and persisting a Sample model instance."""
    recording = created_recording

    sample = Sample(
        recording_id=recording.id,
        name="Test Sample",
        file_path="/path/to/sample.wav",
        start_time_seconds=10.0,
        end_time_seconds=15.5,
        sample_type="one-shot",
        midi_pitch=60,
        metadata_json='{"key": "value"}',
    )
    db_session.add(sample)
    db_session.commit()
    db_session.refresh(sample)

    assert sample.id is not None
    assert sample.recording_id == recording.id
    assert sample.name == "Test Sample"
    assert sample.start_time_seconds == 10.0
    assert sample.midi_pitch == 60
    assert sample.recording is not None, "Sample should have a recording relationship."
    assert sample.recording.name == recording.name # Test relationship

# Relationship Tests
def test_project_has_multiple_recordings(created_project: Project, db_session: Session):
    """Test the one-to-many relationship from Project to Recording."""
    project = created_project

    rec1 = Recording(project_id=project.id, name="Rec 1", file_path="r1.wav")
    rec2 = Recording(project_id=project.id, name="Rec 2", file_path="r2.wav")
    db_session.add_all([rec1, rec2])
    db_session.commit()

    retrieved_project = db_session.query(Project).filter(Project.id == project.id).first()
    assert retrieved_project is not None
    assert len(retrieved_project.recordings) == 2
    # Sort by name for consistent assertion order
    retrieved_recording_names = sorted([r.name for r in retrieved_project.recordings])
    assert retrieved_recording_names == ["Rec 1", "Rec 2"]

def test_recording_has_multiple_samples(created_recording: Recording, db_session: Session):
    """Test the one-to-many relationship from Recording to Sample."""
    recording = created_recording

    sample1 = Sample(
        recording_id=recording.id, name="Sample A", file_path="s_a.wav",
        start_time_seconds=1.0, end_time_seconds=2.0
    )
    sample2 = Sample(
        recording_id=recording.id, name="Sample B", file_path="s_b.wav",
        start_time_seconds=3.0, end_time_seconds=4.0
    )
    db_session.add_all([sample1, sample2])
    db_session.commit()

    retrieved_recording = db_session.query(Recording).filter(Recording.id == recording.id).first()
    assert retrieved_recording is not None
    assert len(retrieved_recording.samples) == 2
    retrieved_sample_names = sorted([s.name for s in retrieved_recording.samples])
    assert retrieved_sample_names == ["Sample A", "Sample B"]

# SampleMapping and SampleMappingItem Model Tests (Basic)
def test_create_sample_mapping(created_project: Project, db_session: Session):
    """Test creating and persisting a SampleMapping model instance."""
    project = created_project

    sample_mapping = SampleMapping(
        project_id=project.id,
        name="Drum Kit Map",
        mapping_type="drum_kit_pad",
    )
    db_session.add(sample_mapping)
    db_session.commit()
    db_session.refresh(sample_mapping)

    assert sample_mapping.id is not None
    assert sample_mapping.project_id == project.id
    assert sample_mapping.name == "Drum Kit Map"
    assert sample_mapping.project is not None
    assert sample_mapping.project.name == project.name

def test_create_sample_mapping_item(
    db_session: Session, created_project: Project, created_recording: Recording # Use existing fixtures
):
    """Test creating and persisting a SampleMappingItem model instance."""
    project = created_project
    recording = created_recording # Use recording from fixture, which is linked to created_project

    # Create a sample linked to the created_recording
    sample = Sample(
        recording_id=recording.id,
        name="Kick Sample for Mapping",
        file_path="kick_map.wav",
        start_time_seconds=0.1,
        end_time_seconds=0.5,
        midi_pitch=36,
    )
    db_session.add(sample)
    
    sample_mapping = SampleMapping(
        project_id=project.id,
        name="Drum Map For Item Test",
        mapping_type="drum_kit",
    )
    db_session.add(sample_mapping)
    db_session.commit()
    db_session.refresh(sample)
    db_session.refresh(sample_mapping)

    item = SampleMappingItem(
        sample_mapping_id=sample_mapping.id,
        sample_id=sample.id,
        key_range_start=36,
        key_range_end=36,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    assert item.id is not None
    assert item.sample_mapping_id == sample_mapping.id
    assert item.sample_id == sample.id
    assert item.key_range_start == 36
    assert item.sample is not None
    assert item.sample.name == "Kick Sample for Mapping"
    assert item.sample_mapping is not None
    assert item.sample_mapping.name == "Drum Map For Item Test"

def test_sample_mapping_has_multiple_items(
    db_session: Session, created_project: Project, created_recording: Recording
):
    """Test the one-to-many relationship from SampleMapping to SampleMappingItem."""
    project = created_project
    recording = created_recording

    sample1 = Sample(
        recording_id=recording.id,
        name="Snare For MultiMap",
        file_path="snare_mm.wav",
        start_time_seconds=0.1,
        end_time_seconds=0.4,
        midi_pitch=38,
    )
    sample2 = Sample(
        recording_id=recording.id,
        name="HiHat For MultiMap",
        file_path="hihat_mm.wav",
        start_time_seconds=0.5,
        end_time_seconds=0.7,
        midi_pitch=42,
    )
    db_session.add_all([sample1, sample2])
    
    sample_mapping = SampleMapping(
        project_id=project.id,
        name="Drum Map Multi Item Test",
        mapping_type="drum_kit",
    )
    db_session.add(sample_mapping)
    db_session.commit()
    db_session.refresh(sample1)
    db_session.refresh(sample2)
    db_session.refresh(sample_mapping)

    item1 = SampleMappingItem(
        sample_mapping_id=sample_mapping.id,
        sample_id=sample1.id,
        key_range_start=38,
        key_range_end=38,
    )
    item2 = SampleMappingItem(
        sample_mapping_id=sample_mapping.id,
        sample_id=sample2.id,
        key_range_start=42,
        key_range_end=42,
    )
    db_session.add_all([item1, item2])
    db_session.commit()

    retrieved_mapping = db_session.query(SampleMapping).filter(
        SampleMapping.id == sample_mapping.id
    ).first()
    assert retrieved_mapping is not None
    assert len(retrieved_mapping.sample_mapping_items) == 2
    
    item_sample_names = sorted([item.sample.name for item in retrieved_mapping.sample_mapping_items])
    assert "HiHat For MultiMap" in item_sample_names
    assert "Snare For MultiMap" in item_sample_names
