"""Unit tests for src.core.stages.vocal_chop_perfection_stage."""
import os
from typing import Tuple, Any # List removed
import pytest
import numpy as np  # type: ignore # pylint: disable=import-error
import soundfile  # type: ignore # pylint: disable=import-error

# Adjust import paths as necessary
# pylint: disable=import-error
try:
    from src.core.stages.vocal_chop_perfection_stage import (
        VocalChopPerfectionWorkflow,
        DenoisingStage,
        ClickPopRemovalStage,
        SilenceAndStabAdjustmentStage,
        MetadataUpdateStage,
        # ProcessingStage, # Not directly used in tests
    )
    from src.core.vocal_chop_evaluator import (
        VocalChopEvaluationResult,
        AnalyzedVocalStab,
        VocalChopIdealCharacteristics,
    )
    from src.utils import soundfile_utils
    # SFCuePoint is used by tested code, not directly here.
    # from src.utils.soundfile_utils import SFCuePoint
except ImportError:
    # Fallback for different execution contexts
    from core.stages.vocal_chop_perfection_stage import ( # type: ignore
        VocalChopPerfectionWorkflow,
        DenoisingStage,
        ClickPopRemovalStage,
        SilenceAndStabAdjustmentStage,
        MetadataUpdateStage,
        # ProcessingStage,
    )
    from core.vocal_chop_evaluator import ( # type: ignore
        VocalChopEvaluationResult,
        AnalyzedVocalStab,
        VocalChopIdealCharacteristics,
    )
    from utils import soundfile_utils # type: ignore
    # from utils.soundfile_utils import SFCuePoint # type: ignore
# pylint: enable=import-error


# --- Fixtures ---

