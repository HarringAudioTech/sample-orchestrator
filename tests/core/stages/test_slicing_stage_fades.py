import os
import pytest
import numpy as np
from unittest.mock import MagicMock
from src.core.stages.slicing_stage import SlicingStage

def test_slicing_stage_applies_fades():
    """
    Test that SlicingStage applies fades to audio slices.
    Currently, the implementation does NOT do this, so this test should FAIL
    once we check for the fade effect.
    """
    stage = SlicingStage()
    
    # Mock context
    context = {
        "db_session": MagicMock(),
        "recording_id": 1,
        "project_id": 1,
        "output_sample_dir": "test_output",
    }
    
    # Mock recording
    mock_recording = MagicMock()
    context["db_session"].get.return_value = mock_recording
    
    # Mock audio data (constant 1.0)
    sr = 44100
    y = np.ones(sr * 2, dtype=np.float32)
    data = {"audio_data": y, "sample_rate": sr}
    
    params = {
        "slice_points": [{"start": 0.0, "end": 1.0}],
        "apply_fades": True,
        "fade_in_ms": 100,
        "fade_out_ms": 100,
        "normalize": False # Disable normalization for easier checking
    }
    
    # Process
    samples = stage.process(data, params, context)
    
    assert len(samples) >= 1, "Should create at least one sample"
    
    # Check the saved file
    import soundfile as sf
    output_path = samples[0]["file_path"]
    y_slice, _ = sf.read(output_path)
    
    # Check fade in: first samples should be increasing
    assert y_slice[0] < 0.1, f"First sample should be close to zero due to fade in. Value: {y_slice[0]}"
    assert y_slice[10] > y_slice[0], "Samples should increase during fade in"
    
    # Check fade out: last samples should be decreasing
    assert y_slice[-1] < 0.1, f"Last sample should be close to zero due to fade out. Value: {y_slice[-1]}"
    assert y_slice[-11] > y_slice[-1], "Samples should decrease during fade out"
    
    # Cleanup
    if os.path.exists(output_path):
        os.remove(output_path)
