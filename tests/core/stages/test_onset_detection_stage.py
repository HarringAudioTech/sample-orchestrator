import os
import pytest
import numpy as np
import librosa
from src.core.stages.onset_detection_stage import OnsetDetectionStage

def test_onset_detection_zero_crossing_snapping():
    """
    Test that detected onsets are snapped to the nearest zero crossing.
    Currently, the implementation does NOT do this, so this test should FAIL
    once we add the assertion for zero crossing.
    """
    stage = OnsetDetectionStage()
    test_file = "test_audio/drum_loop.wav"
    
    if not os.path.exists(test_file):
        pytest.skip(f"Test file {test_file} not found")
        
    # Process the audio file
    onset_times = stage.process(test_file)
    
    assert len(onset_times) > 0, "Should detect at least one onset"
    
    # Load the audio to check zero crossings with the same SR used by the stage
    sr = 44100
    y, _ = librosa.load(test_file, sr=sr)
    
    for t in onset_times:
        # Convert time back to sample index
        # We check a small window because floating point time to samples conversion
        # might be slightly off due to precision.
        sample_idx = librosa.time_to_samples(t, sr=sr)
        
        # Check if ANY of the samples in a tiny window around the converted index 
        # is a zero crossing. This handles rounding discrepancies.
        window_indices = [sample_idx - 1, sample_idx, sample_idx + 1]
        
        found_crossing = False
        for idx in window_indices:
            if idx < 0 or idx >= len(y):
                continue
                
            val = y[idx]
            # Zero crossing: y[i] is very small OR y[i-1] and y[i] have different signs
            # OR y[i] and y[i+1] have different signs
            is_zero_crossing = (np.abs(val) < 1e-4) or \
                              (idx > 0 and np.signbit(y[idx-1]) != np.signbit(y[idx])) or \
                              (idx < len(y)-1 and np.signbit(y[idx]) != np.signbit(y[idx+1]))
            
            if is_zero_crossing:
                found_crossing = True
                break
        
        assert found_crossing, f"No zero crossing found near onset time {t}s (sample {sample_idx}). Value: {y[sample_idx]}"

def test_onset_detection_temporal_resolution():
    """
    Test that onset detection has high temporal resolution (small hop length).
    """
    stage = OnsetDetectionStage()
    test_file = "test_audio/drum_loop.wav"
    
    if not os.path.exists(test_file):
        pytest.skip(f"Test file {test_file} not found")
        
    # Current default hop_length is 512 at 22050Hz (~23ms)
    # For drum hits, we want better resolution.
    # Let's check if the current implementation uses the high resolution we want.
    
    # This is more of a configuration check for now
    params = stage.default_params
    assert params["sr"] >= 44100, "Sample rate should be at least 44100Hz for high precision"
    assert params["hop_length"] <= 256, "Hop length should be 256 or less for high precision"
