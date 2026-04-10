"""
Audio recording infrastructure using PyAudio and Soundfile.
"""

from __future__ import annotations
import logging
import threading
import wave
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

import numpy as np
import pyaudio
import soundfile as sf

logger = logging.getLogger(__name__)

class AudioRecorder:
    """
    Manages audio recording from hardware interfaces.
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
        self.p = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.frames: List[np.ndarray] = []
        self.is_recording = False
        self._lock = threading.Lock()

    def list_devices(self) -> List[Dict[str, Any]]:
        """
        Lists available audio input devices.
        """
        devices = []
        try:
            info = self.p.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount', 0)
            for i in range(0, num_devices):
                device_info = self.p.get_device_info_by_host_api_device_index(0, i)
                if device_info.get('maxInputChannels', 0) > 0:
                    devices.append({
                        "index": i,
                        "name": device_info.get('name'),
                        "max_input_channels": device_info.get('maxInputChannels'),
                        "default_sample_rate": device_info.get('defaultSampleRate')
                    })
        except Exception as e:
            logger.error(f"Error listing audio devices: {e}")
        return devices

    def start_recording(self, device_index: Optional[int] = None):
        """
        Starts an asynchronous recording session.
        """
        with self._lock:
            if self.is_recording:
                logger.warning("Recording is already in progress.")
                return

            self.frames = []
            self.is_recording = True

            try:
                self.stream = self.p.open(
                    format=pyaudio.paFloat32,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    input_device_index=device_index,
                    frames_per_buffer=self.chunk_size,
                    stream_callback=self._stream_callback
                )
                logger.info(f"Audio recording started (device: {device_index}, rate: {self.sample_rate}, channels: {self.channels})")
            except Exception as e:
                self.is_recording = False
                logger.error(f"Failed to open audio stream: {e}")
                raise

    def _stream_callback(self, in_data, frame_count, time_info, status):
        """
        Callback for PyAudio stream.
        """
        if status:
            logger.warning(f"PyAudio status: {status}")
        
        if self.is_recording:
            # Convert bytes to numpy array
            data = np.frombuffer(in_data, dtype=np.float32)
            # We must copy the data because PyAudio might reuse the buffer
            self.frames.append(data.copy())
            
        return (in_data, pyaudio.paContinue)

    def stop_recording(self, output_path: Path) -> Path:
        """
        Stops the recording session and saves the audio to a file.

        Args:
            output_path (Path): Path to save the WAV file.

        Returns:
            Path: The path to the saved file.
        """
        with self._lock:
            if not self.is_recording:
                logger.warning("Stop recording called but not recording.")
                return None

            self.is_recording = False
            
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None

            if not self.frames:
                logger.warning("No audio frames were captured.")
                return None

            try:
                # Concatenate all frames into one large array
                audio_data = np.concatenate(self.frames)
                # Reshape to (samples, channels)
                # Note: PyAudio interleaved format is [L, R, L, R, ...]
                audio_data = audio_data.reshape(-1, self.channels)

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
        Cleanup PyAudio instance.
        """
        try:
            self.p.terminate()
        except:
            pass
