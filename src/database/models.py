"""
Database models for sample-orchestrator using SQLModel.

This module defines SQLModel classes for projects, recordings, and samples.
SQLModel unifies Pydantic models and SQLAlchemy models.
"""
from __future__ import annotations

import datetime
import enum
import json
from typing import Dict, Any, Optional, List, Union

from sqlmodel import SQLModel, Field, Relationship, create_engine, Session, select
from sqlalchemy import Column, Text, DateTime, func, Integer, String
from sqlalchemy.orm import relationship

class ProjectType(str, enum.Enum):
    """Enum for project types."""
    SAMPLE_PACK = "sample_pack"
    VIRTUAL_INSTRUMENT = "virtual_instrument"
    CONSTRUCTION_KIT = "construction_kit"


class SamplePackStatus(str, enum.Enum):
    """Status of a sample pack."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SampleStatus(str, enum.Enum):
    """Processing status of an audio sample."""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class SampleType(str, enum.Enum):
    """Type classification for audio samples."""
    ONE_SHOT = "one_shot"
    LOOP = "loop"
    AMBIENT = "ambient"
    FILL = "fill"
    TRANSITION = "transition"


class ProjectBase(SQLModel):
    name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    project_type: ProjectType = Field(sa_column=Column(String(50)))
    metadata_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    # Optional fields for VirtualInstrument (Single Table Inheritance)
    base_note: Optional[int] = None
    round_robins: Optional[int] = None

class ProjectModel(ProjectBase, table=True):
    __tablename__ = "projects"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now())
    )
    updated_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now(), onupdate=func.now())
    )

    # Relationships
    recordings: List["RecordingModel"] = Relationship(
        sa_relationship=relationship("RecordingModel", back_populates="project", cascade="all, delete-orphan", uselist=True)
    )
    
    velocity_groups: List["VelocityGroupModel"] = Relationship(
        sa_relationship=relationship("VelocityGroupModel", back_populates="project", cascade="all, delete-orphan", uselist=True)
    )
    
    manifest: Optional[ManifestModel] = Relationship(
        sa_relationship=relationship("ManifestModel", back_populates="project", cascade="all, delete-orphan", uselist=False)
    )

    @property
    def meta_data(self) -> Dict[str, Any]:
        """Parse and return metadata JSON as a dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}


# Type aliases for compatibility with legacy code
VirtualInstrumentModel = ProjectModel
ConstructionKitProjectModel = ProjectModel
SamplePackModel = ProjectModel


class RecordingBase(SQLModel):
    project_id: int = Field(foreign_key="projects.id")
    name: str = Field(max_length=255)
    file_path: str = Field(max_length=512)
    file_size_bytes: Optional[int] = None
    duration: Optional[float] = None
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    status: Optional[str] = Field(default="uploaded", max_length=50)
    file_format: Optional[str] = Field(default=None, max_length=10)
    metadata_json: Optional[str] = Field(default=None, sa_column=Column(Text))

class RecordingModel(RecordingBase, table=True):
    __tablename__ = "recordings"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now())
    )

    # Relationships
    project: ProjectModel = Relationship(
        sa_relationship=relationship("ProjectModel", back_populates="recordings")
    )
    samples: List["SampleModel"] = Relationship(
        sa_relationship=relationship("SampleModel", back_populates="recording", cascade="all, delete-orphan", uselist=True)
    )

    @property
    def meta_data(self) -> Dict[str, Any]:
        """Parse and return metadata JSON as a dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}


class SampleBase(SQLModel):
    recording_id: int = Field(foreign_key="recordings.id")
    name: str = Field(max_length=255)
    file_path: str = Field(max_length=512)
    start_time: Optional[float] = None
    duration: Optional[float] = None
    sample_type: Optional[str] = Field(default=SampleType.ONE_SHOT.value, max_length=50)
    status: Optional[str] = Field(default=SampleStatus.PENDING.value, max_length=50)
    metadata_json: Optional[str] = Field(default=None, sa_column=Column(Text))

class SampleModel(SampleBase, table=True):
    __tablename__ = "samples"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now())
    )

    # Relationships
    recording: RecordingModel = Relationship(
        sa_relationship=relationship("RecordingModel", back_populates="samples")
    )
    sample_mapping_items: List["SampleMappingItemModel"] = Relationship(
        sa_relationship=relationship("SampleMappingItemModel", back_populates="sample", cascade="all, delete-orphan", uselist=True)
    )

    @property
    def meta_data(self) -> Dict[str, Any]:
        """Parse and return metadata JSON as a dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}


class VelocityGroupModel(SQLModel, table=True):
    __tablename__ = "velocity_groups"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id")
    name: str = Field(default="default", max_length=255)
    low_vel: int = Field(default=0)
    high_vel: int = Field(default=127)

    # Relationships
    project: ProjectModel = Relationship(
        sa_relationship=relationship("ProjectModel", back_populates="velocity_groups")
    )
    sample_mapping_items: List[SampleMappingItemModel] = Relationship(
        sa_relationship=relationship("SampleMappingItemModel", back_populates="velocity_group")
    )


