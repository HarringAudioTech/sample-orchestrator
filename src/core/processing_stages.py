"""
Legacy bridge for audio processing stages.
Redirects to the new stage_runner infrastructure.
"""

from src.core.stage_runner import (
    BaseStage as AudioProcessingStage,
    DATA_TYPE_FILE_PATH,
    DATA_TYPE_AUDIO_BUFFER_MONO,
    DATA_TYPE_AUDIO_BUFFER_STEREO,
    DATA_TYPE_MIDI_DATA,
    DATA_TYPE_METADATA,
    DATA_TYPE_LIST_OF_SAMPLE_DATA,
    STAGE_REGISTRY,
    register_stage,
    execute_stage_chain
)

# For backward compatibility with existing tests and stages
__all__ = [
    "AudioProcessingStage",
    "DATA_TYPE_FILE_PATH",
    "DATA_TYPE_AUDIO_BUFFER_MONO",
    "DATA_TYPE_AUDIO_BUFFER_STEREO",
    "DATA_TYPE_MIDI_DATA",
    "DATA_TYPE_METADATA",
    "DATA_TYPE_LIST_OF_SAMPLE_DATA",
    "STAGE_REGISTRY",
    "register_stage",
    "execute_stage_chain"
]
