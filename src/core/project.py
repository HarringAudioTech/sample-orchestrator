import os
import wave
import logging  # Added logging
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError  # To catch DB errors specifically
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
from aubio import (
    source,
)

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

    def __init__(self, project_id: int):
        """
        Initializes a Project instance by loading its data from the database.

        Args:
            project_id (int): The ID of the project to load.

        Raises:
            ValueError: If no project with the given `project_id` is found.
            SQLAlchemyError: If there's an issue communicating with the database.
        """
        logger.info(f"Initializing Project core for project_id: {project_id}")
        # Uses a new session that is closed after loading.
        # Consider if this session should be managed by the caller or be longer-lived
        # if multiple operations are performed on the Project instance.
        # For now, __init__ uses its own short-lived session.
        db_gen = get_db()  # get_db() should ideally be configurable for test/prod
        db: Session = next(db_gen)
        try:
            project_model = (
                db.query(ProjectModel).filter(
                    ProjectModel.id == project_id).first())
            if not project_model:
                logger.error(
                    f"Project with id {project_id} not found in database.")
                raise ValueError(f"Project with id {project_id} not found")
            self.project_model = project_model
            self.project_id = project_id
            logger.info(
                f"Successfully initialized Project core for project: {
                    self.project_model.name}")
        except SQLAlchemyError as e:
            logger.error(
                f"Database error during Project initialization for project_id {project_id}: {e}")
            raise
        finally:
            try:
                # Ensure generator is exhausted and session closed
                next(db_gen, None)
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
            f"Adding recording '{name}' from path '{file_path}' to project ID {
                self.project_id}.")
        db: Session = SessionLocal()
        try:
            if not os.path.exists(file_path):
                logger.error(f"Recording file not found: {file_path}")
                raise FileNotFoundError(
                    f"Recording file not found: {file_path}")

            duration_seconds = None
            samplerate = None
            channels = None

            try:
                s = source(file_path, 0, 512)
                samplerate = s.samplerate
                with wave.open(file_path, "rb") as wf:
                    frames = wf.getnframes()
                    rate_wave = wf.getframerate()
                    duration_seconds = frames / float(rate_wave)
                    channels = wf.getnchannels()
                    if samplerate == 0:
                        samplerate = rate_wave
                    elif samplerate != rate_wave:
                        logger.warning(
                            f"Aubio samplerate {samplerate} and wave module samplerate {rate_wave} "
                            f"differ for {file_path}. Using aubio's."
                        )
            except Exception as e:
                logger.error(
                    f"Error getting audio properties for {file_path}: {e}. "
                    "Recording will be added with available metadata.",
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
            db.add(new_recording)
            db.commit()
            db.refresh(new_recording)
            logger.info(
                f"Successfully added recording '{
                    new_recording.name}' with ID {
                    new_recording.id}.")
            return new_recording
        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error adding recording '{name}': {e}")
            raise
        finally:
            db.close()

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
            f"Retrieving recording ID {recording_id} for project ID {
                self.project_id}.")
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
            if recording:
                logger.debug(f"Found recording: {recording.name}")
            else:
                logger.debug(
                    f"Recording ID {recording_id} not found for project ID {
                        self.project_id}.")
            return recording
        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving recording ID {recording_id}: {e}")
            raise
        finally:
            try:
                next(db_gen, None)
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
            f"Listing all recordings for project ID {
                self.project_id}.")
        db_gen = get_db()
        db: Session = next(db_gen)
        try:
            recordings = (
                db.query(RecordingModel)
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
                f"Database error listing recordings for project ID {
                    self.project_id}: {e}")
            raise
        finally:
            try:
                next(db_gen, None)
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

        db_processing_session = SessionLocal()
        try:
            recording = (
                db_processing_session.query(RecordingModel)
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
            db_processing_session.close()

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
        db: Session = SessionLocal()
        try:
            devices = list_available_midi_devices(db)
            logger.info(f"Found {len(devices)} MIDI devices.")
            return devices
        except Exception as e:
            logger.error(
                f"Error listing MIDI devices in Project.list_midi_devices: {e}",
                exc_info=True,
            )
            raise
        finally:
            db.close()

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
            f"Creating MIDI capture session '{session_name}' for project ID {
                self.project_id} " f"with devices: {selected_device_names}")
        db: Session = SessionLocal()
        try:
            recorder = MidiRecorder(
                project_id=self.project_id,
                selected_device_names=selected_device_names,
                session_name=session_name,
                db=db,
            )
            logger.info(
                f"Successfully initialized MidiRecorder for session '{session_name}'.")
            return recorder
        except Exception as e:
            logger.error(
                f"Error creating MIDI capture session '{session_name}' in Project: {e}",
                exc_info=True,
            )
            raise
        finally:
            db.close()

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
            f"Listing MIDI capture sessions for project ID {
                self.project_id}.")
        db: Session = SessionLocal()
        try:
            sessions = (
                db.query(MidiCaptureSessionModel)
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
                f"Database error listing MIDI capture sessions for project ID {
                    self.project_id}: {e}")
            raise
        finally:
            db.close()

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
            f"Retrieving MIDI capture session ID {session_id} for project ID {
                self.project_id}.")
        db: Session = SessionLocal()
        try:
            session = (
                db.query(MidiCaptureSessionModel)
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
                f"Database error retrieving MIDI capture session ID {session_id}: {e}")
            raise
        finally:
            db.close()

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
            f"Retrieving MIDI files for session ID {session_id} (project ID {
                self.project_id}).")
        db: Session = SessionLocal()
        try:
            capture_session = (
                db.query(MidiCaptureSessionModel)
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
                db.query(MidiFileModel)
                .filter(MidiFileModel.midi_capture_session_id == session_id)
                .order_by(MidiFileModel.created_at.asc())
                .all()
            )
            logger.debug(
                f"Found {
                    len(midi_files)} MIDI files for session ID {session_id}.")
            return midi_files
        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving MIDI files for session ID {session_id}: {e}")
            raise
        finally:
            db.close()
