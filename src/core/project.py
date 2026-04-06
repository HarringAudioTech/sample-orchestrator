import os

# import wave # Removed
import logging  # Added logging
from typing import List, Optional, Generator
from sqlalchemy.orm import Session  # Added Session for type hints
from sqlalchemy.exc import SQLAlchemyError
from src.database.models import ProjectModel, RecordingModel, SampleModel, MidiDeviceModel, MidiCaptureSessionModel, MidiFileModel  # Added model imports
from src.database.utils import get_db  # Import get_db function
from src.core.midi_capture import (
    MidiRecorder,
    list_available_midi_devices,
)

# Configure basic logging
# In a larger application, this would likely be configured in a central place.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class Project:
    """
    Manages operations related to a specific project.

    This includes handling audio recordings (adding, listing, processing) and
    MIDI capture sessions (listing devices, creating sessions, listing sessions and files).
    Each instance of this class is tied to a specific project existing in the database.

    Attributes:
        project_id: The ID of the project this instance manages.
        project_model: The SQLAlchemy model instance for this project,
                       loaded from the database during initialization.
        db: Optional SQLAlchemy session passed during initialization.
    """

    def __init__(self, project_id: int, db_session: Optional[Session] = None) -> None:
        """Initializes a Project instance, establishing a context for project-specific operations.

        This constructor fetches the project's metadata from the database using
        the provided `project_id`. It allows for an optional existing SQLAlchemy
        `db_session` to be passed; if none is provided, it will create and manage
        a new session for the duration of its own execution. The loaded
        `ProjectModel` instance is stored as `self.project_model`.

        Args:
            project_id (int): The unique identifier for the project to be loaded
                              and managed by this instance.
            db_session (Optional[Session]): An existing SQLAlchemy database session.
                If provided, this session will be used for database operations
                performed during initialization. If `None`, a new session will be
                obtained from `get_db()` and used locally, then closed upon
                completion of this method.

        Raises:
            ValueError: If no project exists in the database with the specified
                        `project_id`.
            SQLAlchemyError: If any error occurs during database communication
                             (e.g., while querying for the project).
        """
        logger.info(f"Initializing Project core for project_id: {project_id}")
        self.db: Session | None = db_session  # Store the provided session, if any
        self.project_id: int = project_id
        self.project_model: ProjectModel

        _db_to_use: Session
        _manage_session_locally: bool = False
        db_gen: Optional[Generator[Session, None, None]] = None  # Initialize db_gen to None

        if self.db:
            _db_to_use = self.db
            logger.debug("Using provided db_session for Project initialization.")
        else:
            logger.debug(
                "No db_session provided, creating local session for Project initialization."
            )
            # Use get_db as a context manager
            with get_db() as session:
                _db_to_use = session
                _manage_session_locally = False  # No need to manage session as context manager handles it
                
                # Fetch the project within the context manager
                self.project_model = _db_to_use.query(ProjectModel).filter(ProjectModel.id == project_id).first()
                
                if not self.project_model:
                    raise ValueError(f"No project found with ID {project_id}")
                
                logger.info(f"Successfully loaded project: {self.project_model.name} (ID: {project_id})")
                return  # Exit the method early as we've completed our work within the context manager

        # This code only runs if we're using a provided session (not our own context manager)
        if self.db:  # Only execute this block if we're using a provided session
            try:
                project_model: ProjectModel | None = (
                    _db_to_use.query(ProjectModel).filter(ProjectModel.id == project_id).first()
                )
                if not project_model:
                    logger.error(f"Project with id {project_id} not found in database.")
                    raise ValueError(f"Project with id {project_id} not found")
                self.project_model = project_model
                logger.info(
                    f"Successfully initialized Project core for project: {self.project_model.name}"
                )
            except SQLAlchemyError as e:
                logger.error(
                    f"Database error during Project initialization for project_id {project_id}: {e}"
                )
                raise

    def add_recording(self, file_path: str, name: str) -> RecordingModel:
        """Adds a new audio recording to this project.

        This method processes a new audio file, extracts its metadata (duration,
        sample rate, channels) using `librosa`, and then creates a corresponding
        `RecordingModel` entry in the database, associating it with the current
        project.

        If `self.db` (the instance's database session) is `None`, a new session
        is created for this operation and closed upon completion. Otherwise, the
        existing `self.db` session is used.

        Args:
            file_path (str): The absolute or relative path to the audio file
                             (e.g., ".wav", ".mp3").
            name (str): A user-friendly name to assign to this recording within
                        the project (e.g., "Vocal Take 1").

        Returns:
            RecordingModel: The SQLAlchemy `RecordingModel` instance representing
                            the newly added recording, including its generated ID
                            and extracted metadata.

        Raises:
            FileNotFoundError: If the audio file specified by `file_path` does
                               not exist or is not accessible.
            SQLAlchemyError: If any error occurs during database operations (e.g.,
                             adding the new recording, committing the session).
            Exception: Propagates exceptions from `librosa` if audio metadata
                       extraction fails (e.g., due to an unsupported file format
                       or corrupted file). Errors during metadata extraction are
                       logged, and the recording may still be added with minimal
                       or no metadata.
        """
        logger.info(
            f"Adding recording '{name}' from path '{file_path}' to project ID {self.project_id}."
        )

        _db_to_use: Session
        _manage_session_locally: bool = False
        db_gen_local: Optional[Generator[Session, None, None]] = None

        if self.db is None:
            logger.debug("No self.db session, creating local session for add_recording.")
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            _db_to_use = self.db
            logger.debug("Using self.db session for add_recording.")

        try:
            if not os.path.exists(file_path):
                logger.error(f"Recording file not found: {file_path}")
                raise FileNotFoundError(f"Recording file not found: {file_path}")

            duration_seconds: float | None = None
            samplerate: int | None = None
            channels: int | None = None
            # total_frames: int | None = None # Optional

            try:
                # Load the full audio primarily to get its properties.
                # sr=None ensures loading at native sample rate.
                y: np.ndarray
                sr_librosa: int
                y, sr_librosa = librosa.load(  # type: ignore
                    file_path, sr=None, mono=False
                )  # mono=False to get actual channels

                samplerate = sr_librosa
                duration_seconds = librosa.get_duration(y=y, sr=samplerate)

                if y.ndim == 1:
                    channels = 1
                else:
                    channels = y.shape[
                        0
                    ]  # For multi-channel, librosa loads as (channels, samples)

                # total_frames = len(y) if y.ndim == 1 else y.shape[1]

                logger.info(
                    f"Extracted metadata using librosa for {file_path}: SR={samplerate}, Duration={duration_seconds}s, Channels={channels}"
                )

            except Exception as e:
                logger.error(
                    f"Error getting audio properties for {file_path} using librosa: {e}. "
                    "Recording will be added with minimal or no metadata.",
                    exc_info=True,
                )

            filesize: int | None = None
            try:
                filesize = os.path.getsize(file_path)
                logger.info(f"Retrieved file size for {file_path}: {filesize} bytes")
            except OSError as e:
                logger.error(f"Could not get file size for {file_path}: {e}. Recording will be added without filesize.", exc_info=True)


            new_recording: RecordingModel = RecordingModel(
                name=name,
                file_path=file_path,
                file_size_bytes=filesize,
                duration_seconds=duration_seconds,
                sample_rate=samplerate,
                channels=channels,
                status="uploaded",
            )
            # Add the recording to the project using the many-to-many relationship
            self.project_model.recordings.append(new_recording)
            _db_to_use.add(new_recording)
            _db_to_use.commit()
            _db_to_use.refresh(new_recording)
            logger.info(
                f"Successfully added recording '{new_recording.name}' with ID {new_recording.id}."
            )
            return new_recording
        except SQLAlchemyError as e:
            if _db_to_use:  # Check if session was successfully obtained before rollback
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

    def get_recording(self, recording_id: int) -> Optional[RecordingModel]:
        """Retrieves a specific recording by its ID, ensuring it belongs to this project.

        This method queries the database for a `RecordingModel` that matches both
        the provided `recording_id` and the `self.project_id` of this `Project`
        instance.

        If `self.db` (the instance's database session) is `None`, a new session
        is created for this operation and closed upon completion. Otherwise, the
        existing `self.db` session is used.

        Args:
            recording_id (int): The unique identifier of the recording to retrieve.

        Returns:
            Optional[RecordingModel]: The `RecordingModel` instance if a recording
                                      with the specified ID is found and is part of
                                      the current project. Returns `None` otherwise.

        Raises:
            SQLAlchemyError: If an error occurs during database communication.
        """
        logger.debug(
            f"Retrieving recording ID {recording_id} for project ID {self.project_id}."
        )

        _db_to_use: Session
        _manage_session_locally: bool = False
        db_gen_local: Optional[Generator[Session, None, None]] = None

        if self.db is None:
            logger.debug("No self.db session, creating local session for get_recording.")
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            _db_to_use = self.db
            logger.debug("Using self.db session for get_recording.")

        try:
            # Query for the recording by ID first
            recording: RecordingModel | None = (
                _db_to_use.query(RecordingModel)
                .filter(RecordingModel.id == recording_id)
                .first()
            )
            
            # Check if the recording belongs to this project using the many-to-many relationship
            if recording and self.project_model not in recording.projects:
                logger.debug(
                    f"Recording ID {recording_id} found but does not belong to project ID {self.project_id}."
                )
                recording = None
            if recording:
                logger.debug(f"Found recording: {recording.name}")
            else:
                logger.debug(
                    f"Recording ID {recording_id} not found for project ID {self.project_id}."
                )
            return recording
        except SQLAlchemyError as e:
            logger.error(f"Database error retrieving recording ID {recording_id}: {e}")
            raise
        finally:
            if _manage_session_locally and db_gen_local:
                try:
                    next(db_gen_local, None)
                    logger.debug("Closed locally managed session for get_recording.")
                except StopIteration:
                    pass

    def list_recordings(self) -> list[RecordingModel]:
        """Lists all audio recordings associated with the current project.

        This method queries the database for all `RecordingModel` entries that
        are linked to `self.project_id`. The results are ordered by their
        creation timestamp in descending order (newest first).

        If `self.db` (the instance's database session) is `None`, a new session
        is created for this operation and closed upon completion. Otherwise, the
        existing `self.db` session is used.

        Args:
            None.

        Returns:
            list[RecordingModel]: A list of `RecordingModel` SQLAlchemy instances.
                                  If no recordings are found for the project, an
                                  empty list is returned.

        Raises:
            SQLAlchemyError: If an error occurs during database communication.
        """
        logger.debug(f"Listing all recordings for project ID {self.project_id}.")

        _db_to_use: Session
        _manage_session_locally: bool = False
        db_gen_local: Optional[Generator[Session, None, None]] = None

        if self.db is None:
            logger.debug("No self.db session, creating local session for list_recordings.")
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            _db_to_use = self.db
            logger.debug("Using self.db session for list_recordings.")

        try:
            # Use the relationship defined in the project model to get all recordings
            recordings: List[RecordingModel] = self.project_model.recordings
            logger.debug(
                f"Found {len(recordings)} recordings for project ID {self.project_id}."
            )
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
        """Initiates audio processing for a specific recording (currently not implemented).

        This method is intended to handle the processing of an audio recording,
        such as slicing it into samples. However, it currently raises a
        `NotImplementedError` as it needs to be refactored to use the
        new `SlicingStage` via the stage runner system.

        The original implementation involved ensuring the `output_sample_dir`
        exists and then calling a (now deprecated) processing function.
        A pre-check was performed to ensure the recording belonged to the project.

        Args:
            recording_id (int): The ID of the recording to process.
            output_sample_dir (str): The path where processed samples (e.g., slices)
                                     were intended to be saved.

        Raises:
            NotImplementedError: This method always raises this error, indicating
                                 it requires an update.
            SQLAlchemyError: (Historical) Would have been raised if database
                             interaction failed during the pre-check.
            Exception: (Historical) Could have re-raised exceptions from audio
                       processing.
        """
        logger.info(
            f"Initiating processing for recording ID {recording_id} in project {self.project_id}."
        )
        # TODO: Refactor this method to use the new SlicingStage via
        # stage_runner.
        raise NotImplementedError(
            "This processing method needs to be updated to use SlicingStage"
        )

        try:
            os.makedirs(output_sample_dir, exist_ok=True)
            logger.debug(f"Ensured output directory exists: {output_sample_dir}")
        except OSError as e:
            logger.error(
                f"Error creating output directory {output_sample_dir}: {e}. Processing aborted."
            )
            return  # Or raise custom error

        _db_to_use: Session
        _manage_session_locally: bool = False
        db_gen_local: Optional[Generator[Session, None, None]] = None

        if self.db is None:
            logger.debug(
                "No self.db session, creating local session for process_recording pre-check."
            )
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            _db_to_use = self.db
            logger.debug("Using self.db session for process_recording pre-check.")

        try:
            # The following is part of the original method's pre-check logic
            recording: RecordingModel | None = (
                _db_to_use.query(RecordingModel)
                .filter(
                    RecordingModel.id == recording_id,
                    RecordingModel.project_id == self.project_id,
                )
                .first()
            )

            if not recording:
                # Commenting out the problematic logger.warning line
                # logger.warning(
                #     f"Recording ID {recording_id} not found for project {self.project_id}. Processing aborted."
                # )
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
                f"Database error in process_recording pre-check for recording {recording_id}: {e}"
            )
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
                    logger.debug(
                        "Closed locally managed session for process_recording pre-check."
                    )
                except StopIteration:
                    pass
            # Note: The original db_processing_session.close() is removed as we now use _db_to_use
            # which is managed by the common finally block if created locally.
            # If self.db was used, it's not closed here.

    # --- MIDI Capture Related Methods ---

    def list_midi_devices(self) -> List[MidiDeviceModel]:
        """Lists available MIDI input devices and synchronizes them with the database.

        This method acts as a wrapper around `midi_capture.list_available_midi_devices`.
        It facilitates the discovery of MIDI input devices connected to the system
        (using the `mido` library) and ensures that these devices are represented
        in the database. If a device is newly discovered, it's added; if it
        already exists, its record might be updated (e.g., timestamp).

        If `self.db` (the instance's database session) is `None`, a new session
        is created for this operation and passed to the underlying function, then
        closed upon completion. Otherwise, the existing `self.db` session is used.

        Args:
            None.

        Returns:
            List[MidiDeviceModel]: A list of `MidiDeviceModel` SQLAlchemy
                                   instances, representing all MIDI input devices
                                   currently detected and synchronized with the
                                   database.

        Raises:
            SQLAlchemyError: If any database operations fail within the underlying
                             `list_available_midi_devices` function (e.g., during
                             querying, adding, or committing device records).
            Exception: If `mido` library calls to get input device names fail, or
                       for other unexpected errors propagated from the underlying
                       function.
        """
        logger.info(f"Listing MIDI devices for project ID {self.project_id}.")

        _db_to_use: Session
        _manage_session_locally: bool = False
        db_gen_local: Optional[Generator[Session, None, None]] = None

        if self.db is None:
            logger.debug("No self.db session, creating local session for list_midi_devices.")
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            _db_to_use = self.db
            logger.debug("Using self.db session for list_midi_devices.")

        try:
            # list_available_midi_devices itself handles DB operations, so pass the session to it.
            devices: List[MidiDeviceModel] = list_available_midi_devices(_db_to_use)
            logger.info(f"Found {len(devices)} MIDI devices.")
            return devices
        except Exception as e:  # Includes SQLAlchemyError from list_available_midi_devices
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
        """Initializes and returns a `MidiRecorder` for a new MIDI capture session.

        This method facilitates the creation of a new MIDI capture session.
        It instantiates a `MidiRecorder` object, which in turn creates a
        `MidiCaptureSessionModel` entry in the database.

        If `self.db` (the instance's database session) is `None`, a new session
        is created and passed to the `MidiRecorder` constructor for its
        initialization, and then this session is closed. If `self.db` is an
        existing session, it is used by the `MidiRecorder`. The `MidiRecorder`
        is expected to handle its own database commit/rollback for the session
        creation within its constructor.

        Note: The returned `MidiRecorder` instance is now ready to be used for
        recording (via its `start_recording` and `stop_recording` methods).
        The caller will need to manage database sessions for those subsequent
        operations on the `MidiRecorder` if `self.db` was not provided here.

        Args:
            session_name (str): A user-defined, descriptive name for the new
                                MIDI capture session (e.g., "Keyboard Part").
            selected_device_names (list[str]): A list of names of the MIDI input
                devices to be used for this capture session. These device names
                should correspond to existing `MidiDeviceModel` entries in the
                database, typically discovered via `list_midi_devices()`.

        Returns:
            MidiRecorder: An instance of the `MidiRecorder` class, configured and
                          ready for this new capture session. The associated
                          `MidiCaptureSessionModel` has been created in the database.

        Raises:
            ValueError: Propagated from `MidiRecorder.__init__` if the current
                        project ID (`self.project_id`) is invalid, if
                        `selected_device_names` is empty, or if no valid MIDI
                        devices are found in the database matching the provided names.
            SQLAlchemyError: Propagated from `MidiRecorder.__init__` if database
                             operations fail during the creation of the
                             `MidiCaptureSessionModel`.
            Exception: For other unexpected errors during `MidiRecorder` instantiation.
        """
        logger.info(
            f"Creating MIDI capture session '{session_name}' for project ID {self.project_id} "
            f"with devices: {selected_device_names}"
        )

        _db_to_use: Session
        _manage_session_locally: bool = False
        db_gen_local: Optional[Generator[Session, None, None]] = None

        if self.db is None:
            logger.debug(
                "No self.db session, creating local session for create_midi_capture_session."
            )
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            _db_to_use = self.db
            logger.debug("Using self.db session for create_midi_capture_session.")

        try:
            # MidiRecorder's constructor creates a DB entry.
            # It should handle its own commit/rollback for that entry using the passed session.
            recorder: MidiRecorder = MidiRecorder(
                project_id=self.project_id,
                selected_device_names=selected_device_names,
                session_name=session_name,
                db=_db_to_use,  # Pass the resolved session to MidiRecorder
            )
            logger.info(f"Successfully initialized MidiRecorder for session '{session_name}'.")
            # If MidiRecorder commits, and _db_to_use is self.db, that commit happens on the external session.
            # This is generally acceptable as the method name implies creation.
            return recorder
        except Exception as e:  # Includes SQLAlchemyError from MidiRecorder
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
                    logger.debug(
                        "Closed locally managed session for create_midi_capture_session."
                    )
                except StopIteration:
                    pass

    def list_midi_capture_sessions(self) -> List[MidiCaptureSessionModel]:
        """Lists all MIDI capture sessions associated with the current project.

        This method queries the database for all `MidiCaptureSessionModel`
        entries that are linked to the `self.project_id` of this `Project`
        instance. The results are ordered by their creation timestamp in
        descending order, meaning the most recently created sessions appear first.

        If `self.db` (the instance's database session) is `None`, a new session
        is created for this operation and closed upon completion. Otherwise, the
        existing `self.db` session is used.

        Args:
            None.

        Returns:
            List[MidiCaptureSessionModel]: A list of `MidiCaptureSessionModel`
                SQLAlchemy instances. If no MIDI capture sessions are found for
                the project, an empty list is returned.

        Raises:
            SQLAlchemyError: If an error occurs during database communication.
        """
        logger.debug(f"Listing MIDI capture sessions for project ID {self.project_id}.")

        _db_to_use: Session
        _manage_session_locally: bool = False
        db_gen_local: Optional[Generator[Session, None, None]] = None

        if self.db is None:
            logger.debug(
                "No self.db session, creating local session for list_midi_capture_sessions."
            )
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            _db_to_use = self.db
            logger.debug("Using self.db session for list_midi_capture_sessions.")

        try:
            sessions: List[MidiCaptureSessionModel] = (
                _db_to_use.query(MidiCaptureSessionModel)
                .filter(MidiCaptureSessionModel.project_id == self.project_id)
                .order_by(MidiCaptureSessionModel.created_at.desc())
                .all()
            )
            logger.debug(
                f"Found {len(sessions)} MIDI capture sessions for project ID {self.project_id}."
            )
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
                    logger.debug(
                        "Closed locally managed session for list_midi_capture_sessions."
                    )
                except StopIteration:
                    pass

    def get_midi_capture_session(self, session_id: int) -> Optional[MidiCaptureSessionModel]:
        """Retrieves a specific MIDI capture session by ID, ensuring it belongs to this project.

        This method queries the database for a `MidiCaptureSessionModel` that
        matches both the provided `session_id` and the `self.project_id` of this
        `Project` instance.

        If `self.db` (the instance's database session) is `None`, a new session
        is created for this operation and closed upon completion. Otherwise, the
        existing `self.db` session is used.

        Args:
            session_id (int): The unique identifier of the MIDI capture session
                              to retrieve.

        Returns:
            Optional[MidiCaptureSessionModel]: The `MidiCaptureSessionModel`
                SQLAlchemy instance if a session with the specified ID is found
                and is part of the current project. Returns `None` otherwise.

        Raises:
            SQLAlchemyError: If an error occurs during database communication.
        """
        logger.debug(
            f"Retrieving MIDI capture session ID {session_id} for project ID {self.project_id}."
        )

        _db_to_use: Session
        _manage_session_locally: bool = False
        db_gen_local: Optional[Generator[Session, None, None]] = None

        if self.db is None:
            logger.debug(
                "No self.db session, creating local session for get_midi_capture_session."
            )
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            _db_to_use = self.db
            logger.debug("Using self.db session for get_midi_capture_session.")

        try:
            session: MidiCaptureSessionModel | None = (
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
                    f"MIDI capture session ID {session_id} not found for project ID {self.project_id}."
                )
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
                    logger.debug(
                        "Closed locally managed session for get_midi_capture_session."
                    )
                except StopIteration:
                    pass

    def get_midi_files_for_session(self, session_id: int) -> List[MidiFileModel]:
        """Retrieves all MIDI data files associated with a specific MIDI capture session.

        This method performs two main database queries:
        1. It first retrieves the `MidiCaptureSessionModel` for the given `session_id`,
           ensuring that this session belongs to the current project (`self.project_id`).
           If the session is not found or does not belong to this project, an
           empty list is returned.
        2. If the session is validated, it then queries for all `MidiFileModel`
           entries that are linked to this `session_id`. These are ordered by
           their creation timestamp in ascending order (oldest first).

        Each returned `MidiFileModel` instance contains the actual MIDI data as a
        binary blob in its `midi_data` attribute.

        If `self.db` (the instance's database session) is `None`, a new session
        is created for these operations and closed upon completion. Otherwise, the
        existing `self.db` session is used.

        Args:
            session_id (int): The unique identifier of the MIDI capture session
                              for which to retrieve associated MIDI files.

        Returns:
            List[MidiFileModel]: A list of `MidiFileModel` SQLAlchemy instances.
                Each instance corresponds to a MIDI file recorded during the
                specified session and contains the binary MIDI data. Returns an
                empty list if the session is invalid (not found or not part of
                this project) or if the session has no MIDI files associated with it.

        Raises:
            SQLAlchemyError: If an error occurs during database communication.
        """
        logger.debug(
            f"Retrieving MIDI files for session ID {session_id} (project ID {self.project_id})."
        )

        _db_to_use: Session
        _manage_session_locally: bool = False
        db_gen_local: Optional[Generator[Session, None, None]] = None

        if self.db is None:
            logger.debug(
                "No self.db session, creating local session for get_midi_files_for_session."
            )
            db_gen_local = get_db()
            _db_to_use = next(db_gen_local)
            _manage_session_locally = True
        else:
            _db_to_use = self.db
            logger.debug("Using self.db session for get_midi_files_for_session.")

        try:
            capture_session: MidiCaptureSessionModel | None = (
                _db_to_use.query(MidiCaptureSessionModel)
                .filter(
                    MidiCaptureSessionModel.id == session_id,
                    MidiCaptureSessionModel.project_id == self.project_id,
                )
                .first()
            )

            if not capture_session:
                logger.warning(
                    f"MIDI capture session ID {session_id} not found or does not belong to project ID {self.project_id}."
                )
                return []

            midi_files: List[MidiFileModel] = (
                _db_to_use.query(MidiFileModel)
                .filter(MidiFileModel.capture_session_id == session_id)
                .order_by(MidiFileModel.created_at.asc())
                .all()
            )
            logger.debug(f"Found {len(midi_files)} MIDI files for session ID {session_id}.")
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
                    logger.debug(
                        "Closed locally managed session for get_midi_files_for_session."
                    )
                except StopIteration:
                    pass
