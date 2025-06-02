from __future__ import annotations

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    ForeignKey,
    LargeBinary,  # Added LargeBinary
)
from sqlalchemy.orm import relationship, declarative_base, Mapped, mapped_column
from sqlalchemy.sql import func
import datetime # For type hinting datetime columns
from typing import List, Optional # For type hinting relationships and nullable fields

Base = declarative_base()


class Project(Base):
    """Represents a user's project, which groups recordings and sample mappings."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    recordings: Mapped[List["Recording"]] = relationship(
        "Recording", back_populates="project", cascade="all, delete-orphan"
    )
    sample_mappings: Mapped[List["SampleMapping"]] = relationship(
        "SampleMapping", back_populates="project", cascade="all, delete-orphan"
    )
    # Relationship for MidiCaptureSession added at the end of the file
    # midi_capture_sessions: Mapped[List["MidiCaptureSession"]] # Removed this line


class Recording(Base):
    """Represents an audio recording file associated with a project.

    Contains metadata about the audio file and its processing status.
    """

    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    samplerate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    channels: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String, default="pending"
    )  # e.g., "pending", "processing", "processed", "failed"
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="recordings")
    samples: Mapped[List["Sample"]] = relationship("Sample", back_populates="recording", cascade="all, delete-orphan")


class Sample(Base):
    """Represents a sliced audio sample extracted from a recording.

    Contains information about the sample's timing, pitch, and other metadata.
    """

    __tablename__ = "samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    recording_id: Mapped[int] = mapped_column(Integer, ForeignKey("recordings.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)  # Often derived from recording name, pitch, etc.
    file_path: Mapped[str] = mapped_column(
        String, nullable=False, unique=True
    )  # Path to the individual sample's audio file
    start_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sample_type: Mapped[Optional[str]] = mapped_column(String, nullable=True) # E.g., "one-shot", "loop", "multi-sample_region"
    midi_pitch: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # Detected or assigned MIDI pitch
    metadata_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # For additional metadata like velocity, timbre, etc.
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    recording: Mapped["Recording"] = relationship("Recording", back_populates="samples")
    sample_mapping_items: Mapped[List["SampleMappingItem"]] = relationship(
        "SampleMappingItem", back_populates="sample", cascade="all, delete-orphan"
    )


class SampleMapping(Base):
    """Defines how samples are mapped, e.g., to MIDI keys or drum pads.

    Associated with a project.
    """

    __tablename__ = "sample_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)  # E.g., "Piano C4-D#4 Layer 1", "Kick Drum Pad"
    mapping_type: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # E.g., "drum_kit_pad", "instrument_key_zone", "velocity_layer"
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="sample_mappings")
    sample_mapping_items: Mapped[List["SampleMappingItem"]] = relationship(
        "SampleMappingItem",
        back_populates="sample_mapping",
        cascade="all, delete-orphan",
    )


class SampleMappingItem(Base):
    """An individual item within a SampleMapping, linking a specific Sample
    to mapping parameters like key range or velocity range.
    """

    __tablename__ = "sample_mapping_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    sample_mapping_id: Mapped[int] = mapped_column(Integer, ForeignKey("sample_mappings.id"), nullable=False)
    sample_id: Mapped[int] = mapped_column(Integer, ForeignKey("samples.id"), nullable=False)
    key_range_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # MIDI note number
    key_range_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # MIDI note number
    velocity_range_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # MIDI velocity (0-127)
    velocity_range_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # MIDI velocity (0-127)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # updated_at is not strictly necessary here as this table is primarily an
    # association table.

    sample_mapping: Mapped["SampleMapping"] = relationship("SampleMapping", back_populates="sample_mapping_items")
    sample: Mapped["Sample"] = relationship("Sample", back_populates="sample_mapping_items")


# Note on cascade options:
# "all, delete-orphan" means that when a parent object is deleted,
# its related child objects are also deleted. If a child object is
# disassociated from its parent (e.g., project.recordings.remove(some_recording)),
# it will also be deleted if it's an orphan (no longer referenced by a parent).
# This is generally useful for owned relationships like Project ->
# Recordings -> Samples.


class MidiDevice(Base):
    """Represents a MIDI input device."""

    __tablename__ = "midi_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    system_identifier: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    midi_files: Mapped[List["MidiFile"]] = relationship("MidiFile", back_populates="device")


class MidiCaptureSession(Base):
    """Represents a session of capturing MIDI data."""

    __tablename__ = "midi_capture_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    start_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending"
    )  # e.g., "pending", "recording", "completed", "failed"
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="midi_capture_sessions")
    midi_files: Mapped[List["MidiFile"]] = relationship(
        "MidiFile", back_populates="capture_session", cascade="all, delete-orphan"
    )


class MidiFile(Base):
    """Represents MIDI data recorded during a capture session from a specific device.

    The actual MIDI data is stored in the `midi_data` attribute as binary (blob) content.
    """

    __tablename__ = "midi_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    midi_capture_session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("midi_capture_sessions.id"), nullable=False
    )
    midi_device_id: Mapped[int] = mapped_column(Integer, ForeignKey("midi_devices.id"), nullable=False)
    channel_number: Mapped[int] = mapped_column(Integer, nullable=False)
    midi_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False) # Replaced file_path with midi_data
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    capture_session: Mapped["MidiCaptureSession"] = relationship("MidiCaptureSession", back_populates="midi_files")
    device: Mapped["MidiDevice"] = relationship("MidiDevice", back_populates="midi_files")


# Add relationship to Project model for Mypy
Project.midi_capture_sessions = relationship( # type: ignore[attr-defined]
    "MidiCaptureSession", back_populates="project", cascade="all, delete-orphan"
)
