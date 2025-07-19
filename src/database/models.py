"""
Database models for the Audio Processing and Sample Management API.

CRITICAL: This application ONLY supports SQLite. Do not attempt to add 
support for PostgreSQL, MySQL, or any other database engine. Previous 
attempts to support multiple databases caused significant issues and 
were removed. SQLite is the only supported persistence layer.

SQLITE ONLY - NO EXCEPTIONS

Models:
- Project: Audio projects containing recordings and samples
- Recording: Individual audio files within a project
- Sample: Processed audio segments generated from recordings
"""

from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session

# SQLITE ONLY: Base class for all database models
Base = declarative_base()


class Project(Base):
    """
    Represents an audio project containing recordings and generated samples.
    
    SQLITE ONLY: This model is designed specifically for SQLite and should
    not be modified to support other database engines.
    
    Project Types:
    - 'sample_pack': Collection of individual audio samples
    - 'virtual_instrument': Mapped samples for instrument creation
    """
    __tablename__ = 'projects'
    
    # Primary key - SQLite auto-increment integer
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Project identification
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Project type: 'sample_pack' or 'virtual_instrument'
    project_type = Column(String(50), nullable=False, default='sample_pack')
    
    # Timestamps - SQLite compatible datetime
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Virtual instrument specific fields
    base_note = Column(String(10), nullable=True)  # e.g., 'C4', 'A3'
    velocity_layers = Column(Integer, default=1, nullable=False)
    round_robins = Column(Integer, default=1, nullable=False)
    
    # JSON metadata storage - SQLite TEXT field
    metadata_json = Column(Text, nullable=True)
    
    # Relationships - SQLite foreign key constraints
    recordings = relationship("Recording", back_populates="project", cascade="all, delete-orphan")
    midi_capture_sessions = relationship("MidiCaptureSession", back_populates="project", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}', type='{self.project_type}')>"
    
    @property
    def is_virtual_instrument(self) -> bool:
        """Check if this project is configured as a virtual instrument."""
        return self.project_type == 'virtual_instrument'


class Recording(Base):
    """
    Represents an individual audio recording within a project.
    
    SQLITE ONLY: This model uses SQLite-specific features and constraints.
    Do not modify for compatibility with other database engines.
    """
    __tablename__ = 'recordings'
    
    # Primary key - SQLite auto-increment integer
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to projects table - SQLite constraint
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    
    # Recording identification
    name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # Path to audio file
    
    # Audio properties
    duration_seconds = Column(Float, nullable=True)
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    file_size_bytes = Column(Integer, nullable=True)  # Size of the file in bytes
    
    # Processing status
    processing_status = Column(String(50), default='pending', nullable=False)  # pending, processing, completed, failed
    
    # Timestamps - SQLite compatible datetime
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # JSON metadata storage - SQLite TEXT field
    metadata_json = Column(Text, nullable=True)
    
    # Relationships - SQLite foreign key constraints
    project = relationship("Project", back_populates="recordings")
    samples = relationship("Sample", back_populates="recording", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Recording(id={self.id}, name='{self.name}', project_id={self.project_id})>"


class Sample(Base):
    """
    Represents a processed audio sample generated from a recording.
    
    SQLITE ONLY: This model is optimized for SQLite storage and indexing.
    Do not attempt to make it compatible with other database engines.
    """
    __tablename__ = 'samples'
    
    # Primary key - SQLite auto-increment integer
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to recordings table - SQLite constraint
    recording_id = Column(Integer, ForeignKey('recordings.id'), nullable=False)
    
    # Sample identification
    name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)  # Path to processed sample file
    
    # Timing information (in seconds)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    duration = Column(Float, nullable=False)
    
    # Musical properties
    detected_pitch = Column(String(10), nullable=True)  # e.g., 'C4', 'F#3'
    midi_note = Column(Integer, nullable=True)  # MIDI note number (0-127)
    confidence = Column(Float, nullable=True)  # Processing confidence (0.0-1.0)
    
    # Sample classification
    sample_type = Column(String(50), nullable=True)  # 'drum', 'vocal', 'melodic', etc.
    category = Column(String(50), nullable=True)  # Additional categorization used in tests
    tags = Column(Text, nullable=True)  # Comma-separated tags
    
    # Processing information
    processing_stage = Column(String(100), nullable=True)  # Stage that generated this sample
    
    # Timestamps - SQLite compatible datetime
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)
    
    # JSON metadata storage - SQLite TEXT field
    metadata_json = Column(Text, nullable=True)
    
    # Relationships - SQLite foreign key constraints
    recording = relationship("Recording", back_populates="samples")
    
    def __repr__(self) -> str:
        return f"<Sample(id={self.id}, name='{self.name}', recording_id={self.recording_id})>"
    
    @property
    def duration_ms(self) -> float:
        """Get sample duration in milliseconds."""
        return self.duration * 1000.0


