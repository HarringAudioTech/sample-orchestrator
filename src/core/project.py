import os
# import wave # Removed
import logging  # Added logging
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError  # To catch DB errors specifically
import librosa # Added
import numpy as np # Added

from src.database.models import (
    Project as ProjectModel,
    Recording as RecordingModel,
    MidiDevice as MidiDeviceModel,
    MidiCaptureSession as MidiCaptureSessionModel,
    MidiFile as MidiFileModel,
)
from src.database.utils import get_db, SessionLocal
from src.core.midi_capture import (
    MidiRecorder,
    list_available_midi_devices,
)
# from aubio import ( # Removed
#     source,
# )

# Configure basic logging
# In a larger application, this would likely be configured in a central place.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class Project:
    """
    Manages operations related to a specific project.

    This includes handling audio recordings (adding, listing, processing) and
    MIDI capture sessions (listing devices, creating sessions, listing sessions and files).
    Each instance of this class is tied to a specific project existing in the database.

    Attributes:
        project_id (int): The ID of the project this instance manages.
        project_model (ProjectModel): The SQLAlchemy model instance for this project,
                                      loaded from the database during initialization.
    """

    def __init__(self, project_id: int, db_session: Session = None):
        """
        Initializes a Project instance by loading its data from the database.

        Args:
            project_id (int): The ID of the project to load.
            db_session (Session, optional): An existing SQLAlchemy session.
                If provided, this session is used for database operations.
                If None, a new session is created for the initialization scope.

        Raises:
            ValueError: If no project with the given `project_id` is found.
            SQLAlchemyError: If there's an issue communicating with the database.
        """
        logger.info(f"Initializing Project core for project_id: {project_id}")
        self.db = db_session  # Store the provided session, if any

        _db_to_use: Session
        _manage_session_locally = False
        db_gen = None  # Initialize db_gen to None

        if self.db:
            _db_to_use = self.db
            logger.debug("Using provided db_session for Project initialization.")
        else:
            logger.debug("No db_session provided, creating local session for Project initialization.")
            db_gen = get_db()  # get_db() can now use app.config if in app context
            _db_to_use = next(db_gen)
            _manage_session_locally = True

        try:
            project_model = (
                _db_to_use.query(ProjectModel)
                .filter(ProjectModel.id == project_id)
                .first()
            )
            if not project_model:
                logger.error(
                    f"Project with id {project_id} not found in database."
                )
                raise ValueError(f"Project with id {project_id} not found")
            self.project_model = project_model
            self.project_id = project_id
            logger.info(
                f"Successfully initialized Project core for project: {self.project_model.name}"
            )
        except SQLAlchemyError as e:
            logger.error(
                f"Database error during Project initialization for project_id {project_id}: {e}"
            )
            raise
        finally:
            if _manage_session_locally and db_gen:
                try:
                    # Ensure generator is exhausted and session closed if created locally
                    next(db_gen, None)
                    logger.debug("Closed locally managed session for Project initialization.")
                except StopIteration:  # Handle if generator is already exhausted
                    pass

    def add_recording(self, file_path: str, name: str) -> RecordingModel:
        """
        Adds a new audio recording to the current project.

        Extracts metadata (duration, samplerate, channels) from the audio file,
        creates a new `RecordingModel` entry in the database, and associates
        it with this project.

        Args:
            file_path (str): The path to the audio file.
            name (str): A user-friendly name for this recording.

        Returns:
            RecordingModel: The newly created SQLAlchemy `RecordingModel` instance.

        Raises:
            FileNotFoundError: If the audio file at `file_path` does not exist.
            SQLAlchemyError: If any database operations fail.
            Exception: Can re-raise exceptions from audio metadata extraction
                       (e.g., `aubio.source`, `wave.open`) if issues occur.
        """
        logger.info(
            f"Adding recording '{name}' from path '{file_path}' to project ID {self.project_id}."
        )
        
        _db_to_use = self.db
        _manage_session_locally = False
        db_gen_local = None

        if _db_to_use is None:
            logger.debug("No self.db session, creating local session for add_recording.")
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            logger.debug("Using self.db session for add_recording.")

        try:
            if not os.path.exists(file_path):
                logger.error(f"Recording file not found: {file_path}")
                raise FileNotFoundError(
                    f"Recording file not found: {file_path}")

            duration_seconds = None
            samplerate = None
            channels = None
            # total_frames = None # Optional, but good to have, though not directly used by RecordingModel

            try:
                # Load the full audio primarily to get its properties.
                # sr=None ensures loading at native sample rate.
                y, sr_librosa = librosa.load(file_path, sr=None, mono=False) # mono=False to get actual channels

                samplerate = sr_librosa
                duration_seconds = librosa.get_duration(y=y, sr=samplerate)
                
                if y.ndim == 1:
                    channels = 1
                else:
                    channels = y.shape[0] # For multi-channel, librosa loads as (channels, samples)
                
                # total_frames = len(y) if y.ndim == 1 else y.shape[1] # Not directly stored in RecordingModel

                logger.info(f"Extracted metadata using librosa for {file_path}: SR={samplerate}, Duration={duration_seconds}s, Channels={channels}")

            except Exception as e:
                logger.error(
                    f"Error getting audio properties for {file_path} using librosa: {e}. "
                    "Recording will be added with minimal or no metadata.",
                    exc_info=True,
                )

            new_recording = RecordingModel(
                project_id=self.project_id,
                name=name,
                file_path=file_path,
                duration_seconds=duration_seconds,
                samplerate=samplerate,
                channels=channels,
                status="pending",
            )
            _db_to_use.add(new_recording)
            _db_to_use.commit()
            _db_to_use.refresh(new_recording)
            logger.info(
                f"Successfully added recording '{new_recording.name}' with ID {new_recording.id}."
            )
            return new_recording
        except SQLAlchemyError as e:
            if _db_to_use: # Check if session was successfully obtained before rollback
                _db_to_use.rollback()
            logger.error(f"Database error adding recording '{name}': {e}")
            raise
        finally:
            if _manage_session_locally and db_gen_local:
                try:
                    next(db_gen_local, None)
                    logger.debug("Closed locally managed session for add_recording.")
                except StopIteration:
                    pass

    def get_recording(self, recording_id: int) -> RecordingModel | None:
        """
        Retrieves a specific recording associated with this project by its ID.

        Args:
            recording_id (int): The ID of the recording to retrieve.

        Returns:
            RecordingModel | None: The `RecordingModel` instance if found and belonging
                                   to this project, otherwise `None`.

        Raises:
            SQLAlchemyError: If there's an issue communicating with the database.
        """
        logger.debug(
            f"Retrieving recording ID {recording_id} for project ID {self.project_id}."
        )
        
        _db_to_use = self.db
        _manage_session_locally = False
        db_gen_local = None

        if _db_to_use is None:
            logger.debug("No self.db session, creating local session for get_recording.")
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            logger.debug("Using self.db session for get_recording.")

        try:
            recording = (
                _db_to_use.query(RecordingModel)
                .filter(
                    RecordingModel.id == recording_id,
                    RecordingModel.project_id == self.project_id,
                )
                .first()
            )
            if recording:
                logger.debug(f"Found recording: {recording.name}")
            else:
                logger.debug(
                    f"Recording ID {recording_id} not found for project ID {
                        self.project_id}.")
            return recording
        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving recording ID {recording_id}: {e}"
            )
            raise
        finally:
            if _manage_session_locally and db_gen_local:
                try:
                    next(db_gen_local, None)
                    logger.debug("Closed locally managed session for get_recording.")
                except StopIteration:
                    pass

    def list_recordings(self) -> list[RecordingModel]:
        """
        Lists all recordings associated with this project.

        Returns:
            list[RecordingModel]: A list of `RecordingModel` instances.

        Raises:
            SQLAlchemyError: If there's an issue communicating with the database.
        """
        logger.debug(
            f"Listing all recordings for project ID {self.project_id}."
        )

        _db_to_use = self.db
        _manage_session_locally = False
        db_gen_local = None

        if _db_to_use is None:
            logger.debug("No self.db session, creating local session for list_recordings.")
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            logger.debug("Using self.db session for list_recordings.")

        try:
            recordings = (
                _db_to_use.query(RecordingModel)
                .filter(RecordingModel.project_id == self.project_id)
                .order_by(RecordingModel.created_at.desc())  # Example ordering
                .all()
            )
            logger.debug(
                f"Found {
                    len(recordings)} recordings for project ID {
                    self.project_id}.")
            return recordings
        except SQLAlchemyError as e:
            logger.error(
                f"Database error listing recordings for project ID {self.project_id}: {e}"
            )
            raise
        finally:
            if _manage_session_locally and db_gen_local:
                try:
                    next(db_gen_local, None)
                    logger.debug("Closed locally managed session for list_recordings.")
                except StopIteration:
                    pass

    def process_recording(self, recording_id: int, output_sample_dir: str):
        """
        Initiates audio processing for a specific recording.

        Uses `detect_and_slice_recording` from `audio_processor.py`. Ensures the
        output directory exists. The processing function handles DB updates for
        samples and recording status.

        Args:
            recording_id (int): The ID of the recording to process.
            output_sample_dir (str): Path where sliced samples should be saved.

        Raises:
            SQLAlchemyError: If database interaction fails during pre-check.
            Exception: Can re-raise exceptions from `detect_and_slice_recording`.
        """
        logger.info(
            f"Initiating processing for recording ID {recording_id} in project {
                self.project_id}.")
        # TODO: Refactor this method to use the new SlicingStage via
        # stage_runner.
        raise NotImplementedError(
            "This processing method needs to be updated to use SlicingStage"
        )

        try:
            os.makedirs(output_sample_dir, exist_ok=True)
            logger.debug(
                f"Ensured output directory exists: {output_sample_dir}")
        except OSError as e:
            logger.error(
                f"Error creating output directory {output_sample_dir}: {e}. Processing aborted.")
            return  # Or raise custom error

        _db_to_use = self.db
        _manage_session_locally = False
        db_gen_local = None

        if _db_to_use is None:
            logger.debug("No self.db session, creating local session for process_recording pre-check.")
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            logger.debug("Using self.db session for process_recording pre-check.")
        
        try:
            # The following is part of the original method's pre-check logic
            recording = (
                _db_to_use.query(RecordingModel)
                .filter(
                    RecordingModel.id == recording_id,
                    RecordingModel.project_id == self.project_id,
                )
                .first()
            )

            if not recording:
                logger.warning(
                    f"Recording ID {recording_id} not found for project {
                        self.project_id}. Processing aborted.")
                return

            logger.info(
                # This line will now be part of the dead code
                f"Calling detect_and_slice_recording for recording ID {recording_id}."
            )
            # detect_and_slice_recording( # This line will now be part of the dead code
            #     db_processing_session, recording_id, output_sample_dir # This line will now be part of the dead code
            # ) # This line will now be part of the dead code
            logger.info(
                f"Processing task submitted for recording ID {recording_id}."
            )  # This line will now be part of the dead code
        except SQLAlchemyError as e:  # Catch DB errors from the pre-check query
            logger.error(
                f"Database error in process_recording pre-check for recording {recording_id}: {e}")
            raise
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during process_recording setup for recording {recording_id}: {e}",
                exc_info=True,
            )
            # Consider updating recording status to 'failed' here if
            # appropriate and not handled by called function
            raise
        finally:
            if _manage_session_locally and db_gen_local:
                try:
                    next(db_gen_local, None)
                    logger.debug("Closed locally managed session for process_recording pre-check.")
                except StopIteration:
                    pass
            # Note: The original db_processing_session.close() is removed as we now use _db_to_use
            # which is managed by the common finally block if created locally.
            # If self.db was used, it's not closed here.

    # --- MIDI Capture Related Methods ---

    def list_midi_devices(self) -> List[MidiDeviceModel]:
        """
        Lists available MIDI input devices and syncs them with the database.

        This method utilizes `list_available_midi_devices` from `midi_capture.py`,
        which handles the discovery of devices via `mido` and their persistence
        in the database.

        Returns:
            List[MidiDeviceModel]: A list of `MidiDeviceModel` instances representing
                                   all currently available MIDI input devices.

        Raises:
            SQLAlchemyError: If database interaction fails within `list_available_midi_devices`.
            Exception: If `mido` backend calls fail within `list_available_midi_devices`.
        """
        logger.info(f"Listing MIDI devices for project ID {self.project_id}.")

        _db_to_use = self.db
        _manage_session_locally = False
        db_gen_local = None

        if _db_to_use is None:
            logger.debug("No self.db session, creating local session for list_midi_devices.")
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            logger.debug("Using self.db session for list_midi_devices.")
        
        try:
            # list_available_midi_devices itself handles DB operations, so pass the session to it.
            devices = list_available_midi_devices(_db_to_use)
            logger.info(f"Found {len(devices)} MIDI devices.")
            return devices
        except Exception as e: # Includes SQLAlchemyError from list_available_midi_devices
            logger.error(
                f"Error listing MIDI devices in Project.list_midi_devices: {e}",
                exc_info=True,
            )
            # No explicit rollback here as list_available_midi_devices should handle its transaction,
            # or if it raises an error, the session state might be uncertain.
            # If _db_to_use is self.db, the caller manages its state.
            raise
        finally:
            if _manage_session_locally and db_gen_local:
                try:
                    next(db_gen_local, None)
                    logger.debug("Closed locally managed session for list_midi_devices.")
                except StopIteration:
                    pass

    def create_midi_capture_session(
        self, session_name: str, selected_device_names: list[str]
    ) -> MidiRecorder:
        """
        Initializes a `MidiRecorder` for a new MIDI capture session.

        A `MidiCaptureSessionModel` entry is created in the database via the
        `MidiRecorder`'s constructor. The database session used for this
        initialization is then closed. The returned `MidiRecorder` instance
        requires a new database session to be passed to its `start_recording`
        and `stop_recording` methods by the caller.

        Args:
            session_name (str): The user-defined name for the new MIDI capture session.
            selected_device_names (list[str]): A list of names of MIDI input devices
                                               to be used for this session. These devices
                                               should exist in the database (e.g., by prior
                                               call to `list_midi_devices`).

        Returns:
            MidiRecorder: An instance of `MidiRecorder` configured for the new session.

        Raises:
            ValueError: If `project_id` is invalid, or if no valid devices are found
                        based on `selected_device_names` (raised by `MidiRecorder`).
            SQLAlchemyError: If database operations fail during `MidiRecorder` initialization.
        """
        logger.info(
            f"Creating MIDI capture session '{session_name}' for project ID {self.project_id} "
            f"with devices: {selected_device_names}"
        )

        _db_to_use = self.db
        _manage_session_locally = False
        db_gen_local = None

        if _db_to_use is None:
            logger.debug("No self.db session, creating local session for create_midi_capture_session.")
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            logger.debug("Using self.db session for create_midi_capture_session.")

        try:
            # MidiRecorder's constructor creates a DB entry.
            # It should handle its own commit/rollback for that entry using the passed session.
            recorder = MidiRecorder(
                project_id=self.project_id,
                selected_device_names=selected_device_names,
                session_name=session_name,
                db=_db_to_use, # Pass the resolved session to MidiRecorder
            )
            logger.info(
                f"Successfully initialized MidiRecorder for session '{session_name}'."
            )
            # If MidiRecorder commits, and _db_to_use is self.db, that commit happens on the external session.
            # This is generally acceptable as the method name implies creation.
            return recorder
        except Exception as e: # Includes SQLAlchemyError from MidiRecorder
            logger.error(
                f"Error creating MIDI capture session '{session_name}' in Project: {e}",
                exc_info=True,
            )
            # MidiRecorder should handle its own rollback on error during its init.
            # If an error occurs here, the state of _db_to_use might depend on MidiRecorder's actions.
            raise
        finally:
            if _manage_session_locally and db_gen_local:
                try:
                    next(db_gen_local, None)
                    logger.debug("Closed locally managed session for create_midi_capture_session.")
                except StopIteration:
                    pass

    def list_midi_capture_sessions(self) -> List[MidiCaptureSessionModel]:
        """
        Lists all MIDI capture sessions associated with the current project.

        Returns:
            List[MidiCaptureSessionModel]: A list of `MidiCaptureSessionModel` instances,
                                           ordered by creation date (most recent first).

        Raises:
            SQLAlchemyError: If there's an issue communicating with the database.
        """
        logger.debug(
            f"Listing MIDI capture sessions for project ID {self.project_id}."
        )

        _db_to_use = self.db
        _manage_session_locally = False
        db_gen_local = None

        if _db_to_use is None:
            logger.debug("No self.db session, creating local session for list_midi_capture_sessions.")
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            logger.debug("Using self.db session for list_midi_capture_sessions.")

        try:
            sessions = (
                _db_to_use.query(MidiCaptureSessionModel)
                .filter(MidiCaptureSessionModel.project_id == self.project_id)
                .order_by(MidiCaptureSessionModel.created_at.desc())
                .all()
            )
            logger.debug(
                f"Found {
                    len(sessions)} MIDI capture sessions for project ID {
                    self.project_id}.")
            return sessions
        except SQLAlchemyError as e:
            logger.error(
                f"Database error listing MIDI capture sessions for project ID {self.project_id}: {e}"
            )
            raise
        finally:
            if _manage_session_locally and db_gen_local:
                try:
                    next(db_gen_local, None)
                    logger.debug("Closed locally managed session for list_midi_capture_sessions.")
                except StopIteration:
                    pass

    def get_midi_capture_session(
        self, session_id: int
    ) -> MidiCaptureSessionModel | None:
        """
        Retrieves a specific MIDI capture session by its ID.

        Ensures that the retrieved session belongs to the current project.

        Args:
            session_id (int): The ID of the MIDI capture session to retrieve.

        Returns:
            MidiCaptureSessionModel | None: The `MidiCaptureSessionModel` instance
                                             if found and belonging to this project,
                                             otherwise `None`.

        Raises:
            SQLAlchemyError: If there's an issue communicating with the database.
        """
        logger.debug(
            f"Retrieving MIDI capture session ID {session_id} for project ID {self.project_id}."
        )

        _db_to_use = self.db
        _manage_session_locally = False
        db_gen_local = None

        if _db_to_use is None:
            logger.debug("No self.db session, creating local session for get_midi_capture_session.")
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            logger.debug("Using self.db session for get_midi_capture_session.")

        try:
            session = (
                _db_to_use.query(MidiCaptureSessionModel)
                .filter(
                    MidiCaptureSessionModel.id == session_id,
                    MidiCaptureSessionModel.project_id == self.project_id,
                )
                .first()
            )
            if session:
                logger.debug(f"Found MIDI capture session: {session.name}")
            else:
                logger.debug(
                    f"MIDI capture session ID {session_id} not found for project ID {
                        self.project_id}.")
            return session
        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving MIDI capture session ID {session_id}: {e}"
            )
            raise
        finally:
            if _manage_session_locally and db_gen_local:
                try:
                    next(db_gen_local, None)
                    logger.debug("Closed locally managed session for get_midi_capture_session.")
                except StopIteration:
                    pass

    def get_midi_files_for_session(
            self, session_id: int) -> List[MidiFileModel]:
        """
        Retrieves all MIDI data entries associated with a specific MIDI capture session.

        This method first verifies that the session belongs to the current project.
        The returned `MidiFileModel` instances will contain the raw MIDI data
        in their `midi_data` attribute.

        Args:
            session_id (int): The ID of the MIDI capture session whose MIDI data entries
                              are to be retrieved.

        Returns:
            List[MidiFileModel]: A list of `MidiFileModel` instances, each representing
                                  a stored MIDI recording (containing binary MIDI data).
                                  The list is ordered by creation date (oldest first).
                                  Returns an empty list if the session is not found,
                                  does not belong to this project, or has no associated MIDI data.

        Raises:
            SQLAlchemyError: If there's an issue communicating with the database.
        """
        logger.debug(
            f"Retrieving MIDI files for session ID {session_id} (project ID {self.project_id})."
        )

        _db_to_use = self.db
        _manage_session_locally = False
        db_gen_local = None

        if _db_to_use is None:
            logger.debug("No self.db session, creating local session for get_midi_files_for_session.")
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            logger.debug("Using self.db session for get_midi_files_for_session.")

        try:
            capture_session = (
                _db_to_use.query(MidiCaptureSessionModel)
                .filter(
                    MidiCaptureSessionModel.id == session_id,
                    MidiCaptureSessionModel.project_id == self.project_id,
                )
                .first()
            )

            if not capture_session:
                logger.warning(
                    f"MIDI capture session ID {session_id} not found or does not belong to project ID {
                        self.project_id}.")
                return []

            midi_files = (
                _db_to_use.query(MidiFileModel)
                .filter(MidiFileModel.midi_capture_session_id == session_id)
                .order_by(MidiFileModel.created_at.asc())
                .all()
            )
            logger.debug(
                f"Found {len(midi_files)} MIDI files for session ID {session_id}."
            )
            return midi_files
        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving MIDI files for session ID {session_id}: {e}"
            )
            raise
        finally:
            if _manage_session_locally and db_gen_local:
                try:
                    next(db_gen_local, None)
                    logger.debug("Closed locally managed session for get_midi_files_for_session.")
                except StopIteration:
                    pass
