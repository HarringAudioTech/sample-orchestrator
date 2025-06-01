import os
import datetime
import re
import mido
import logging  # Added logging
import io  # Added io
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from src.database.models import (
    Project as ProjectModel,
    MidiDevice,
    MidiCaptureSession,
    MidiFile,
)
from src.database.utils import (
    get_db,
)  # Removed SessionLocal, get_db is not used directly here but aligns imports

# Configure basic logging
# In a larger application, this would likely be configured in a central place.
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def sanitize_filename(name: str) -> str:
    """
    Sanitizes a string to be used as a filename or directory name.

    Replaces spaces with underscores and removes characters that are generally
    problematic for filesystems (keeps alphanumeric, underscore, dot, hyphen).

    Args:
        name (str): The input string to sanitize.

    Returns:
        str: The sanitized string suitable for use as a filename.
    """
    name = name.replace(" ", "_")
    name = re.sub(r"[^\w\.-]", "", name)
    return name


def list_available_midi_devices(db: Session) -> list[MidiDevice]:
    """
    Lists available MIDI input devices detected by `mido`.

    Synchronizes these devices with the database. If a detected device
    is not in the database, it's added. If it exists, its `updated_at`
    timestamp is modified.

    Args:
        db: The SQLAlchemy database session.

    Returns:
        A list of `MidiDevice` SQLAlchemy model instances,
        reflecting all currently available MIDI input devices.

    Raises:
        SQLAlchemyError: If there's an issue committing changes to the database.
        Exception: If `mido.get_input_names()` or other operations fail.
    """
    logger.info("Listing available MIDI devices.")
    try:
        device_names: list[str] = mido.get_input_names()
    except Exception as e:
        logger.error(f"Error getting MIDI input names from mido: {e}")
        raise

    found_or_created_devices: list[MidiDevice] = []

    try:
        for name in device_names:
            device: MidiDevice | None = db.query(MidiDevice).filter(MidiDevice.name == name).first()
            if device:
                logger.debug(f"MIDI device '{name}' found in database. Updating timestamp.")
                device.updated_at = datetime.datetime.utcnow()
                db.add(device)
            else:
                logger.info(f"New MIDI device '{name}' detected. Adding to database.")
                # Assuming name can serve as a basic system_identifier
                # initially
                device = MidiDevice(name=name, system_identifier=name)
                db.add(device)
            found_or_created_devices.append(device)

        db.commit()
        logger.info(
            f"Successfully synchronized {
                len(found_or_created_devices)} MIDI devices with the database."
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error while synchronizing MIDI devices: {e}")
        raise
    except Exception as e:
        db.rollback()  # Rollback on other errors too for safety with DB state
        logger.error(f"Unexpected error listing or saving MIDI devices: {e}")
        raise

    return found_or_created_devices


def get_midi_device_by_name(db: Session, name: str) -> MidiDevice | None:
    """
    Retrieves a `MidiDevice` from the database by its name.

    Args:
        db: The SQLAlchemy database session.
        name: The name of the MIDI device to retrieve.

    Returns:
        The `MidiDevice` SQLAlchemy model instance if found,
        otherwise `None`.

    Raises:
        SQLAlchemyError: If a database query error occurs.
    """
    logger.debug(f"Querying for MIDI device by name: '{name}'")
    try:
        device: MidiDevice | None = db.query(MidiDevice).filter(MidiDevice.name == name).first()
        return device
    except SQLAlchemyError as e:
        logger.error(f"Database error querying for MIDI device '{name}': {e}")
        raise
    except Exception as e:  # Should be rare, but good practice
        logger.error(f"Unexpected error querying for MIDI device '{name}': {e}")
        raise


