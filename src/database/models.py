from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class Project(Base):
    """
    Represents a user's project, which groups recordings and sample mappings.
    """
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    recordings = relationship("Recording", back_populates="project", cascade="all, delete-orphan")
    sample_mappings = relationship("SampleMapping", back_populates="project", cascade="all, delete-orphan")

class Recording(Base):
    """
    Represents an audio recording file associated with a project.
    Contains metadata about the audio file and its processing status.
    """
    __tablename__ = "recordings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    file_path = Column(String, nullable=False, unique=True)
    duration_seconds = Column(Float)
    samplerate = Column(Integer)
    channels = Column(Integer)
    status = Column(String, default="pending")  # e.g., "pending", "processing", "processed", "failed"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="recordings")
    samples = relationship("Sample", back_populates="recording", cascade="all, delete-orphan")

class Sample(Base):
    """
    Represents a sliced audio sample extracted from a recording.
    Contains information about the sample's timing, pitch, and other metadata.
    """
    __tablename__ = "samples"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    recording_id = Column(Integer, ForeignKey("recordings.id"), nullable=False)
    name = Column(String, nullable=False) # Often derived from recording name, pitch, etc.
    file_path = Column(String, nullable=False, unique=True) # Path to the individual sample's audio file
    start_time_seconds = Column(Float, nullable=False)
    end_time_seconds = Column(Float, nullable=False)
    sample_type = Column(String)  # E.g., "one-shot", "loop", "multi-sample_region"
    midi_pitch = Column(Integer, nullable=True) # Detected or assigned MIDI pitch
    metadata_json = Column(Text, nullable=True) # For additional metadata like velocity, timbre, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    recording = relationship("Recording", back_populates="samples")
    sample_mapping_items = relationship("SampleMappingItem", back_populates="sample", cascade="all, delete-orphan")

class SampleMapping(Base):
    """
    Defines how samples are mapped, e.g., to MIDI keys or drum pads.
    Associated with a project.
    """
    __tablename__ = "sample_mappings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)  # E.g., "Piano C4-D#4 Layer 1", "Kick Drum Pad"
    mapping_type = Column(String)  # E.g., "drum_kit_pad", "instrument_key_zone", "velocity_layer"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    project = relationship("Project", back_populates="sample_mappings")
    sample_mapping_items = relationship("SampleMappingItem", back_populates="sample_mapping", cascade="all, delete-orphan")

class SampleMappingItem(Base):
    """
    An individual item within a SampleMapping, linking a specific Sample
    to mapping parameters like key range or velocity range.
    """
    __tablename__ = "sample_mapping_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    sample_mapping_id = Column(Integer, ForeignKey("sample_mappings.id"), nullable=False)
    sample_id = Column(Integer, ForeignKey("samples.id"), nullable=False)
    key_range_start = Column(Integer, nullable=True) # MIDI note number
    key_range_end = Column(Integer, nullable=True)   # MIDI note number
    velocity_range_start = Column(Integer, nullable=True) # MIDI velocity (0-127)
    velocity_range_end = Column(Integer, nullable=True)   # MIDI velocity (0-127)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # updated_at is not strictly necessary here as this table is primarily an association table.

    sample_mapping = relationship("SampleMapping", back_populates="sample_mapping_items")
    sample = relationship("Sample", back_populates="sample_mapping_items")


# Note on cascade options:
# "all, delete-orphan" means that when a parent object is deleted,
# its related child objects are also deleted. If a child object is
# disassociated from its parent (e.g., project.recordings.remove(some_recording)),
# it will also be deleted if it's an orphan (no longer referenced by a parent).
# This is generally useful for owned relationships like Project -> Recordings -> Samples.
