from __future__ import annotations

from enum import Enum as PyEnum
from typing import List, Optional, Dict, Any
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Float,
    ForeignKey,
    LargeBinary,
    Enum as SQLAlchemyEnum,
    JSON,
    Boolean,
    Table,
    CheckConstraint,
)
from sqlalchemy.orm import relationship, declarative_base, Mapped, mapped_column
from sqlalchemy.sql import func
import datetime

Base = declarative_base()


class ProjectType(str, PyEnum):
    """Enumeration of project types."""
    SAMPLE_PACK = "sample_pack"
    VIRTUAL_INSTRUMENT = "virtual_instrument"


class Project(Base):
    """Represents a user's project, which groups recordings and sample mappings.
    
    Attributes:
        project_type: The type of project (sample pack or virtual instrument)
        name: The name of the project
        description: Optional description of the project
        base_note: For virtual instruments, the root note (e.g., 60 for C3)
        velocity_layers: Number of velocity layers for virtual instruments
        round_robins: Number of round robin variations per note/velocity
        metadata_json: Additional metadata in JSON format
    """

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    project_type: Mapped[ProjectType] = mapped_column(
        SQLAlchemyEnum(ProjectType, name="project_type"),
        nullable=False,
        default=ProjectType.SAMPLE_PACK
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # Virtual instrument specific fields
    base_note: Mapped[Optional[int]] = mapped_column(
        Integer, 
        nullable=True, 
        comment="MIDI note number for the base/root note (e.g., 60 for C3)"
    )
    velocity_layers: Mapped[Optional[int]] = mapped_column(
        Integer, 
        nullable=True, 
        default=1,
        comment="Number of velocity layers (e.g., 1-127)"
    )
    round_robins: Mapped[Optional[int]] = mapped_column(
        Integer, 
        nullable=True, 
        default=1,
        comment="Number of round robin variations per note/velocity"
    )
    metadata_json: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional metadata in JSON format"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    recordings: Mapped[List["Recording"]] = relationship(
        "Recording", back_populates="project", cascade="all, delete-orphan"
    )
    sample_mappings: Mapped[List["SampleMapping"]] = relationship(
        "SampleMapping", back_populates="project", cascade="all, delete-orphan"
    )
    midi_capture_sessions: Mapped[List["MidiCaptureSession"]] = relationship(
        "MidiCaptureSession", back_populates="project", cascade="all, delete-orphan"
    )
    sample_packs: Mapped[List["SamplePack"]] = relationship(
        "SamplePack", back_populates="project", cascade="all, delete-orphan"
    )


class Recording(Base):
    """Represents an audio recording file associated with a project.

    Contains metadata about the audio file and its processing status.
    """

    __tablename__ = "recordings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    filesize: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    samplerate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    channels: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(
        String, default="pending"
    )  # e.g., "pending", "processing", "processed", "failed"
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship("Project", back_populates="recordings")
    samples: Mapped[List["Sample"]] = relationship(
        "Sample", back_populates="recording", cascade="all, delete-orphan"
    )


class SampleType(str, PyEnum):
    ONE_SHOT = "one_shot"
    LOOP = "loop"
    MULTI_SAMPLE = "multi_sample"
    FILL = "fill"
    EFFECT = "effect"
    TEXTURE = "texture"


class Sample(Base):
    """Represents a sliced audio sample extracted from a recording.

    Contains information about the sample's timing, pitch, and other metadata.
    """

    __tablename__ = "samples"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    recording_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("recordings.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(
        String, nullable=False
    )  # Often derived from recording name, pitch, etc.
    file_path: Mapped[str] = mapped_column(
        String, nullable=False, unique=True
    )  # Path to the individual sample's audio file
    start_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    end_time_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    sample_type: Mapped[SampleType] = mapped_column(
        SQLAlchemyEnum(SampleType, name="sample_type"),
        nullable=False,
        default=SampleType.ONE_SHOT
    )
    is_loop: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    bpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    key: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    midi_pitch: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # Detected or assigned MIDI pitch
    metadata_json: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )  # For additional metadata like velocity, timbre, etc.
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sample_pack_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sample_packs.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    recording: Mapped["Recording"] = relationship("Recording", back_populates="samples")
    sample_mapping_items: Mapped[List["SampleMappingItem"]] = relationship(
        "SampleMappingItem", back_populates="sample", cascade="all, delete-orphan"
    )
    sample_pack: Mapped[Optional["SamplePack"]] = relationship("SamplePack", back_populates="samples")
    categories: Mapped[List["SampleCategory"]] = relationship(
        "SampleCategory", secondary="sample_category_association", back_populates="samples"
    )


class SampleMapping(Base):
    """Defines how samples are mapped, e.g., to MIDI keys or drum pads.

    Associated with a project.
    """

    __tablename__ = "sample_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(
        String, nullable=False
    )  # E.g., "Piano C4-D#4 Layer 1", "Kick Drum Pad"
    mapping_type: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )  # E.g., "drum_kit_pad", "instrument_key_zone", "velocity_layer"
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
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
    sample_mapping_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sample_mappings.id"), nullable=False
    )
    sample_id: Mapped[int] = mapped_column(Integer, ForeignKey("samples.id"), nullable=False)
    key_range_start: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # MIDI note number
    key_range_end: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # MIDI note number
    velocity_range_start: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # MIDI velocity (0-127)
    velocity_range_end: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )  # MIDI velocity (0-127)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # updated_at is not strictly necessary here as this table is primarily an
    # association table.

    sample_mapping: Mapped["SampleMapping"] = relationship(
        "SampleMapping", back_populates="sample_mapping_items"
    )
    sample: Mapped["Sample"] = relationship("Sample", back_populates="sample_mapping_items")


