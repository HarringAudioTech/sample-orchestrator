import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.database.models import (
    Base,
    Project,
    Recording,
    Sample,
    SampleMapping,
    SampleMappingItem,
)  # Import all models
from src.database.utils import init_db as initialize_db_utils, get_db as get_db_utils


# --- Test Database Fixtures ---
@pytest.fixture(
    scope="function"
)  # "function" scope ensures a fresh DB for each test function
def test_engine():
    """Creates an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    initialize_db_utils(engine_instance=engine)  # Use the modified init_db
    return engine


@pytest.fixture(scope="function")
def db_session(test_engine):
    """Creates a new database session for a test."""
    # get_db_utils is a generator, so we call next() on it.
    # We also need to pass the test_engine to our modified get_db_utils
    session_generator = get_db_utils(engine_instance=test_engine)
    session = next(session_generator)
    try:
        yield session
    finally:
        session.close()  # Ensure session is closed


# --- Model Tests ---


# Project Model Tests
def test_create_project(db_session: Session):
    project = Project(name="Test Project", description="A test description")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    assert project.id is not None
    assert project.name == "Test Project"
    assert project.description == "A test description"
    assert project.created_at is not None
    assert project.updated_at is not None

    retrieved_project = (
        db_session.query(Project).filter(Project.id == project.id).first()
    )
    assert retrieved_project is not None
    assert retrieved_project.name == "Test Project"


def test_update_project(db_session: Session):
    project = Project(name="Initial Project Name")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    project.name = "Updated Project Name"
    project.description = "Now with a description"
    db_session.commit()
    db_session.refresh(project)

    updated_project = db_session.query(Project).filter(
        Project.id == project.id).first()
    assert updated_project.name == "Updated Project Name"
    assert updated_project.description == "Now with a description"


def test_delete_project(db_session: Session):
    project = Project(name="To Be Deleted")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    project_id = project.id

    db_session.delete(project)
    db_session.commit()

    deleted_project = db_session.query(Project).filter(
        Project.id == project_id).first()
    assert deleted_project is None


# Recording Model Tests
def test_create_recording(db_session: Session):
    project = Project(name="Project For Recordings")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

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
    assert recording.project.name == "Project For Recordings"  # Test relationship


def test_update_recording_status(db_session: Session):
    project = Project(name="Project For Recording Update")
    db_session.add(project)
    db_session.commit()
    recording = Recording(
        project_id=project.id, name="Rec Status Test", file_path="test.wav"
    )
    db_session.add(recording)
    db_session.commit()
    db_session.refresh(recording)

    recording.status = "processed"
    db_session.commit()
    db_session.refresh(recording)

    updated_recording = (
        db_session.query(Recording).filter(
            Recording.id == recording.id).first())
    assert updated_recording.status == "processed"


# Sample Model Tests
def test_create_sample(db_session: Session):
    project = Project(name="Project For Samples")
    db_session.add(project)
    db_session.commit()
    recording = Recording(
        project_id=project.id,
        name="Recording For Samples",
        file_path="rec.wav")
    db_session.add(recording)
    db_session.commit()
    db_session.refresh(recording)

    sample = Sample(
        recording_id=recording.id,
        name="Test Sample",
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
    assert sample.recording.name == "Recording For Samples"  # Test relationship


# Relationship Tests
def test_project_has_multiple_recordings(db_session: Session):
    project = Project(name="Multi-Recording Project")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    rec1 = Recording(project_id=project.id, name="Rec 1", file_path="r1.wav")
    rec2 = Recording(project_id=project.id, name="Rec 2", file_path="r2.wav")
    db_session.add_all([rec1, rec2])
    db_session.commit()

    # Query project and check its recordings relationship
    retrieved_project = (
        db_session.query(Project).filter(Project.id == project.id).first()
    )
    assert len(retrieved_project.recordings) == 2
    assert retrieved_project.recordings[0].name == "Rec 1"
    assert retrieved_project.recordings[1].name == "Rec 2"


def test_recording_has_multiple_samples(db_session: Session):
    project = Project(name="Project For Multi-Sample Recording")
    db_session.add(project)
    db_session.commit()
    recording = Recording(
        project_id=project.id,
        name="Multi-Sample Recording",
        file_path="rec_ms.wav")
    db_session.add(recording)
    db_session.commit()
    db_session.refresh(recording)

    sample1 = Sample(
        recording_id=recording.id,
        name="Sample A",
        start_time_seconds=1.0,
        end_time_seconds=2.0,
    )
    sample2 = Sample(
        recording_id=recording.id,
        name="Sample B",
        start_time_seconds=3.0,
        end_time_seconds=4.0,
    )
    db_session.add_all([sample1, sample2])
    db_session.commit()

    retrieved_recording = (
        db_session.query(Recording).filter(
            Recording.id == recording.id).first())
    assert len(retrieved_recording.samples) == 2
    assert retrieved_recording.samples[0].name == "Sample A"
    assert retrieved_recording.samples[1].name == "Sample B"


# SampleMapping and SampleMappingItem Model Tests (Basic)
def test_create_sample_mapping(db_session: Session):
    project = Project(name="Project For Mappings")
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    sample_mapping = SampleMapping(
        project_id=project.id, name="Drum Kit Map", mapping_type="drum_kit_pad"
    )
    db_session.add(sample_mapping)
    db_session.commit()
    db_session.refresh(sample_mapping)

    assert sample_mapping.id is not None
    assert sample_mapping.project_id == project.id
    assert sample_mapping.name == "Drum Kit Map"
    assert sample_mapping.project.name == "Project For Mappings"


def test_create_sample_mapping_item(db_session: Session):
    project = Project(name="Project For Mapping Items")
    db_session.add(project)
    db_session.commit()
    recording = Recording(
        project_id=project.id,
        name="Recording For Mapping Items",
        file_path="rec_mi.wav",
    )
    db_session.add(recording)
    sample = Sample(
        recording_id=recording.id,
        name="Kick Sample",
        start_time_seconds=0.1,
        end_time_seconds=0.5,
        midi_pitch=36,
    )
    db_session.add(sample)
    sample_mapping = SampleMapping(
        project_id=project.id,
        name="Drum Map For Item Test",
        mapping_type="drum_kit")
    db_session.add(sample_mapping)
    db_session.commit()
    db_session.refresh(project)
    db_session.refresh(recording)
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
    assert item.sample.name == "Kick Sample"
    assert item.sample_mapping.name == "Drum Map For Item Test"


def test_sample_mapping_has_multiple_items(db_session: Session):
    project = Project(name="Project For Multi-Item Mapping")
    db_session.add(project)
    db_session.commit()
    recording = Recording(
        project_id=project.id,
        name="Rec For Multi-Item",
        file_path="rec_smi.wav")
    db_session.add(recording)
    sample1 = Sample(
        recording_id=recording.id,
        name="Snare",
        start_time_seconds=0.1,
        end_time_seconds=0.4,
        midi_pitch=38,
    )
    sample2 = Sample(
        recording_id=recording.id,
        name="HiHat",
        start_time_seconds=0.5,
        end_time_seconds=0.7,
        midi_pitch=42,
    )
    db_session.add_all([sample1, sample2])
    sample_mapping = SampleMapping(
        project_id=project.id,
        name="Drum Map Multi Test",
        mapping_type="drum_kit")
    db_session.add(sample_mapping)
    db_session.commit()
    db_session.refresh(project)  # Refresh all to get IDs
    db_session.refresh(recording)
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

    retrieved_mapping = (
        db_session.query(SampleMapping)
        .filter(SampleMapping.id == sample_mapping.id)
        .first()
    )
    assert len(retrieved_mapping.sample_mapping_items) == 2
    # Order might not be guaranteed, so check names or specific attributes
    item_names = sorted(
        [item.sample.name for item in retrieved_mapping.sample_mapping_items]
    )
    assert "HiHat" in item_names
    assert "Snare" in item_names