class SampleMappingItemModel(SQLModel, table=True):
    __tablename__ = "sample_mapping_items"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    sample_id: int = Field(foreign_key="samples.id")
    velocity_group_id: Optional[int] = Field(default=None, foreign_key="velocity_groups.id")

    key_range_start: Optional[int] = None
    key_range_end: Optional[int] = None
    root_note: Optional[int] = None
    created_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now())
    )
    
    # Relationships
    sample: SampleModel = Relationship(
        sa_relationship=relationship("SampleModel", back_populates="sample_mapping_items")
    )
    velocity_group: Optional[VelocityGroupModel] = Relationship(
        sa_relationship=relationship("VelocityGroupModel", back_populates="sample_mapping_items")
    )


class MidiDeviceModel(SQLModel, table=True):
    __tablename__ = "midi_devices"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255, sa_column=Column(String(255), unique=True, nullable=False))
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    is_available: bool = Field(default=True)
    created_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now())
    )
    updated_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now(), onupdate=func.now())
    )
    metadata_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    
    @property
    def meta_data(self) -> Dict[str, Any]:
        """Parse and return metadata JSON as a dictionary."""
        if self.metadata_json:
            try:
                return json.loads(self.metadata_json)
            except json.JSONDecodeError:
                return {}
        return {}


class MidiCaptureSessionModel(SQLModel, table=True):
    __tablename__ = "midi_capture_sessions"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id")
    name: str = Field(max_length=255)
    status: str = Field(max_length=50)  # pending, recording, completed, failed, completed_empty
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    created_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now())
    )
    updated_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now(), onupdate=func.now())
    )
    
    # Relationships
    midi_files: List["MidiFileModel"] = Relationship(
        sa_relationship=relationship("MidiFileModel", back_populates="capture_session", cascade="all, delete-orphan", uselist=True)
    )


class MidiFileModel(SQLModel, table=True):
    __tablename__ = "midi_files"

    id: Optional[int] = Field(default=None, primary_key=True)
    capture_session_id: int = Field(foreign_key="midi_capture_sessions.id")
    device_id: int = Field(foreign_key="midi_devices.id")
    channel: int = Field()  # -1 for system messages, 0-15 for MIDI channels
    file_data: str = Field(sa_column=Column(Text, nullable=False)) # base64 encoded
    created_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now())
    )

    # Relationships
    capture_session: MidiCaptureSessionModel = Relationship(
        sa_relationship=relationship("MidiCaptureSessionModel", back_populates="midi_files")
    )


class LoopGenerationConfigModel(SQLModel, table=True):
    __tablename__ = "loop_generation_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    engine_id: str = Field(default="bass", max_length=100)
    key: str = Field(default="C", max_length=10)
    meter: str = Field(default="4/4", max_length=10)
    tempo: float = Field(default=120.0)
    bars: int = Field(default=4)
    seed: int = Field(default=42)
    engine_options_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    chords_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now())
    )
    updated_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now(), onupdate=func.now())
    )

    @property
    def engine_options(self) -> Dict[str, Any]:
        return json.loads(self.engine_options_json) if self.engine_options_json else {}

    @property
    def chords(self) -> List[Dict[str, str]]:
        return json.loads(self.chords_json) if self.chords_json else []


class LoopRenderingConfigModel(SQLModel, table=True):
    __tablename__ = "loop_rendering_configs"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=255)
    midi_port: str = Field(max_length=255)
    audio_device_index: Optional[int] = None
    capture_tail_seconds: float = Field(default=2.0)
    patch_data_json: Optional[str] = Field(default=None, sa_column=Column(Text))
    created_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now())
    )
    updated_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now(), onupdate=func.now())
    )

    @property
    def patch_data(self) -> Dict[str, Any]:
        return json.loads(self.patch_data_json) if self.patch_data_json else {}


class ManifestModel(SQLModel, table=True):
    __tablename__ = "manifests"

    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: int = Field(foreign_key="projects.id")
    created_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now())
    )
    updated_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now(), onupdate=func.now())
    )

    # Relationships
    project: ProjectModel = Relationship(
        sa_relationship=relationship("ProjectModel", back_populates="manifest")
    )
    rules: List["ManifestRuleModel"] = Relationship(
        sa_relationship=relationship("ManifestRuleModel", back_populates="manifest", cascade="all, delete-orphan", uselist=True)
    )


class ManifestRuleModel(SQLModel, table=True):
    __tablename__ = "manifest_rules"

    id: Optional[int] = Field(default=None, primary_key=True)
    manifest_id: int = Field(foreign_key="manifests.id")
    name: str = Field(max_length=255)
    required_tags_json: str = Field(sa_column=Column(Text, nullable=False))
    target_count: int = Field(default=1)
    category: Optional[str] = Field(default=None, max_length=100)
    created_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now())
    )
    updated_at: datetime.datetime = Field(
        sa_column=Column(DateTime, server_default=func.now(), onupdate=func.now())
    )

    # Relationships
    manifest: ManifestModel = Relationship(
        sa_relationship=relationship("ManifestModel", back_populates="rules")
    )

    @property
    def required_tags(self) -> Dict[str, Any]:
        """Parse and return required tags JSON as a dictionary."""
        if self.required_tags_json:
            try:
                return json.loads(self.required_tags_json)
            except json.JSONDecodeError:
                return {}
        return {}
