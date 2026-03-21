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
            "sr": 22050,  # Target sample rate
            "hop_length": 512,
            "n_fft": 2048,
            "detection_params": {
                "units": "time",  # Return onset times in seconds
                "hop_length": 512,
                "backtrack": False,
                "energy": 0.01,  # Minimum energy threshold
                "fmin": 20.0,     # Minimum frequency in Hz
                "fmax": 20000.0,  # Maximum frequency in Hz
                "aggregate": np.mean,
                "detection_threshold": 0.1,
            }
        }
    
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
        merged_params.update(params)
        
        # Extract parameters
        sr = merged_params.get("sr", 22050)
        hop_length = merged_params.get("hop_length", 512)
        n_fft = merged_params.get("n_fft", 2048)
        detection_params = merged_params.get("detection_params", {})
        
        try:
            # Load audio file
            y, _ = librosa.load(data, sr=sr, mono=True)
            
            # Detect onsets
            onset_times = librosa.onset.onset_detect(
                y=y, 
                sr=sr, 
                hop_length=hop_length,
                **detection_params
            )
            
            # Convert to seconds if needed
            if isinstance(onset_times, np.ndarray) and len(onset_times) > 0:
                if detection_params.get("units", "time") == "samples":
                    onset_times = librosa.samples_to_time(onset_times, sr=sr)
                
                # Ensure we return a list of floats, not numpy types
                return [float(t) for t in onset_times]
            
            return []
            
        except FileNotFoundError as e:
            logger.error(f"Audio file not found: {data}")
            raise
        except Exception as e:
            logger.error(f"Error detecting onsets: {str(e)}")
            raise RuntimeError(f"Onset detection failed: {str(e)}")


# Register the stage when this module is imported
register_stage(OnsetDetectionStage)
