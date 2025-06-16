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
    """Sanitizes a string for use as a filename or directory name.

    This function performs two main operations to make a string safe for
    filesystem usage:
    1. Replaces all occurrences of space characters (' ') with underscores ('_').
    2. Removes any characters that are not alphanumeric (letters, numbers),
       underscores ('_'), dots ('.'), or hyphens ('-').

    Args:
        name (str): The input string to be sanitized.

    Returns:
        str: The sanitized string, which is more suitable for use as a part
             of a filename or directory name.
    """
    name = name.replace(" ", "_")
    name = re.sub(r"[^\w\.-]", "", name)
    return name


def list_available_midi_devices(db: Session) -> list[MidiDevice]:
    """Lists available MIDI input devices and synchronizes them with the database.

    This function retrieves the names of all MIDI input devices currently
    recognized by the `mido` library. It then iterates through these names,
    checking if each device already exists in the `MidiDevice` table in the
    database.
    - If a device is found, its `updated_at` timestamp is refreshed.
    - If a device is not found, a new `MidiDevice` record is created and added
      to the database.
    All changes are committed to the database session provided.

    Args:
        db (Session): The SQLAlchemy database session to use for querying and
                      updating `MidiDevice` records.

    Returns:
        list[MidiDevice]: A list of `MidiDevice` SQLAlchemy model instances. This
                          list includes all devices found by `mido`, whether they
                          were newly added or existing ones that were updated.

    Raises:
        SQLAlchemyError: If any database operation (query, add, commit) fails.
        Exception: If `mido.get_input_names()` fails or any other unexpected
                   error occurs during the process. Errors from `mido` are
                   logged and re-raised.
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
            device: MidiDevice | None = (
                db.query(MidiDevice).filter(MidiDevice.name == name).first()
            )
            if device:
                logger.debug(
                    f"MIDI device '{name}' found in database. Updating timestamp."
                )
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
            f"Successfully synchronized {len(found_or_created_devices)} MIDI devices with the database."
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
    """Retrieves a MIDI device from the database by its unique name.

    This function queries the `MidiDevice` table for an entry where the `name`
    column matches the provided `name` argument.

    Args:
        db (Session): The SQLAlchemy database session to use for the query.
        name (str): The name of the MIDI device to search for. This is expected
                    to be the unique identifier as recognized by `mido` and
                    stored in the database.

    Returns:
        Optional[MidiDevice]: The `MidiDevice` SQLAlchemy model instance if a
                              device with the specified name is found in the
                              database. Returns `None` if no such device exists.

    Raises:
        SQLAlchemyError: If an error occurs during the database query operation.
        Exception: If any other unexpected error occurs. These are logged and
                   re-raised.
    """
    logger.debug(f"Querying for MIDI device by name: '{name}'")
    try:
        device: MidiDevice | None = (
            db.query(MidiDevice).filter(MidiDevice.name == name).first()
        )
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
        """Initializes a MidiRecorder instance for a given project and MIDI devices.

        This constructor sets up the necessary state for a MIDI recording session.
        It performs the following key actions:
        1. Validates that the specified `project_id` corresponds to an existing
           project in the database.
        2. Creates a new `MidiCaptureSession` record in the database with a
           status of "pending" and associates it with the project.
        3. Resolves the `selected_device_names` against the `MidiDevice` table
           in the database. Only devices found in the database are considered valid
           target devices for recording.
        4. Stores the resolved target devices and other session information as
           instance attributes.

        Args:
            project_id (int): The unique identifier of the `ProjectModel` to which
                              this MIDI capture session will belong.
            selected_device_names (list[str]): A list of strings, where each string
                                               is the name of a MIDI device to be
                                               used for recording.
            session_name (str): A user-defined, descriptive name for this MIDI
                                capture session (e.g., "Piano Take 1").
            db (Session): The SQLAlchemy database session to be used for all
                          database operations during initialization (e.g.,
                          querying projects, creating the capture session,
                          resolving devices).

        Raises:
            ValueError:
                - If the `project_id` does not correspond to an existing project.
                - If `selected_device_names` is empty.
                - If none of the names in `selected_device_names` correspond to
                  known `MidiDevice` records in the database.
            SQLAlchemyError: If any database operation (query, add, commit, flush)
                             fails during the initialization process.
            Exception: For any other unexpected errors, which are logged and re-raised.
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
            project: ProjectModel | None = (
                db.query(ProjectModel)
                .filter(ProjectModel.id == self.project_id)
                .first()
            )
            if not project:
                logger.error(f"Project with ID {self.project_id} not found.")
                raise ValueError(f"Project with ID {self.project_id} not found.")

            self.capture_session = MidiCaptureSession(
                project_id=self.project_id,
                name=self.session_name,
                status="pending",
            )
            db.add(self.capture_session)
            db.flush()  # Obtain capture_session.id for path generation if needed early

            # logger.info("Created MidiCaptureSession '" + self.session_name + "' with ID " + str(self.capture_session.id) + ".") # Commented out for pylint test

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
        except ValueError as ve:
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
        """Determines and creates the base output directory for the current capture session.

        This method constructs a directory path based on the project ID and the
        current MIDI capture session's name (or ID as a fallback). The structure
        is: `data/projects/<project_id>/midi_captures/<sanitized_session_name_or_id>/`.

        The directory is created if it doesn't already exist. While MIDI files
        themselves are stored as BLOBs in the database, this directory can be
        utilized for storing auxiliary files or metadata related to the capture
        session if needed in the future.

        Args:
            None. Relies on `self.capture_session`.

        Returns:
            str: The absolute path to the ensured base output directory for this
                 capture session.

        Raises:
            ValueError: If `self.capture_session` is not initialized or if
                        `self.capture_session.id` is None, as these are crucial
                        for path construction.
            OSError: If an error occurs during directory creation (e.g., due to
                     permissions issues).
        """
        if not self.capture_session or self.capture_session.id is None:
            logger.error(
                "Cannot get output directory: Capture session not initialized or lacks ID."
            )
            raise ValueError(
                "Capture session is not properly initialized or does not have an ID."
            )

        session_part: str = sanitize_filename(self.capture_session.name)
        if (
            not session_part
        ):  # Fallback to ID if name sanitization results in empty string
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
        """Constructs and ensures the directory path for a specific MIDI file.

        This method generates a file path intended for a MIDI file associated with
        a particular device and channel within the current capture session.
        The structure of the path is:
        `<session_output_directory>/<sanitized_device_name>/channel_<channel_or_sys>.mid`.

        It first calls `_get_output_directory()` to get the base directory for
        the session, then creates a subdirectory within it named after the
        sanitized `device_name`. The filename itself indicates the channel
        (e.g., "channel_1.mid", "channel_sys.mid" for system messages).
        The device-specific subdirectory is created if it doesn't already exist.

        Note: While this method generates a filepath, the primary storage for
        MIDI data in this class is as BLOBs in the database. This filepath
        generation might be used for temporary storage or if future requirements
        involve saving physical .mid files alongside database entries.

        Args:
            device_name (str): The name of the MIDI device. This will be sanitized
                               for use in the directory structure.
            channel (int): The MIDI channel number. If less than 0 (e.g., -1),
                           it's treated as a system channel and represented as 'sys'
                           in the filename.

        Returns:
            str: The absolute path for the MIDI file. This path includes the
                 session's output directory, a device-specific subdirectory,
                 and the channel-specific filename.

        Raises:
            ValueError: If `_get_output_directory()` raises it (e.g., session not
                        initialized).
            OSError: If creation of the device-specific subdirectory fails (e.g.,
                     due to permissions).
        """
        output_dir: str = self._get_output_directory()
        sanitized_device_name: str = sanitize_filename(device_name)

        device_specific_dir: str = os.path.join(output_dir, sanitized_device_name)
        try:
            os.makedirs(device_specific_dir, exist_ok=True)
            logger.debug(
                f"Ensured device-specific directory exists: {device_specific_dir}"
            )
        except OSError as e:
            logger.error(
                f"Failed to create device-specific directory {device_specific_dir}: {e}"
            )
            raise

        filename: str = f"channel_{channel if channel >= 0 else 'sys'}.mid"
        return os.path.join(device_specific_dir, filename)

    def start_recording(self, db: Session) -> None:
        """Starts the MIDI recording process for the configured devices.

        This method initiates the MIDI recording by:
        1. Checking if recording is already active or if the recorder is properly
           initialized (has a capture session and target devices).
        2. Iterating through the `self.target_devices` (resolved `MidiDevice` models).
           For each device, it attempts to open a MIDI input port using `mido.open_input()`.
           The `_midi_callback` method is set as the callback for incoming messages.
        3. If any ports are successfully opened:
           - Updates the associated `MidiCaptureSession` record in the database:
             - Sets `start_time` to the current UTC datetime.
             - Sets `status` to "recording".
           - Sets `self.active` to `True`.
        4. If no MIDI input ports can be opened (e.g., devices disconnected or
           `mido` errors), the session status is set to "failed", and the method
           returns without starting active recording.

        Error handling includes logging issues with opening specific ports and
        rolling back database changes if necessary.

        Args:
            db (Session): The SQLAlchemy database session used to update the
                          `MidiCaptureSession` record.

        Raises:
            ValueError: If the `MidiRecorder` instance is not properly initialized
                        (e.g., `self.capture_session` is `None`).
            SQLAlchemyError: If a database error occurs while updating the
                             `MidiCaptureSession` (e.g., during `db.commit()`).
            Exception: Re-raises exceptions from `mido.open_input()` if they occur
                       and are not handled internally (though many `mido` errors
                       are caught per-device). Also re-raises other unexpected
                       exceptions.
        """
        if self.active:
            logger.warning("Start recording called but recording is already active.")
            return
        if not self.capture_session:
            logger.error(
                "Cannot start recording: MidiRecorder not properly initialized (no capture session)."
            )
            raise ValueError(
                "MidiRecorder not properly initialized (no capture session)."
            )
        if not self.target_devices:
            logger.warning("No target devices configured for recording. Cannot start.")
            return

        logger.info(
            f"Starting MIDI recording for session ID: {self.capture_session.id}"
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
                    logger.info(f"Successfully opened MIDI input: {device_model.name}")
                except Exception as e:
                    logger.error(
                        f"Error opening MIDI device {device_model.name}: {e}. This device will be skipped."
                    )

            if opened_ports_count == 0:
                self.capture_session.status = "failed"  # type: ignore
                self.capture_session.updated_at = datetime.datetime.utcnow()  # type: ignore
                db.add(self.capture_session)
                db.commit()
                logger.error(
                    "No MIDI input ports could be opened. Recording cannot start."
                )
                return

            self.capture_session.start_time = datetime.datetime.utcnow()  # type: ignore
            self.capture_session.status = "recording"  # type: ignore
            self.active = True
            db.add(self.capture_session)
            db.commit()
            logger.info(
                f"Recording started for session: '{self.capture_session.name}' (ID: {self.capture_session.id})"
            )

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during start_recording: {e}")
            self.active = False
            for port in self.midi_inputs.values():
                port.close()
            self.midi_inputs.clear()
            raise
        except Exception as e:
            logger.error(f"Generic error in start_recording: {e}", exc_info=True)
            if self.capture_session and self.capture_session.status != "failed":
                self.capture_session.status = "failed"  # type: ignore
                self.capture_session.updated_at = datetime.datetime.utcnow()  # type: ignore
                try:
                    db.add(self.capture_session)
                    db.commit()
                except SQLAlchemyError:
                    db.rollback()
            for port in self.midi_inputs.values():
                port.close()
            self.midi_inputs.clear()
            self.active = False
            raise

    def _midi_callback(self, msg: mido.Message, device_name: str) -> None:
        """Handles incoming MIDI messages from `mido` input ports.

        This method serves as the callback function passed to `mido.open_input()`.
        It is invoked by `mido` whenever a new MIDI message is received on one
        of the monitored ports.

        The method performs the following actions:
        1. Checks if recording is `self.active`. If not, the message is ignored.
        2. Determines the MIDI channel of the message. Messages without a channel
           (e.g., system exclusive) are assigned a nominal channel of -1.
        3. Creates a unique key based on the `device_name` and `channel`.
        4. If a `mido.MidiFile` object does not already exist in `self.midi_files`
           for this key, a new one is created with a single track. The track is
           named using the sanitized device name and channel.
        5. Appends the received `mido.Message` (`msg`) to the appropriate track
           within the corresponding `mido.MidiFile` object.

        Any exceptions encountered during this process are logged, but typically
        do not halt the recording process for other messages or devices.

        Args:
            msg (mido.Message): The MIDI message object received from the
                                `mido` library.
            device_name (str): The name of the MIDI device from which this
                               message originated. This is passed by the `lambda`
                               wrapper in `start_recording`.
        """
        if not self.active:
            return

        try:
            channel: int
            if hasattr(msg, "channel"):
                channel = msg.channel
            else:
                channel = -1

            file_key: tuple[str, int] = (device_name, channel)

            if file_key not in self.midi_files:
                mido_file: mido.MidiFile = mido.MidiFile(type=1)
                track_name: str = (
                    f"{sanitize_filename(device_name)}_ch{channel if channel >= 0 else 'sys'}"
                )
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
        """Stops the MIDI recording, finalizes data, and updates the database.

        This method orchestrates the end of a MIDI recording session:
        1. Checks if recording is active and the recorder is initialized.
        2. Closes all open MIDI input ports that were managed by `mido`.
        3. Iterates through the `self.midi_files` dictionary, which contains
           the captured MIDI messages organized by device and channel.
           For each `mido.MidiFile` object:
             a. If the track contains no messages, it's skipped.
             b. The `mido.MidiFile` object is serialized into binary MIDI data
                (a `bytes` object) using an in-memory `io.BytesIO` buffer.
             c. A new `MidiFile` SQLAlchemy record is created, storing this
                binary data as a BLOB, along with references to the
                `MidiCaptureSession` and the source `MidiDevice`, and the
                channel number. This record is added to the database session.
        4. Updates the associated `MidiCaptureSession` record in the database:
           - Sets `end_time` to the current UTC datetime.
           - Sets `status` to "completed" if any MIDI files were saved, or
             "completed_empty" if no MIDI data was recorded or saved.
        5. Sets `self.active` to `False`.
        6. Clears the in-memory `self.midi_files` cache.

        All database changes are committed. Errors during port closing, data
        serialization, or database operations are logged.

        Args:
            db (Session): The SQLAlchemy database session used for all database
                          updates (creating `MidiFile` records, updating the
                          `MidiCaptureSession`).

        Raises:
            ValueError: If the `MidiRecorder` instance is not properly initialized
                        (e.g., `self.capture_session` is `None`).
            SQLAlchemyError: If a database error occurs during the saving of
                             `MidiFile` records or the update of the
                             `MidiCaptureSession` (e.g., during `db.commit()`).
            Exception: Re-raises exceptions that might occur during MIDI data
                       serialization (e.g., from `mido_file_obj.save()`) or
                       other unexpected critical errors.
        """
        if not self.active:
            logger.warning(
                "Stop recording called but recording is not currently active."
            )
            return
        if not self.capture_session:
            logger.error(
                "Cannot stop recording: MidiRecorder not properly initialized (no capture session)."
            )
            raise ValueError(
                "MidiRecorder not properly initialized (no capture session)."
            )

        logger.info(
            f"Stopping MIDI recording for session ID: {self.capture_session.id}"
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

                try:
                    if not mido_file_obj.tracks or not mido_file_obj.tracks[0]:
                        logger.info(
                            f"No messages recorded for {device_name}, channel {channel}. Skipping database save."
                        )
                        continue

                    midi_buffer: io.BytesIO = io.BytesIO()
                    mido_file_obj.save(file=midi_buffer)
                    binary_midi_data: bytes = midi_buffer.getvalue()
                    midi_buffer.close()

                    logger.info(
                        f"Serialized MIDI data for device {device_name}, channel {channel} for database storage ({len(binary_midi_data)} bytes)."
                    )

                    new_midi_file_record: MidiFile = MidiFile(
                        midi_capture_session_id=self.capture_session.id,  # type: ignore
                        midi_device_id=device_model.id,
                        channel_number=channel,
                        midi_data=binary_midi_data,
                    )
                    db.add(new_midi_file_record)
                    saved_file_count += 1
                except Exception as e:
                    logger.error(
                        f"Error serializing or saving MIDI data for device {device_name}, channel {channel} to database: {e}",
                        exc_info=True,
                    )

            self.capture_session.end_time = datetime.datetime.utcnow()  # type: ignore
            if saved_file_count == 0:
                self.capture_session.status = "completed_empty"  # type: ignore
                if not self.midi_files:
                    logger.info(
                        "Session completed empty: No MIDI messages were received to initiate any tracks."
                    )
                else:
                    logger.info(
                        "Session completed empty: No actual MIDI data was saved, though messages might have been processed."
                    )
            else:
                self.capture_session.status = "completed"  # type: ignore
            self.active = False

            db.add(self.capture_session)
            db.commit()
            logger.info(
                f"Recording stopped for session: '{self.capture_session.name}'. {saved_file_count} MIDI file(s) saved."
            )

        except SQLAlchemyError as e:
            db.rollback()
            logger.error(f"Database error during stop_recording: {e}")
            raise
        except Exception as e:
            logger.error(f"Generic error in stop_recording: {e}", exc_info=True)
            if self.capture_session:
                self.capture_session.status = "failed"  # type: ignore
                self.capture_session.updated_at = datetime.datetime.utcnow()  # type: ignore
                try:
                    db.add(self.capture_session)
                    db.commit()
                except SQLAlchemyError:
                    db.rollback()
            raise
        finally:
            self.midi_files.clear()
            logger.debug("Cleared in-memory MIDI data.")
