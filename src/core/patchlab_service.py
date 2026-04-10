"""
Patchlab service for synthesizer manipulation.
"""

from __future__ import annotations
import logging
from typing import Optional, Dict, Any, List
import patchlab

logger = logging.getLogger(__name__)

class PatchlabService:
    """
    Service wrapper for the Patchlab library to control hardware synthesizers.
    """

    def __init__(self):
        """
        Initializes the PatchlabService.
        """
        self.device: Optional[Any] = None
        self.device_type: Optional[str] = None

    def list_ports(self) -> List[str]:
        """
        Lists available MIDI output ports.
        """
        try:
            return patchlab.list_output_ports()
        except Exception as e:
            logger.error(f"Error listing MIDI output ports: {e}")
            return []

    def connect(self, device_type: str, port: str, device_id: int = 0, midi_channel: int = 0) -> bool:
        """
        Connects to a synthesizer device.

        Args:
            device_type (str): Type of device (e.g., 'procussion', 'ms2000').
            port (str): MIDI port name or pattern.
            device_id (int): Device SysEx ID.
            midi_channel (int): MIDI channel (0-15).

        Returns:
            bool: True if connection was successful.
        """
        try:
            logger.info(f"Connecting to {device_type} on port '{port}'...")
            self.device = patchlab.connect(device_type, port, device_id, midi_channel)
            self.device_type = device_type
            logger.info(f"Connected to {device_type} successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to {device_type}: {e}")
            self.device = None
            self.device_type = None
            return False

    def load_patch(self, patch_data: Dict[str, Any], location: int = 0) -> bool:
        """
        Loads a patch/kit into the connected synthesizer.

        Args:
            patch_data (Dict[str, Any]): The patch data (dictionary format).
            location (int): The memory location (e.g., kit number).

        Returns:
            bool: True if successful.
        """
        if not self.device:
            logger.error("Cannot load patch: Not connected to a device.")
            return False

        try:
            # Note: The exact method depends on the device type in Patchlab
            if hasattr(self.device, "send_kit"):
                self.device.send_kit(location, patch_data)
            elif hasattr(self.device, "send_patch"):
                self.device.send_patch(location, patch_data)
            else:
                logger.warning(f"Device type '{self.device_type}' may not support bulk patch loading via this service yet.")
                return False
            
            logger.info(f"Patch loaded into {self.device_type} at location {location}.")
            return True
        except Exception as e:
            logger.error(f"Error loading patch: {e}")
            return False

    def set_parameter(self, parameter_number: int, value: int) -> bool:
        """
        Sets a single parameter on the connected synthesizer.
        """
        if not self.device:
            return False

        try:
            self.device.set_parameter(parameter_number, value)
            return True
        except Exception as e:
            logger.error(f"Error setting parameter: {e}")
            return False

    def note_on(self, channel: int, note: int, velocity: int):
        """Sends a MIDI Note On message."""
        if self.device:
            self.device.note_on(channel, note, velocity)

    def note_off(self, channel: int, note: int, velocity: int):
        """Sends a MIDI Note Off message."""
        if self.device:
            self.device.note_off(channel, note, velocity)