# Association table for many-to-many relationship between Sample and SampleCategory
sample_category_association = Table(
    'sample_category_association',
    Base.metadata,
    Column('sample_id', Integer, ForeignKey('samples.id'), primary_key=True),
    Column('category_id', Integer, ForeignKey('sample_categories.id'), primary_key=True)
)


class SamplePackStatus(str, PyEnum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    PUBLISHED = "published"


class SamplePack(Base):
    """Represents a collection of samples with metadata.
    
    A sample pack is a curated collection of audio samples, MIDI files, and related
    assets that are distributed together.
    """
    __tablename__ = "sample_packs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[SamplePackStatus] = mapped_column(
        SQLAlchemyEnum(SamplePackStatus, name="sample_pack_status"),
        nullable=False,
        default=SamplePackStatus.DRAFT
    )
    bpm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    key: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="sample_packs")
    samples: Mapped[List["Sample"]] = relationship("Sample", back_populates="sample_pack", cascade="all, delete-orphan")
    categories: Mapped[List["SampleCategory"]] = relationship(
        "SampleCategory", secondary="sample_pack_categories", back_populates="sample_packs"
    )
    bill_of_materials: Mapped[Optional["BillOfMaterials"]] = relationship(
        "BillOfMaterials", back_populates="sample_pack", uselist=False, cascade="all, delete-orphan"
    )
    midi_files: Mapped[List["MidiFile"]] = relationship("MidiFile", back_populates="sample_pack")


class SampleCategory(Base):
    """Categories for organizing samples within a sample pack.
    
    Examples: Drums, Bass, Synths, Vocals, etc.
    """
    __tablename__ = "sample_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    icon: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    samples: Mapped[List["Sample"]] = relationship(
        "Sample", secondary=sample_category_association, back_populates="categories"
    )
    sample_packs: Mapped[List["SamplePack"]] = relationship(
        "SamplePack", secondary="sample_pack_categories", back_populates="categories"
    )


# Association table for many-to-many relationship between SamplePack and SampleCategory
sample_pack_categories = Table(
    'sample_pack_categories',
    Base.metadata,
    Column('sample_pack_id', Integer, ForeignKey('sample_packs.id'), primary_key=True),
    Column('category_id', Integer, ForeignKey('sample_categories.id'), primary_key=True)
)


class BillOfMaterials(Base):
    """Tracks required components for a sample pack to be considered complete."""
    __tablename__ = "bill_of_materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    sample_pack_id: Mapped[int] = mapped_column(Integer, ForeignKey("sample_packs.id"), nullable=False, unique=True)
    required_samples: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required_midi: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    required_documentation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    required_artwork: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    sample_pack: Mapped["SamplePack"] = relationship("SamplePack", back_populates="bill_of_materials")

    # Stats (computed properties)
    @property
    def samples_completed(self) -> int:
        return len([s for s in self.sample_pack.samples if s.is_processed])

    @property
    def midi_completed(self) -> int:
        return len(self.sample_pack.midi_files)

    @property
    def completion_percentage(self) -> float:
        total_required = sum([
            self.required_samples,
            self.required_midi,
            1 if self.required_documentation else 0,
            1 if self.required_artwork else 0
        ])

        completed = sum(
            [
                min(self.samples_completed, self.required_samples),
                min(self.midi_completed, self.required_midi),
                (
                    1
                    if not self.required_documentation
                    or (
                        self.sample_pack.metadata_json is not None
                        and self.sample_pack.metadata_json.get("has_documentation")
                    )
                    else 0
                ),
                (
                    1
                    if not self.required_artwork
                    or (
                        self.sample_pack.metadata_json is not None
                        and self.sample_pack.metadata_json.get("has_artwork")
                    )
                    else 0
                ),
            ]
        )

        return (completed / total_required) * 100 if total_required > 0 else 0.0


class MidiDevice(Base):
    """Represents a MIDI input device."""

    __tablename__ = "midi_devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    system_identifier: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
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
    start_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_time: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending"
    )  # e.g., "pending", "recording", "completed", "failed"
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    project: Mapped["Project"] = relationship(
        "Project", back_populates="midi_capture_sessions"
    )
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
    midi_device_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("midi_devices.id"), nullable=False
    )
    channel_number: Mapped[int] = mapped_column(Integer, nullable=False)
    midi_data: Mapped[bytes] = mapped_column(
        LargeBinary, nullable=False
    )  # Replaced file_path with midi_data
    sample_pack_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sample_packs.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    capture_session: Mapped["MidiCaptureSession"] = relationship(
        "MidiCaptureSession", back_populates="midi_files"
    )
    device: Mapped["MidiDevice"] = relationship("MidiDevice", back_populates="midi_files")
    sample_pack: Mapped[Optional["SamplePack"]] = relationship("SamplePack", back_populates="midi_files")
