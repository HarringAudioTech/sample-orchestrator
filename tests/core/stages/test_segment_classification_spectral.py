import os
import pytest
import numpy as np
import librosa
from src.core.stages.segment_classification_stage import SegmentClassificationStage

def test_segment_classification_drum_types():
    """
    Test that SegmentClassificationStage correctly identifies drum hits
    based on spectral features.
    """
    stage = SegmentClassificationStage()
    
    # We need a file path in context to load audio for analysis
    test_file = "test_audio/drum_loop.wav"
    if not os.path.exists(test_file):
        pytest.skip(f"Test file {test_file} not found")
        
    context = {"file_path": test_file}
    
    # Define some segments (start, end)
    # These are rough estimates from a typical drum loop
    segments = [
        {"start_time": 0.0, "end_time": 0.2, "metadata": {}}, # Kick?
        {"start_time": 0.5, "end_time": 0.7, "metadata": {}}, # Snare?
        {"start_time": 0.2, "end_time": 0.3, "metadata": {}}, # Hi-hat?
    ]
    
    # Process
    # This SHOULD fail to identify specific drum types currently as it only does duration
    classified = stage.process(segments, context=context)
    
    for seg in classified:
        assert "instrument_type" in seg["metadata"], f"Segment should have instrument_type in metadata. Seg: {seg}"
        assert "tags" in seg["metadata"], f"Segment should have tags in metadata. Seg: {seg}"
        assert "one_shot" in seg["metadata"]["tags"], "All segments should be tagged as one_shot"
        
        # Verify specific drum tags if identified
        instr = seg["metadata"]["instrument_type"]
        if instr in ["kick", "snare", "hihat"]:
            assert "drum" in seg["metadata"]["tags"]
            assert instr in seg["metadata"]["tags"]
