"""
MIDI capture infrastructure using mido.
"""

import os
import datetime
import re
import logging
import io
from typing import Optional, List, Dict, Tuple
import mido
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from src.database.models import MidiDeviceModel, MidiCaptureSessionModel, MidiFileModel, ProjectModel

# pylint: disable=no-member

logger = logging.getLogger(__name__)

def sanitize_filename(name: str) -> str:
    """Sanitizes a string for use as a filename or directory name."""
    if not name:
        return "unknown"
    name = name.replace(" ", "_")
    name = re.sub(r"[^\w\.-]", "", name)
    return name

def list_available_midi_devices(db: Session) -> List[MidiDeviceModel]:
    """Lists available MIDI input devices and synchronizes them with the database."""
    logger.info("Listing available MIDI devices.")
    try:
        device_names: List[str] = mido.get_input_names()
    except Exception as e:
        logger.error(f"Error getting MIDI input names from mido: {e}")
        raise

    found_or_created_devices: List[MidiDeviceModel] = []

    try:
        for name in device_names:
            device = db.query(MidiDeviceModel).filter(MidiDeviceModel.name == name).first()
            if device:
                logger.debug(f"MIDI device '{name}' found in database. Updating timestamp.")
                device.updated_at = datetime.datetime.utcnow()
                db.add(device)
            else:
                logger.info(f"New MIDI device '{name}' detected. Adding to database.")
                device = MidiDeviceModel(name=name, system_identifier=name)
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
        db.rollback()
        logger.error(f"Unexpected error listing or saving MIDI devices: {e}")
        raise

    return found_or_created_devices

def get_midi_device_by_name(db: Session, name: str) -> Optional[MidiDeviceModel]:
    """Retrieves a MIDI device from the database by its unique name."""
    logger.debug(f"Querying for MIDI device by name: '{name}'")
    try:
        device = db.query(MidiDeviceModel).filter(MidiDeviceModel.name == name).first()
        return device
    except SQLAlchemyError as e:
        logger.error(f"Database error querying for MIDI device '{name}': {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error querying for MIDI device '{name}': {e}")
        raise

class MidiRecorder:
    """
    Manages the process of recording MIDI data from selected input devices.
    """

    def __init__(
        self,
        project_id: int,
        selected_device_names: List[str],
        session_name: str,
        db: Session,
    ) -> None:
        self.project_id = project_id
        self.selected_device_names = selected_device_names
        self.session_name = session_name
        self.capture_session: Optional[MidiCaptureSessionModel] = None
        self.target_devices: List[MidiDeviceModel] = []
        self.midi_inputs: Dict[str, mido.ports.BaseInput] = {}
        self.midi_files: Dict[Tuple[str, int], mido.MidiFile] = {}
        self.active = False

        logger.info(
            f"Initializing MidiRecorder for project ID {project_id}, session '{session_name}'."
        )

        try:
            project = db.get(ProjectModel, self.project_id)
            if not project:
                logger.error(f"Project with ID {self.project_id} not found.")
                raise ValueError(f"Project with ID {self.project_id} not found.")

            self.capture_session = MidiCaptureSessionModel(
                project_id=self.project_id,
                name=self.session_name,
                status="pending",
            )
            db.add(self.capture_session)
            db.flush()

            resolved_devices: List[MidiDeviceModel] = []
            for device_name in self.selected_device_names:
                device = get_midi_device_by_name(db, device_name)
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
            db.commit()
            logger.info("MidiRecorder initialized successfully.")

        except (SQLAlchemyError, ValueError) as e:
            db.rollback()
            logger.error(f"Error during MidiRecorder initialization: {e}")
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Unexpected error during MidiRecorder initialization: {e}", exc_info=True)
            raise

    def start_recording(self, db: Session) -> None:
        """Starts the MIDI recording process for the configured devices."""
        if self.active:
            logger.warning("Start recording called but recording is already active.")
            return
        if not self.capture_session:
            raise ValueError("MidiRecorder not properly initialized (no capture session).")

        logger.info(f"Starting MIDI recording for session ID: {self.capture_session.id}")
        opened_ports_count = 0
        try:
            for device_model in self.target_devices:
                try:
                    port = mido.open_input(
                        device_model.name,
                        callback=lambda msg, dn=device_model.name: self._midi_callback(msg, dn),
                    )
                    self.midi_inputs[device_model.name] = port
                    opened_ports_count += 1
                    logger.info(f"Successfully opened MIDI input: {device_model.name}")
                except Exception as e:
                    logger.error(f"Error opening MIDI device {device_model.name}: {e}")

            if opened_ports_count == 0:
                self.capture_session.status = "failed"
                db.add(self.capture_session)
                db.commit()
                return

            self.capture_session.start_time = datetime.datetime.utcnow()
            self.capture_session.status = "recording"
            self.active = True
            db.add(self.capture_session)
            db.commit()

        except SQLAlchemyError as e:
            db.rollback()
            self.active = False
            for port in self.midi_inputs.values():
                port.close()
            self.midi_inputs.clear()
            raise
        except Exception as e:
            logger.error(f"Error in start_recording: {e}", exc_info=True)
            self.active = False
            raise

    def _midi_callback(self, msg: mido.Message, device_name: str) -> None:
        """Handles incoming MIDI messages."""
        if not self.active:
            return

        try:
            channel = getattr(msg, "channel", -1)
            file_key = (device_name, channel)

            if file_key not in self.midi_files:
                mido_file = mido.MidiFile(type=1)
                track_name = f"{sanitize_filename(device_name)}_ch{channel if channel >= 0 else 'sys'}"
                mido_file.add_track(name=track_name)
                self.midi_files[file_key] = mido_file

            self.midi_files[file_key].tracks[0].append(msg)
        except Exception as e:
            logger.error(f"Error in _midi_callback: {e}", exc_info=True)

    def stop_recording(self, db: Session) -> None:
        """Stops the MIDI recording and saves files to the database."""
        if not self.active or not self.capture_session:
            return

        logger.info(f"Stopping MIDI recording for session ID: {self.capture_session.id}")
        try:
            for port in self.midi_inputs.values():
                port.close()
            self.midi_inputs.clear()

            saved_file_count = 0
            for (device_name, channel), mido_file_obj in self.midi_files.items():
                device_model = next((dev for dev in self.target_devices if dev.name == device_name), None)
                if not device_model or not mido_file_obj.tracks or not mido_file_obj.tracks[0]:
                    continue

                midi_buffer = io.BytesIO()
                mido_file_obj.save(file=midi_buffer)
                binary_midi_data = midi_buffer.getvalue()
                
                new_midi_file_record = MidiFileModel(
                    midi_capture_session_id=self.capture_session.id,
                    midi_device_id=device_model.id,
                    channel_number=channel,
                    midi_data=binary_midi_data,
                )
                db.add(new_midi_file_record)
                saved_file_count += 1

            self.capture_session.end_time = datetime.datetime.utcnow()
            self.capture_session.status = "completed" if saved_file_count > 0 else "completed_empty"
            self.active = False
            db.add(self.capture_session)
            db.commit()

        except SQLAlchemyError as e:
            db.rollback()
            raise
        except Exception as e:
            logger.error(f"Error in stop_recording: {e}", exc_info=True)
            raise
        finally:
            self.midi_files.clear()