# SQLITE ONLY: Helper functions for model operations
def model_to_dict(model_instance: Optional[Base]) -> Optional[Dict[str, Any]]:
    """
    Convert a SQLAlchemy model instance to a dictionary.
    
    SQLITE ONLY: This function is designed for SQLite model serialization.
    
    Args:
        model_instance: SQLAlchemy model instance or None
        
    Returns:
        Dictionary representation or None
    """
    if model_instance is None:
        return None
        
    result = {}
    
    # Get all column attributes
    for column in model_instance.__table__.columns:
        value = getattr(model_instance, column.name)
        
        # Convert datetime objects to ISO format strings
        if isinstance(value, datetime):
            value = value.isoformat()
            
        result[column.name] = value
    
    # Add computed properties for specific models
    if isinstance(model_instance, Project):
        result['is_virtual_instrument'] = model_instance.is_virtual_instrument
        
    if isinstance(model_instance, Sample):
        result['duration_ms'] = model_instance.duration_ms
    
    return result


# SQLITE ONLY: Enums used by processing stages and other modules
class ProjectType(str, Enum):
    """Enum for project types. Attribute names match database string values for ease of use.
    Upper-case names are kept for backwards compatibility, while lower-case aliases allow
    attribute access like ``ProjectType.sample_pack`` which many tests expect.
    """

    # Primary members
    SAMPLE_PACK = "sample_pack"
    VIRTUAL_INSTRUMENT = "virtual_instrument"

    # Aliases matching database string values (duplicate values become Enum aliases)
    sample_pack = SAMPLE_PACK  # type: ignore  # alias for convenience
    virtual_instrument = VIRTUAL_INSTRUMENT  # type: ignore  # alias for convenience


class SampleType(Enum):
    """Enum for sample types used in processing stages."""
    ONE_SHOT = "one_shot"
    LOOP = "loop"
    SUSTAIN = "sustain"
    RELEASE = "release"


class SampleStatus(Enum):
    """Enum for sample processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SamplePackStatus(Enum):
    """Enum for sample pack status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# MIDI Device Model
class MidiDevice(Base):
    """Represents a MIDI input device available to the system.
    
    SQLITE ONLY: This model stores information about MIDI devices that can be
    used for recording MIDI data.
    """
    __tablename__ = 'midi_devices'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    system_identifier = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<MidiDevice(id={self.id}, name='{self.name}')>"


# MIDI Capture Session Model
class MidiCaptureSession(Base):
    """Represents a MIDI capture session for recording MIDI data.
    
    SQLITE ONLY: This model stores information about MIDI recording sessions.
    """
    __tablename__ = 'midi_capture_sessions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default='pending')  # pending, recording, completed, failed
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="midi_capture_sessions")
    midi_files = relationship("MidiFile", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<MidiCaptureSession(id={self.id}, name='{self.name}', status='{self.status}')>"


# MIDI File Model
class MidiFile(Base):
    """Represents a MIDI file captured during a MIDI recording session.
    
    SQLITE ONLY: This model stores the binary MIDI data and metadata.
    """
    __tablename__ = 'midi_files'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey('midi_capture_sessions.id'), nullable=False)
    device_id = Column(Integer, ForeignKey('midi_devices.id'), nullable=True)
    channel = Column(Integer, nullable=True)  # -1 for system messages
    midi_data = Column(Text, nullable=False)  # Store as base64-encoded string
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    session = relationship("MidiCaptureSession", back_populates="midi_files")
    device = relationship("MidiDevice")
    
    def __repr__(self):
        return f"<MidiFile(id={self.id}, session_id={self.session_id}, channel={self.channel})>"


# SQLITE ONLY: Legacy model aliases for backward compatibility
class SamplePack(Base):
    """
    Legacy sample pack model for backward compatibility.
    
    SQLITE ONLY: This model provides backward compatibility for existing
    processing stages that expect a SamplePack model.
    """
    __tablename__ = 'sample_packs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default='pending')
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    project = relationship("Project")
    
    def __repr__(self) -> str:
        return f"<SamplePack(id={self.id}, name='{self.name}', project_id={self.project_id})>"


class SampleMappingItem(Base):
    """
    Model for individual sample mapping items.
    
    SQLITE ONLY: Used for virtual instrument sample mappings.
    """
    __tablename__ = 'sample_mapping_items'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(Integer, ForeignKey('samples.id'), nullable=False)
    note = Column(String(10), nullable=True)  # MIDI note like 'C4'
    velocity_min = Column(Integer, nullable=True, default=0)
    velocity_max = Column(Integer, nullable=True, default=127)
    pitch_offset = Column(Float, nullable=True, default=0.0)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationship
    sample = relationship("Sample")
    
    def __repr__(self) -> str:
        return f"<SampleMappingItem(id={self.id}, sample_id={self.sample_id}, note='{self.note}')>"