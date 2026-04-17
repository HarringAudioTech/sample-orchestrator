"""
Audio recording infrastructure using SoundCard and Soundfile.
"""

from __future__ import annotations
import logging
import threading
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np
import soundcard as sc
import soundfile as sf

logger = logging.getLogger(__name__)

class AudioRecorder:
    """
    Manages audio recording from hardware interfaces using SoundCard.
    """

    def __init__(self, sample_rate: int = 44100, channels: int = 2, chunk_size: int = 1024):
        """
        Initializes the AudioRecorder.

        Args:
            sample_rate (int): Hardware sample rate.
            channels (int): Number of input channels.
            chunk_size (int): Buffer size for recording.
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.frames: List[np.ndarray] = []
        self.is_recording = False
        self._lock = threading.Lock()
        self._recording_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def list_devices(self) -> List[Dict[str, Any]]:
        """
        Lists available audio input devices using SoundCard.
        """
        devices = []
        try:
            inputs = sc.all_inputs()
            for i, mic in enumerate(inputs):
                devices.append({
                    "index": i,
                    "id": mic.name,
                    "name": mic.name,
                    "max_input_channels": 2, # SoundCard usually handles this transparently
                    "default_sample_rate": self.sample_rate
                })
        except Exception as e:
            logger.error(f"Error listing audio devices with SoundCard: {e}")
        return devices

    def start_recording(self, device_index: Optional[int] = None, device_name: Optional[str] = None):
        """
        Starts an asynchronous recording session in a separate thread.
        """
        with self._lock:
            if self.is_recording:
                logger.warning("Recording is already in progress.")
                return

            self.frames = []
            self.is_recording = True
            self._stop_event.clear()

            # Resolve device
            try:
                if device_name:
                    mic = sc.get_microphone(device_name)
                elif device_index is not None:
                    mic = sc.all_inputs()[device_index]
                else:
                    mic = sc.default_input()
            except Exception as e:
                self.is_recording = False
                logger.error(f"Failed to find audio device: {e}")
                raise

            self._recording_thread = threading.Thread(
                target=self._recording_loop,
                args=(mic,),
                daemon=True
            )
            self._recording_thread.start()
            logger.info(f"Audio recording thread started (device: {mic.name}, rate: {self.sample_rate})")

    def _recording_loop(self, mic: Any):
        """
        Continuous recording loop run in a separate thread.
        """
        try:
            with mic.recorder(samplerate=self.sample_rate, channels=self.channels) as recorder:
                while not self._stop_event.is_set():
                    data = recorder.record(numframes=self.chunk_size)
                    with self._lock:
                        self.frames.append(data.copy())
        except Exception as e:
            logger.error(f"Error in recording loop: {e}")
            self.is_recording = False

    def stop_recording(self, output_path: Path) -> Optional[Path]:
        """
        Stops the recording session and saves the audio to a file.

        Args:
            output_path (Path): Path to save the WAV file.

        Returns:
            Optional[Path]: The path to the saved file if successful.
        """
        if not self.is_recording:
            logger.warning("Stop recording called but not recording.")
            return None

        self._stop_event.set()
        if self._recording_thread:
            self._recording_thread.join(timeout=2.0)
            self._recording_thread = None

        with self._lock:
            self.is_recording = False
            
            if not self.frames:
                logger.warning("No audio frames were captured.")
                return None

            try:
                # Concatenate all frames into one large array
                audio_data = np.concatenate(self.frames)
                
                # SoundCard already returns (samples, channels) format
                
                # Ensure output directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Save using soundfile
                sf.write(str(output_path), audio_data, self.sample_rate)
                logger.info(f"Audio recording saved to {output_path} ({len(audio_data)} samples)")
                return output_path
            except Exception as e:
                logger.error(f"Error saving audio recording: {e}")
                raise

    def __del__(self):
        """
        Cleanup ensure recording stopped.
        """
        self._stop_event.set()