class MidiRecorder:
    """
    Manages the process of recording MIDI data from selected input devices.

    This class handles the initialization of a MIDI capture session,
    opening MIDI ports, capturing incoming MIDI messages, and serializing them
    for storage as binary data in the database. It also interacts with the
    database to store metadata about the capture session and the MIDI data.

    Attributes:
        project_id (int): The ID of the project this recorder is associated with.
        selected_device_names (list[str]): Names of MIDI devices to record from.
        session_name (str): User-defined name for this capture session.
        capture_session (MidiCaptureSession | None): The SQLAlchemy model for the current session.
        target_devices (list[MidiDevice]): List of resolved MidiDevice models to record from.
        midi_inputs (dict[str, mido.ports.BaseInput]): Dictionary mapping device names to open mido input ports.
        midi_files (dict[tuple[str, int], mido.MidiFile]): Dictionary storing captured MIDI data, keyed by (device_name, channel).
        active (bool): True if recording is currently in progress, False otherwise.
    """

    def __init__(
        self,
        project_id: int,
        selected_device_names: list[str],
        session_name: str,
        db: Session,
    ) -> None:
        """Initializes the MidiRecorder.

        Sets up a new MIDI capture session in the database and resolves the
        selected MIDI devices.

        Args:
            project_id: The ID of the project for this capture session.
            selected_device_names: A list of MIDI device names to record from.
            session_name: A descriptive name for this capture session.
            db: The SQLAlchemy database session to use for initialization.

        Raises:
            ValueError: If the specified `project_id` is not found, or if no valid
                        MIDI devices are found from `selected_device_names`, or if
                        `selected_device_names` is empty.
            SQLAlchemyError: If there's an error during database operations.
        """
        self.project_id: int = project_id
        self.selected_device_names: list[str] = selected_device_names
        self.session_name: str = session_name
        self.capture_session: MidiCaptureSession | None = None
        self.target_devices: list[MidiDevice] = []
        self.midi_inputs: dict[str, mido.ports.BaseInput] = {}
        self.midi_files: dict[tuple[str, int], mido.MidiFile] = {}
        self.active: bool = False

        logger.info(
            f"Initializing MidiRecorder for project ID {project_id}, session '{session_name}'."
        )

        try:
            project: ProjectModel | None = db.query(ProjectModel).filter(ProjectModel.id == self.project_id).first()
            if not project:
                logger.error(f"Project with ID {self.project_id} not found.")
                raise ValueError(
                    f"Project with ID {
                        self.project_id} not found."
                )

            self.capture_session = MidiCaptureSession(
                project_id=self.project_id,
                name=self.session_name,
                status="pending",
            )
            db.add(self.capture_session)
            db.flush()  # Obtain capture_session.id for path generation if needed early

            logger.info(
                f"Created MidiCaptureSession '{
                    self.session_name}' with ID {
                    self.capture_session.id}."
            )

            resolved_devices: list[MidiDevice] = []
            for device_name in self.selected_device_names:
                device: MidiDevice | None = get_midi_device_by_name(db, device_name)
                if device:
                    resolved_devices.append(device)
                else:
                    logger.warning(
                        f"MIDI device '{device_name}' not found in database. It will be skipped."
                    )

            if not resolved_devices:
                db.rollback()
                self.capture_session = None
                logger.error(
                    "No valid MIDI devices were found or specified for recording. Initialization failed."
                )
                raise ValueError(
                    "No valid MIDI devices were found or specified for recording."
                )

            self.target_devices = resolved_devices
            logger.info(
                f"Target MIDI devices for recording: {[dev.name for dev in self.target_devices]}"
            )

            db.commit()
            logger.info("MidiRecorder initialized successfully.")

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during MidiRecorder initialization: {e}")
            raise
        except ValueError as ve:  # Specific ValueErrors already logged by their source
            # db.rollback() # Rollback handled by specific error locations or
            # not needed if before add.
            logger.error(f"Value error during MidiRecorder initialization: {ve}")
            raise
        except Exception as e:
            db.rollback()
            logger.error(
                f"Unexpected error during MidiRecorder initialization: {e}",
                exc_info=True,
            )
            raise

    def _get_output_directory(self) -> str:
        """
        Determines and creates a base output directory for the current capture session.

        The directory structure is `data/projects/<project_id>/midi_captures/<session_name_or_id>/`.
        Note: This directory is not used for storing MIDI files themselves (as they are stored
        as blobs in the database), but can be used for other session-related files or metadata if needed.

        Returns:
            The absolute path to the base output directory for the session.

        Raises:
            ValueError: If the capture session is not initialized or has no ID.
            OSError: If directory creation fails.
        """
        if not self.capture_session or self.capture_session.id is None:
            logger.error(
                "Cannot get output directory: Capture session not initialized or lacks ID."
            )
            raise ValueError(
                "Capture session is not properly initialized or does not have an ID."
            )

        session_part: str = sanitize_filename(self.capture_session.name)
        if not session_part:  # Fallback to ID if name sanitization results in empty string
            session_part = str(self.capture_session.id)

        path: str = os.path.join(
            "data",
            "projects",
            str(self.capture_session.project_id),
            "midi_captures",
            session_part,
        )

        try:
            os.makedirs(path, exist_ok=True)
            logger.debug(f"Ensured output directory exists: {path}")
        except OSError as e:
            logger.error(f"Failed to create output directory {path}: {e}")
            raise
        return path

    def _get_midi_filepath(self, device_name: str, channel: int) -> str:
        """
        Determines and creates the path for a specific MIDI file.

        The path is `<output_directory>/<sanitized_device_name>/channel_<channel>.mid`.
        A subdirectory for the device is created if it doesn't exist.

        Args:
            device_name: The name of the MIDI device.
            channel: The MIDI channel number.

        Returns:
            The absolute path for the MIDI file.

        Raises:
            OSError: If subdirectory creation fails.
        """
        output_dir: str = self._get_output_directory()  # Ensures base session directory exists
        sanitized_device_name: str = sanitize_filename(device_name)

        device_specific_dir: str = os.path.join(output_dir, sanitized_device_name)
        try:
            os.makedirs(device_specific_dir, exist_ok=True)
            logger.debug(f"Ensured device-specific directory exists: {device_specific_dir}")
        except OSError as e:
            logger.error(
                f"Failed to create device-specific directory {device_specific_dir}: {e}"
            )
            raise

        # Handle system messages channel (-1)
        filename: str = f"channel_{channel if channel >= 0 else 'sys'}.mid"
        return os.path.join(device_specific_dir, filename)

    # The _get_output_directory method is kept for potential future use (e.g., storing
    # other session-related files, or if the directory structure itself is useful metadata),
    # even though MIDI files themselves are now stored as blobs in the
    # database.

    def start_recording(self, db: Session) -> None:
        """Starts the MIDI recording process.

        Opens MIDI input ports for the selected devices and sets their callbacks
        to `_midi_callback`. Updates the capture session status to 'recording'.

        Args:
            db: The SQLAlchemy database session.

        Raises:
            ValueError: If the recorder is not properly initialized.
            SQLAlchemyError: If there's an error updating the session status in the database.
            Exception: Can re-raise errors from `mido.open_input`.
        """
        if self.active:
            logger.warning("Start recording called but recording is already active.")
            return
        if not self.capture_session:
            logger.error(
                "Cannot start recording: MidiRecorder not properly initialized (no capture session)."
            )
            raise ValueError("MidiRecorder not properly initialized (no capture session).")
        if not self.target_devices:
            logger.warning("No target devices configured for recording. Cannot start.")
            return

        logger.info(
            f"Starting MIDI recording for session ID: {
                self.capture_session.id}"
        )
        opened_ports_count: int = 0
        try:
            for device_model in self.target_devices:
                try:
                    port: mido.ports.BaseInput = mido.open_input(
                        device_model.name,
                        callback=lambda msg, dn=device_model.name: self._midi_callback(
                            msg, dn
                        ),
                    )
                    self.midi_inputs[device_model.name] = port
                    opened_ports_count += 1
                    logger.info(
                        f"Successfully opened MIDI input: {
                            device_model.name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Error opening MIDI device {
                            device_model.name}: {e}. This device will be skipped."
                    )

            if opened_ports_count == 0:
                self.capture_session.status = "failed" # type: ignore
                self.capture_session.updated_at = datetime.datetime.utcnow() # type: ignore
                db.add(self.capture_session)
                db.commit()
                logger.error("No MIDI input ports could be opened. Recording cannot start.")
                return

            self.capture_session.start_time = datetime.datetime.utcnow() # type: ignore
            self.capture_session.status = "recording" # type: ignore
            self.active = True
            db.add(self.capture_session)
            db.commit()
            logger.info(
                f"Recording started for session: '{
                    self.capture_session.name}' (ID: {
                    self.capture_session.id})"
            )

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during start_recording: {e}")
            self.active = False
            for port in self.midi_inputs.values():
                port.close()  # Clean up
            self.midi_inputs.clear()
            raise
        except Exception as e:
            logger.error(f"Generic error in start_recording: {e}", exc_info=True)
            if self.capture_session and self.capture_session.status != "failed":
                self.capture_session.status = "failed" # type: ignore
                self.capture_session.updated_at = datetime.datetime.utcnow() # type: ignore
                try:
                    db.add(self.capture_session)
                    db.commit()
                except SQLAlchemyError:
                    db.rollback()
            for port in self.midi_inputs.values():
                port.close()  # Clean up
            self.midi_inputs.clear()
            self.active = False
            raise

    def _midi_callback(self, msg: mido.Message, device_name: str) -> None:
        """Callback function to handle incoming MIDI messages.

        This method is called by `mido` for each MIDI message received from
        an open input port. It appends the message to the appropriate
        `mido.MidiFile` object in `self.midi_files`.

        Args:
            msg: The MIDI message received.
            device_name: The name of the MIDI device that sent the message.
        """
        if not self.active:
            # logger.debug("MIDI callback called while not active. Ignoring
            # message.") # Can be too verbose
            return

        # logger.debug(f"MIDI from {device_name}: {msg}") # Can be very verbose

        try:
            channel: int
            if hasattr(msg, "channel"):
                channel = msg.channel
            else:
                channel = -1  # For system messages or messages without a channel

            file_key: tuple[str, int] = (device_name, channel)

            if file_key not in self.midi_files:
                mido_file: mido.MidiFile = mido.MidiFile(type=1)
                track_name: str = f"{
                    sanitize_filename(device_name)}_ch{
                    channel if channel >= 0 else 'sys'}"
                mido_file.add_track(name=track_name)
                self.midi_files[file_key] = mido_file
                logger.debug(
                    f"Created new mido.MidiFile for device '{device_name}', channel {channel}."
                )

            self.midi_files[file_key].tracks[0].append(msg)

        except Exception as e:
            logger.error(
                f"Error in _midi_callback for device {device_name}, msg {msg}: {e}",
                exc_info=True,
            )

    def stop_recording(self, db: Session) -> None:
        """Stops the MIDI recording process.

        Closes all open MIDI input ports, serializes the captured MIDI data for each
        device and channel, and stores this data as blobs in `MidiFile` records
        in the database. Updates the capture session status to 'completed' or
        'completed_empty'.

        Args:
            db: The SQLAlchemy database session.

        Raises:
            ValueError: If the recorder is not properly initialized.
            SQLAlchemyError: If there's an error during database operations.
            Exception: Can re-raise errors from `mido_file_obj.save()`.
        """
        if not self.active:
            logger.warning("Stop recording called but recording is not currently active.")
            return
        if not self.capture_session:
            logger.error(
                "Cannot stop recording: MidiRecorder not properly initialized (no capture session)."
            )
            raise ValueError("MidiRecorder not properly initialized (no capture session).")

        logger.info(
            f"Stopping MIDI recording for session ID: {
                self.capture_session.id}"
        )
        try:
            for device_name, port in self.midi_inputs.items():
                try:
                    port.close()
                    logger.info(f"Closed MIDI input: {device_name}")
                except Exception as e:
                    logger.error(f"Error closing MIDI device {device_name}: {e}")
            self.midi_inputs.clear()

            saved_file_count: int = 0
            if not self.midi_files:
                logger.info("No MIDI messages were captured during this session.")

            for (device_name, channel), mido_file_obj in self.midi_files.items():
                device_model: MidiDevice | None = next(
                    (dev for dev in self.target_devices if dev.name == device_name),
                    None,
                )

                if not device_model:
                    logger.error(
                        f"Critical: Could not find device model for {device_name} during stop_recording. Skipping saving its MIDI file."
                    )
                    continue

                # Removed: filepath = self._get_midi_filepath(device_name, channel)
                try:
                    if not mido_file_obj.tracks or not mido_file_obj.tracks[0]:
                        logger.info(
                            f"No messages recorded for {device_name}, channel {channel}. Skipping database save."
                        )
                        continue

                    # Serialize MIDI data to bytes
                    midi_buffer: io.BytesIO = io.BytesIO()
                    mido_file_obj.save(file=midi_buffer)
                    binary_midi_data: bytes = midi_buffer.getvalue()
                    midi_buffer.close()

                    logger.info(
                        f"Serialized MIDI data for device {device_name}, channel {channel} for database storage ({
                            len(binary_midi_data)} bytes)."
                    )

                    new_midi_file_record: MidiFile = MidiFile(
                        midi_capture_session_id=self.capture_session.id, # type: ignore
                        midi_device_id=device_model.id,
                        channel_number=channel,
                        midi_data=binary_midi_data,  # Store binary data
                    )
                    db.add(new_midi_file_record)
                    saved_file_count += 1
                except Exception as e:
                    logger.error(
                        f"Error serializing or saving MIDI data for device {device_name}, channel {channel} to database: {e}",
                        exc_info=True,
                    )

            self.capture_session.end_time = datetime.datetime.utcnow() # type: ignore
            if saved_file_count == 0:
                self.capture_session.status = "completed_empty" # type: ignore
                if not self.midi_files:  # No messages received at all
                    logger.info(
                        "Session completed empty: No MIDI messages were received to initiate any tracks."
                    )
                else:  # Messages might have been received but resulted in no actual data being saved (e.g. only meta)
                    logger.info(
                        "Session completed empty: No actual MIDI data was saved, though messages might have been processed."
                    )
            else:
                self.capture_session.status = "completed" # type: ignore
            self.active = False

            db.add(self.capture_session)
            db.commit()
            logger.info(
                f"Recording stopped for session: '{
                    self.capture_session.name}'. {saved_file_count} MIDI file(s) saved."
            )

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during stop_recording: {e}")
            raise
        except Exception as e:
            logger.error(f"Generic error in stop_recording: {e}", exc_info=True)
            if self.capture_session:
                self.capture_session.status = "failed" # type: ignore
                self.capture_session.updated_at = datetime.datetime.utcnow() # type: ignore
                try:
                    db.add(self.capture_session)
                    db.commit()
                except SQLAlchemyError:  # If even marking as failed fails
                    db.rollback()
            raise
        finally:
            self.midi_files.clear()
            logger.debug("Cleared in-memory MIDI data.")


# Example Usage (Illustrative)
# ... (example usage code remains unchanged, but print statements there would ideally also be logging)
# Note: The actual 'if __name__ == "__main__":' block and its contents were removed
# in previous steps to aid 'black' formatting if they caused issues.
# If needed for actual script execution, it would be re-added here, ensuring
# it's also black-compliant. For library code, it's often omitted.