@pytest.fixture
def tmp_dirs(tmp_path):
    """Creates output_dir and base_tmp_path under tmp_path."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return {"output_dir": str(output_dir), "base_tmp_path": str(tmp_path)}

@pytest.fixture
def base_evaluation_result(sample_wav_file) -> VocalChopEvaluationResult: # pylint: disable=redefined-outer-name
    """Returns a basic VocalChopEvaluationResult instance."""
    info = soundfile.info(sample_wav_file)
    return VocalChopEvaluationResult(
        file_path=sample_wav_file,
        sample_rate=info.samplerate,
        channels=info.channels,
        duration_ms=(info.frames / info.samplerate) * 1000,
    )

@pytest.fixture
def ideal_characteristics() -> VocalChopIdealCharacteristics:
    """Returns default VocalChopIdealCharacteristics."""
    return VocalChopIdealCharacteristics()

@pytest.fixture
def sample_wav_file(tmp_path) -> str: # pylint: disable=redefined-outer-name
    """Creates a simple WAV file and returns its path."""
    file_path = tmp_path / "sample.wav"
    sr = 44100
    y = np.sin(
        2 * np.pi * 440 * np.linspace(0, 1, sr), dtype=np.float32
    )
    soundfile.write(str(file_path), y, sr)
    return str(file_path)

# --- Tests for Stubbed Stages ---

# pylint: disable=redefined-outer-name
def test_denoising_stage_passthrough(
    sample_wav_file: str,
    tmp_dirs: dict,
    base_evaluation_result: VocalChopEvaluationResult,
    caplog: Any,
):
    """Tests DenoisingStage passthrough and logging."""
    stage = DenoisingStage(
        working_dir=tmp_dirs["output_dir"]
    )
    base_evaluation_result.denoising_recommended = False
    output_path = stage.process(sample_wav_file, base_evaluation_result)
    assert output_path == sample_wav_file
    assert "Denoising not recommended" in caplog.text

    caplog.clear()
    base_evaluation_result.denoising_recommended = True
    output_path = stage.process(sample_wav_file, base_evaluation_result)
    expected_output_name = os.path.basename(sample_wav_file).replace(
        ".wav", "_denoised_stub.wav"
    )
    assert os.path.basename(output_path) == expected_output_name
    assert os.path.exists(output_path)
    assert "Denoising recommended" in caplog.text
    assert "Denoising not yet implemented" in caplog.text

# pylint: disable=redefined-outer-name
def test_clickpop_removal_stage_passthrough(
    sample_wav_file: str,
    tmp_dirs: dict,
    base_evaluation_result: VocalChopEvaluationResult,
    caplog: Any,
):
    """Tests ClickPopRemovalStage passthrough and logging."""
    stage = ClickPopRemovalStage(working_dir=tmp_dirs["output_dir"])

    base_evaluation_result.click_pop_detected = False
    output_path = stage.process(sample_wav_file, base_evaluation_result)
    assert output_path == sample_wav_file
    assert "No clicks/pops detected" in caplog.text

    caplog.clear()
    base_evaluation_result.click_pop_detected = True
    output_path = stage.process(sample_wav_file, base_evaluation_result)
    expected_output_name = os.path.basename(sample_wav_file).replace(
        ".wav", "_clickremoved_stub.wav"
    )
    assert os.path.basename(output_path) == expected_output_name
    assert os.path.exists(output_path)
    assert "Click/pop removal recommended" in caplog.text
    assert "Click/pop removal not yet implemented" in caplog.text


# --- Tests for SilenceAndStabAdjustmentStage ---

@pytest.fixture
def two_burst_wav_file(tmp_path) -> Tuple[str, int, int, int]:
    """Creates a WAV with two short bursts separated by short silence."""
    sr = 44100
    burst_duration_samples = int(0.1 * sr)
    silence_duration_samples = int(0.05 * sr)

    burst1 = (
        np.sin(np.linspace(0, 10 * np.pi, burst_duration_samples), dtype=np.float32)
        * 0.5
    )
    burst2 = (
        np.cos(np.linspace(0, 10 * np.pi, burst_duration_samples), dtype=np.float32)
        * 0.5
    )
    silence = np.zeros(silence_duration_samples, dtype=np.float32)

    audio_data = np.concatenate([burst1, silence, burst2])
    file_path = tmp_path / "two_burst.wav"
    soundfile.write(str(file_path), audio_data, sr)
    return str(file_path), sr, burst_duration_samples, silence_duration_samples

# pylint: disable=redefined-outer-name,too-many-locals
def test_silence_adjustment_stage_silence_insertion(
    two_burst_wav_file: Tuple[str, int, int, int],
    tmp_dirs: dict,
    ideal_characteristics: VocalChopIdealCharacteristics,
    base_evaluation_result: VocalChopEvaluationResult,
):
    """Tests SilenceAndStabAdjustmentStage for correct silence insertion."""
    file_path, sr, burst_samples, initial_silence_samples = two_burst_wav_file

    base_evaluation_result.file_path = file_path
    base_evaluation_result.sample_rate = sr
    base_evaluation_result.duration_ms = (
        (2 * burst_samples + initial_silence_samples) / sr
    ) * 1000
    base_evaluation_result.stabs = [
        AnalyzedVocalStab(start_sample=0, end_sample=burst_samples, label="Stab1"),
        AnalyzedVocalStab(
            start_sample=burst_samples + initial_silence_samples,
            end_sample=burst_samples * 2 + initial_silence_samples,
            label="Stab2",
        ),
    ]
    setattr(base_evaluation_result, "ideal_characteristics", ideal_characteristics)

    stage = SilenceAndStabAdjustmentStage(working_dir=tmp_dirs["output_dir"])
    output_path = stage.process(file_path, base_evaluation_result)

    assert os.path.exists(output_path)
    y_processed, sr_processed = soundfile.read(output_path)

    assert sr_processed == sr

    expected_silence_ms = ideal_characteristics.min_silence_duration_ms
    expected_silence_samples = int((expected_silence_ms / 1000.0) * sr)

    expected_total_samples = 2 * burst_samples + expected_silence_samples
    assert len(y_processed) == pytest.approx(expected_total_samples, abs=1)

    assert len(base_evaluation_result.stabs) == 2
    processed_stab1 = base_evaluation_result.stabs[0]
    processed_stab2 = base_evaluation_result.stabs[1]

    actual_silence_start = processed_stab1.end_sample
    actual_silence_end = processed_stab2.start_sample
    actual_silence_len_samples = actual_silence_end - actual_silence_start

    assert actual_silence_len_samples == expected_silence_samples

    silence_segment_data = y_processed[actual_silence_start:actual_silence_end]
    assert np.all(silence_segment_data == 0)

    assert processed_stab1.end_sample - processed_stab1.start_sample == pytest.approx(
        burst_samples, abs=int(0.02 * sr)
    )
    assert processed_stab2.end_sample - processed_stab2.start_sample == pytest.approx(
        burst_samples, abs=int(0.02 * sr)
    )


# TODO: test_silence_adjustment_stage_zero_crossing - needs carefully crafted audio

# --- Tests for MetadataUpdateStage ---

# pylint: disable=redefined-outer-name
def test_metadata_update_stage_writes_cues(
    sample_wav_file: str,
    tmp_dirs: dict,
    base_evaluation_result: VocalChopEvaluationResult,
):
    """Tests that MetadataUpdateStage correctly writes cue markers."""
    base_evaluation_result.stabs = [
        AnalyzedVocalStab(start_sample=100, end_sample=200, label="TestCue1"),
        AnalyzedVocalStab(start_sample=300, end_sample=400, label="TestCue Γειά"),
    ]
    stage = MetadataUpdateStage(working_dir=tmp_dirs["output_dir"])
    output_path = stage.process(sample_wav_file, base_evaluation_result)

    retrieved_cues = soundfile_utils.get_cue_markers(output_path)
    assert len(retrieved_cues) == 2
    assert retrieved_cues[0].name.startswith(b"TestCue1")
    assert retrieved_cues[0].position == 100
    assert retrieved_cues[1].name.startswith("TestCue Γειά".encode("utf-8"))
    assert retrieved_cues[1].position == 300

# pylint: disable=redefined-outer-name
def test_metadata_update_stage_writes_tempo_key(
    sample_wav_file: str,
    tmp_dirs: dict,
    base_evaluation_result: VocalChopEvaluationResult,
):
    """Tests that MetadataUpdateStage correctly writes tempo and key information."""
    base_evaluation_result.tempo = 140.0
    base_evaluation_result.key = "A#4/Bb4"

    stage = MetadataUpdateStage(working_dir=tmp_dirs["output_dir"])
    output_path = stage.process(sample_wav_file, base_evaluation_result)

    loop_info = soundfile_utils.get_loop_info(output_path)
    assert loop_info is not None
    assert loop_info.bpm == pytest.approx(140.0)
    assert loop_info.root_key == 70 # A#4/Bb4 is MIDI 70

    instr_info = soundfile_utils.get_instrument_info(output_path)
    assert instr_info is not None
    assert instr_info.basenote == 70

# pylint: disable=redefined-outer-name
def test_metadata_update_stage_comment(
    sample_wav_file: str,
    tmp_dirs: dict,
    base_evaluation_result: VocalChopEvaluationResult,
    caplog: Any,
):
    """Tests that MetadataUpdateStage attempts to write a comment."""
    stage = MetadataUpdateStage(working_dir=tmp_dirs["output_dir"])
    output_path = stage.process(sample_wav_file, base_evaluation_result)

    with soundfile.SoundFile(output_path) as sf_out:
        if hasattr(sf_out, "comment"):
            assert "Processed by VocalChopPerfectionWorkflow." in sf_out.comment
        else:
            assert "Set comment metadata." in caplog.text
            print(
                "Note: Direct comment reading not available, checked log."
            )


# --- Tests for VocalChopPerfectionWorkflow ---

# pylint: disable=redefined-outer-name
def test_workflow_execution_order(
    sample_wav_file: str,
    tmp_dirs: dict,
    base_evaluation_result: VocalChopEvaluationResult,
    mocker: Any,
):
    """Tests that workflow stages are called in the correct order."""
    output_dir = tmp_dirs["output_dir"]

    mock_denoise_process = mocker.patch.object(
        DenoisingStage, "process", return_value=sample_wav_file + "_denoised"
    )
    mock_clickpop_process = mocker.patch.object(
        ClickPopRemovalStage, "process", return_value=sample_wav_file + "_clickremoved"
    )
    mock_adjust_process = mocker.patch.object(
        SilenceAndStabAdjustmentStage,
        "process",
        return_value=sample_wav_file + "_adjusted",
    )
    mock_metadata_process = mocker.patch.object(
        MetadataUpdateStage, "process", return_value=sample_wav_file + "_meta_updated"
    )

    workflow = VocalChopPerfectionWorkflow(sample_wav_file, base_evaluation_result)
    final_file, _ = workflow.run(output_dir) # W0612: intermediates_dir unused

    mock_denoise_process.assert_called_once_with(
        sample_wav_file, base_evaluation_result
    )
    mock_clickpop_process.assert_called_once_with(
        sample_wav_file + "_denoised", base_evaluation_result
    )
    mock_adjust_process.assert_called_once_with(
        sample_wav_file + "_clickremoved", base_evaluation_result
    )
    mock_metadata_process.assert_called_once_with(
        sample_wav_file + "_adjusted", base_evaluation_result
    )

    expected_final_name = os.path.basename(sample_wav_file).replace(
        ".wav", "_perfected.wav"
    )
    assert os.path.basename(final_file) == expected_final_name

# pylint: disable=redefined-outer-name
def test_workflow_file_management(
    sample_wav_file: str,
    tmp_dirs: dict,
    base_evaluation_result: VocalChopEvaluationResult,
):
    """Tests workflow's creation of intermediate and final files."""
    output_dir = tmp_dirs["output_dir"]

    base_evaluation_result.denoising_recommended = True
    base_evaluation_result.click_pop_detected = True

    workflow = VocalChopPerfectionWorkflow(sample_wav_file, base_evaluation_result)
    final_file, intermediates_dir = workflow.run(output_dir)

    assert os.path.isdir(intermediates_dir)

    original_base = os.path.splitext(os.path.basename(sample_wav_file))[0]
    assert os.path.exists(
        os.path.join(intermediates_dir, f"{original_base}_denoised_stub.wav")
    )
    assert os.path.exists(
        os.path.join(intermediates_dir, f"{original_base}_clickremoved_stub.wav")
    )
    assert os.path.exists(
        os.path.join(intermediates_dir, f"{original_base}_adjusted_stub.wav")
    )
    assert os.path.exists(
        os.path.join(intermediates_dir, f"{original_base}_meta_updated.wav")
    )

    assert os.path.exists(final_file)
    expected_final_name = f"{original_base}_perfected.wav"
    # Corrected line:
    final_basename = os.path.basename(final_file)
    assert final_basename == expected_final_name


# TODO: Add more specific tests for SilenceAndStabAdjustmentStage:
# - _find_closest_zero_crossing helper function directly.
# - Zero-crossing adjustment logic with specific audio data where ZCs are known.
# - Cases with no stabs, or only one stab for silence adjustment.

# TODO: Add more specific tests for MetadataUpdateStage:
# - Test behavior when metadata chunks already exist in the file (overwrite vs. append if applicable).
# - Test with various valid and invalid key strings for librosa.note_to_midi.
# - If SFC_SET_STRING is implemented, test setting other string types.
# - Test with an empty list of stabs for cue setting.
# - Test that default values are correctly set in SFLoopInfo/SFInstrumentInfo if not provided.
# - Test what happens if `soundfile_utils` functions return False (failure).
