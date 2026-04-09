"""
Defines the OnsetDetectionStage for audio processing pipelines.
This stage is responsible for detecting onsets/transients in audio files.
"""

import logging
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
import librosa

from src.core.processing_stages import AudioProcessingStage
from src.core.stage_runner import register_stage

logger = logging.getLogger(__name__)

class OnsetDetectionStage(AudioProcessingStage):
    """
    A processing stage that detects onsets/transients in an audio file.
    
    This stage takes an audio file as input and returns a list of detected
    onset times or sample indices that can be used for slicing.
    """
    
    @property
    def name(self) -> str:
        return "onset_detection"
    
    @property
    def description(self) -> str:
        return "Detects onsets/transients in an audio file"
    
    @property
    def input_type(self) -> str:
        return "file_path"  # Path to audio file
    
    @property
    def output_type(self) -> str:
        return "onset_times"  # List of onset times in seconds
    
    @property
    def default_params(self) -> Dict[str, Any]:
        """
        Returns default parameters for librosa's onset_detect function.
        These can be overridden when calling process().
        """
        return {
            "sr": 44100,  # Higher target sample rate for precision
            "hop_length": 256,  # Smaller hop length for better temporal resolution
            "n_fft": 2048,
            "snap_to_zero_crossing": True, # New parameter to enable snapping
            "detection_params": {
                "units": "samples",  # Use samples for internal precision
                "backtrack": True,   # Backtrack to preceding minimum for better transient start
                "energy": None,      # Will use onset_envelope if None
                "fmin": 20.0,
                "fmax": 20000.0,
                "aggregate": np.mean,
                "delta": 0.07,       # threshold for peak picking (formerly detection_threshold)
                "wait": 5,           # minimum number of frames between onsets
                "pre_max": 5,
                "post_max": 5,
                "pre_avg": 10,
                "post_avg": 10,
            }
        }
    
    def _snap_to_zero_crossing(self, y: np.ndarray, sample_idx: int) -> int:
        """
        Find the nearest zero crossing to the given sample index.
        If no zero crossing is found in the window, returns the sample with the 
        minimum absolute value in that window.
        """
        # Look in a small window around the sample_idx
        window_size = 1024
        start = max(0, sample_idx - window_size)
        end = min(len(y), sample_idx + window_size)
        
        # Get the audio segment
        segment = y[start:end]
        
        # Find where sign changes
        sign_changes = np.where(np.diff(np.signbit(segment)))[0]
        
        if len(sign_changes) > 0:
            # For each change at index i, the crossing is between i and i+1
            # We want the sample that is closer to zero
            crossings = []
            for i in sign_changes:
                if np.abs(segment[i]) < np.abs(segment[i+1]):
                    crossings.append(i + start)
                else:
                    crossings.append(i + 1 + start)
            
            crossings = np.array(crossings)
            
            # Find the closest crossing to the original sample_idx
            closest_idx = crossings[np.argmin(np.abs(crossings - sample_idx))]
            return int(closest_idx)
        else:
            # If no zero crossing, find the minimum absolute value in the window
            min_idx = np.argmin(np.abs(segment))
            return int(min_idx + start)

    def process(
        self, 
        data: str, 
        params: Optional[Dict[str, Any]] = None, 
        context: Optional[Dict[str, Any]] = None
    ) -> List[float]:
        """
        Detect onsets in the given audio file.
        
        Args:
            data: Path to the input audio file
            params: Optional parameters for onset detection. Can include:
                   - sr: Target sample rate
                   - hop_length: Hop length for STFT
                   - n_fft: FFT window size
                   - snap_to_zero_crossing: Whether to snap onsets to zero crossings
                   - detection_params: Parameters for librosa.onset.onset_detect()
            context: Optional context dictionary (unused in this stage)
            
        Returns:
            List of onset times in seconds
            
        Raises:
            FileNotFoundError: If the input audio file is not found
            RuntimeError: If audio processing fails
        """
        if params is None:
            params = {}
            
        # Merge default params with provided params
        merged_params = self.default_params.copy()
        # Deep merge detection_params if they exist
        if "detection_params" in params:
            merged_params["detection_params"].update(params.pop("detection_params"))
        merged_params.update(params)
        
        # Extract parameters
        sr = merged_params.get("sr", 44100)
        hop_length = merged_params.get("hop_length", 256)
        n_fft = merged_params.get("n_fft", 2048)
        snap_to_zero_crossing = merged_params.get("snap_to_zero_crossing", True)
        detection_params = merged_params.get("detection_params", {})
        
        try:
            # Load audio file
            y, _ = librosa.load(data, sr=sr, mono=True)
            
            # Extract strength parameters from detection_params
            strength_keys = ["fmin", "fmax", "n_mels", "aggregate"]
            strength_params = {k: detection_params.pop(k) for k in strength_keys if k in detection_params}
            
            # Compute onset strength envelope separately to allow passing specific parameters
            oenv = librosa.onset.onset_strength(
                y=y, 
                sr=sr, 
                hop_length=hop_length,
                n_fft=n_fft,
                **strength_params
            )
            
            # Detect onsets using the envelope
            onset_samples = librosa.onset.onset_detect(
                onset_envelope=oenv,
                sr=sr, 
                hop_length=hop_length,
                **detection_params
            )
            
            # librosa.onset_detect returns frames if units is not specified or set to None
            # We want samples for snapping
            if detection_params.get("units") != "samples":
                onset_samples = librosa.frames_to_samples(onset_samples, hop_length=hop_length)
            
            # Snap to zero crossing if requested
            if snap_to_zero_crossing:
                onset_samples = [self._snap_to_zero_crossing(y, int(s)) for s in onset_samples]
            
            # Convert to seconds for output
            onset_times = librosa.samples_to_time(onset_samples, sr=sr)
            
            # Ensure we return a list of floats, not numpy types
            return [float(t) for t in onset_times]
            
        except FileNotFoundError as e:
            logger.error(f"Audio file not found: {data}")
            raise
        except Exception as e:
            logger.error(f"Error detecting onsets: {str(e)}")
            raise RuntimeError(f"Onset detection failed: {str(e)}")


# Register the stage when this module is imported
register_stage(OnsetDetectionStage)
