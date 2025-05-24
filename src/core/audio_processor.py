"""
Core audio processing utilities.

This module previously contained functions for note detection, audio slicing,
and retrieving audio file details.

As of a recent refactoring:
- Note detection and slicing logic has been moved into the `SlicingStage`
  class located in `src.core.stages.slicing_stage`. This stage is designed
  to be used within the audio processing pipeline defined by `processing_stages.py`
  and executed by `stage_runner.py`.
- The `get_audio_details` function, which was used to extract metadata like
  samplerate and total frames, has also been effectively integrated. The
  `SlicingStage` now handles its own audio detail extraction internally using
  a helper `_get_audio_details_for_slicing`. The `Project.add_recording` method
  in `src.core.project` also implements its own logic for extracting necessary
  metadata (samplerate, duration, channels) when a new recording is added.

Therefore, this module is currently minimal or empty. It is kept for potential
future use if general, non-stage-specific audio processing utilities are needed.
"""

# No functions are currently defined in this module after refactoring.
# Imports that were specific to the removed functions (like aubio, wave, os, Session, models)
# are no longer needed here unless new utility functions requiring them
# are added.

pass
