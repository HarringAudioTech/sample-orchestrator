"""
Database models for sample-orchestrator.

This module defines SQLAlchemy models for projects, recordings, and samples.
"""

import datetime
import enum
import json
from typing import Dict, Any, Optional, List

from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

from src.database.utils import Base


class ProjectType(str, enum.Enum):
    """Enum for project types."""
    SAMPLE_PACK = "sample_pack"
    VIRTUAL_INSTRUMENT = "virtual_instrument"


class SamplePackStatus(str, enum.Enum):
    """Status of a sample pack in the orchestrator."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETE = "complete"
    FAILED = "failed"


class ProjectModel(Base):
    """Base model for projects."""
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    project_type = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    metadata_json = Column(Text, nullable=True)
    
    # Define relationships
    recordings = relationship("RecordingModel", back_populates="project", cascade="all, delete-orphan")
    
    __mapper_args__ = {
        "polymorphic_identity": "project",
        "polymorphic_on": project_type
    }
    
    @property
    def meta_data(self) -> Dict[str, Any]:
        """Parse and return metadata JSON as a dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}


class SamplePackModel(ProjectModel):
    """Model for sample pack projects."""
    __tablename__ = "sample_packs"
    
    id = Column(Integer, ForeignKey("projects.id"), primary_key=True)
    
    __mapper_args__ = {
        "polymorphic_identity": "sample_pack",
    }
    
    @property
    def sample_count(self) -> int:
        """Get the total number of samples in this sample pack."""
        count = 0
        for recording in self.recordings:
            count += len(recording.samples)
        return count


class VirtualInstrumentModel(ProjectModel):
    """Model for virtual instrument projects."""
    __tablename__ = "virtual_instruments"
    
    id = Column(Integer, ForeignKey("projects.id"), primary_key=True)
    base_note = Column(Integer, nullable=True)  # MIDI note number
    velocity_layers = Column(Integer, nullable=True)
    round_robins = Column(Integer, nullable=True)
    
    __mapper_args__ = {
        "polymorphic_identity": "virtual_instrument",
    }


class RecordingModel(Base):
    """Model for audio recordings."""
    __tablename__ = "recordings"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    duration = Column(Float, nullable=True)  # in seconds
    sample_rate = Column(Integer, nullable=True)
    channels = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    metadata_json = Column(Text, nullable=True)
    
    # Define relationships
    project = relationship("ProjectModel", back_populates="recordings")
    samples = relationship("SampleModel", back_populates="recording", cascade="all, delete-orphan")
    
    @property
    def meta_data(self) -> Dict[str, Any]:
        """Parse and return metadata JSON as a dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}


class SampleModel(Base):
    """Model for audio samples."""
    __tablename__ = "samples"
    
    id = Column(Integer, primary_key=True, index=True)
    recording_id = Column(Integer, ForeignKey("recordings.id"), nullable=False)
    name = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    start_time = Column(Float, nullable=True)  # in seconds from parent recording
    duration = Column(Float, nullable=True)    # in seconds
    created_at = Column(DateTime, server_default=func.now())
    metadata_json = Column(Text, nullable=True)
    
    # Define relationships
    recording = relationship("RecordingModel", back_populates="samples")
    sample_mapping_items = relationship("SampleMappingItemModel", back_populates="sample", cascade="all, delete-orphan")
    
    @property
    def meta_data(self) -> Dict[str, Any]:
        """Parse and return metadata JSON as a dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}


class SampleMappingItemModel(Base):
    """Model for sample key mapping items."""
    __tablename__ = "sample_mapping_items"
    
    id = Column(Integer, primary_key=True, index=True)
    sample_id = Column(Integer, ForeignKey("samples.id"), nullable=False)
    key_range_start = Column(Integer, nullable=True)  # MIDI note number for range start
    key_range_end = Column(Integer, nullable=True)    # MIDI note number for range end
    velocity_range_start = Column(Integer, nullable=True)  # MIDI velocity range start
    velocity_range_end = Column(Integer, nullable=True)    # MIDI velocity range end
    root_note = Column(Integer, nullable=True)  # MIDI note number for sample root note
    created_at = Column(DateTime, server_default=func.now())
    
    # Define relationships
    sample = relationship("SampleModel", back_populates="sample_mapping_items")


class MidiDeviceModel(Base):
    """Model for MIDI input devices."""
    __tablename__ = "midi_devices"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    metadata_json = Column(Text, nullable=True)
    
    @property
    def meta_data(self) -> Dict[str, Any]:
        """Parse and return metadata JSON as a dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}


class MidiCaptureSessionModel(Base):
    """Model for MIDI capture sessions."""
    __tablename__ = "midi_capture_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)  # pending, recording, completed, failed, completed_empty
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Define relationships
    project = relationship("ProjectModel")
    midi_files = relationship("MidiFileModel", back_populates="capture_session", cascade="all, delete-orphan")


class MidiFileModel(Base):
    """Model for MIDI files captured in a session."""
    __tablename__ = "midi_files"
    
    id = Column(Integer, primary_key=True, index=True)
    capture_session_id = Column(Integer, ForeignKey("midi_capture_sessions.id"), nullable=False)
    device_id = Column(Integer, ForeignKey("midi_devices.id"), nullable=False)
    channel = Column(Integer, nullable=False)  # -1 for system messages, 0-15 for MIDI channels
    file_data = Column(Text, nullable=False)  # Binary MIDI data stored as text (base64 encoded)
    created_at = Column(DateTime, server_default=func.now())
    
    # Define relationships
    capture_session = relationship("MidiCaptureSessionModel", back_populates="midi_files")
    device = relationship("MidiDeviceModel")