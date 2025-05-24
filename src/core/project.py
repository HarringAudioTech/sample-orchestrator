"""
Manages projects and their associated audio recordings.

This module defines the `Project` class, which provides an interface for
interacting with project data stored in the database. It allows for creating
projects (though project creation itself is usually handled at the API level),
adding recordings to projects, and listing recordings within a project.
Audio file metadata extraction is also handled when adding recordings.
"""

import os
import wave
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError # For more specific exception handling

from src.database.models import Project as ProjectModel, Recording as RecordingModel
from src.database.utils import get_db # Changed SessionLocal import to get_db


class Project:
    """
    Manages operations related to a specific project, such as adding,
    retrieving, and processing audio recordings associated with it.

    Attributes:
        project_id (int): The ID of the project this instance manages.
        project_model (ProjectModel): The SQLAlchemy model instance for this project,
                                      loaded from the database.
    """

    def __init__(self, project_id: int):
        """
        Initializes a Project instance by loading its data from the database.

        Args:
            project_id (int): The ID of the project to load.

        Raises:
            ValueError: If no project with the given `project_id` is found in the database.
        """
        db_gen = get_db()
        db: Session = next(db_gen)
        try:
            project_model_instance = ( # Renamed to avoid direct self assignment before validation
                db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
            )
            if not project_model_instance:
                # Log this specific error condition
                # current_app.logger.warning(f"Project with id {project_id} not found in database.")
                raise ValueError(f"Project with id {project_id} not found")
            self.project_model = project_model_instance
            self.project_id = project_id
        except SQLAlchemyError as e_sql:
            # current_app.logger.error(f"SQLAlchemyError initializing project {project_id}: {e_sql}", exc_info=True)
            raise ValueError(f"Database error while loading project {project_id}") from e_sql
        # Removed broad Exception catch, ValueError and SQLAlchemyError are more specific
        finally:
            next(db_gen, None) # Ensure generator is exhausted and session closed

    def add_recording(self, file_path: str, name: str) -> RecordingModel:
        """
        Adds a new audio recording to the current project.

        This method extracts metadata (duration, samplerate, channels) from the
        audio file, creates a new Recording entry in the database, and associates
        it with this project.

        Args:
            file_path (str): The absolute or relative path to the audio file.
            name (str): A user-friendly name for this recording.

        Returns:
            RecordingModel: The newly created SQLAlchemy Recording model instance.

        Raises:
            FileNotFoundError: If the audio file at `file_path` does not exist.
            wave.Error: If the audio file is not a valid WAV file or is corrupted.
            IOError: If there's an issue reading the file.
            SQLAlchemyError: If there's an error during database operations.
        """
        db_gen = get_db()
        db: Session = next(db_gen)
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Recording file not found: {file_path}")

            duration_seconds = None
            samplerate = None
            channels = None

            try:
                with wave.open(file_path, "rb") as wf:
                    frames = wf.getnframes()
                    samplerate = wf.getframerate() # Use wave's samplerate directly
                    duration_seconds = frames / float(samplerate)
                    channels = wf.getnchannels()
            except (wave.Error, IOError) as e_wave:
                # Log error or handle as per application requirements
                # For now, re-raise to indicate failure in getting audio properties
                # Or, allow recording to be added with null metadata by commenting out raise
                print(f"Error getting WAV audio properties for {file_path}: {e_wave}.")
                print("Recording will be added with partial/null metadata.")
                # raise ValueError(f"Error getting WAV audio properties for {file_path}: {e_wave}") from e_wave # Option to enforce
                # metadata presence by raising an error.

            new_recording = RecordingModel(
                project_id=self.project_id,
                name=name,
                file_path=file_path,  # Store the original path
                duration_seconds=duration_seconds,
                samplerate=samplerate,
                channels=channels,
                status="pending",  # Initial status
            )
            db.add(new_recording)
            db.commit()
            db.refresh(new_recording)
            return new_recording
        except SQLAlchemyError as e_sql:
            db.rollback()
            # Log error: print(f"Database error adding recording {name}: {e_sql}")
            raise # Re-raise to be handled by caller or a higher-level error handler
        finally:
            next(db_gen, None)

    def get_recording(self, recording_id: int) -> RecordingModel | None:
        """
        Retrieves a specific recording associated with this project by its ID.

        Args:
            recording_id (int): The ID of the recording to retrieve.

        Returns:
            RecordingModel | None: The SQLAlchemy Recording model instance if found,
                                   otherwise None.
        """
        db_gen = get_db()
        db: Session = next(db_gen)
        try:
            recording = (
                db.query(RecordingModel)
                .filter(
                    RecordingModel.id == recording_id,
                    RecordingModel.project_id == self.project_id,
                )
                .first()
            )
            return recording
        finally:
            next(db_gen, None)

    def list_recordings(self) -> list[RecordingModel]:
        """
        Lists all recordings associated with this project.

        Returns:
            list[RecordingModel]: A list of SQLAlchemy Recording model instances.
        """
        db_gen = get_db()
        db: Session = next(db_gen)
        try:
            recordings = (
                db.query(RecordingModel)
                .filter(RecordingModel.project_id == self.project_id)
                .all()
            )
            return recordings
        finally:
            next(db_gen, None)

    def process_recording(self, recording_id: int, output_sample_dir: str):
        """
        # The process_recording method has been removed as slicing is now handled by SlicingStage.
        pass

if __name__ == "__main__":
    # The example usage code has been removed to simplify the module and
    # because it relied on the now-removed process_recording method and aubio.
    # For testing or direct interaction, please use the API or dedicated test scripts.
    pass
