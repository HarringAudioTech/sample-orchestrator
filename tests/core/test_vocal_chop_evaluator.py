"""Unit tests for src.core.vocal_chop_evaluator."""
from typing import Tuple, Any # Removed List as it's not directly used by tests
import pytest
import numpy as np  # type: ignore # pylint: disable=import-error
import soundfile  # type: ignore # pylint: disable=import-error
import librosa  # type: ignore # pylint: disable=import-error

# Adjust import paths as necessary for your project structure
# pylint: disable=import-error
try:
    from src.core.vocal_chop_evaluator import (
        VocalChopEvaluator,
        VocalChopIdealCharacteristics,
        # VocalChopEvaluationResult, # Not directly used by tests, but by tested module
        # AnalyzedVocalStab, # Not directly used by tests, but by tested module
    )
    from src.utils.soundfile_utils import (
        SFCuePoint,
        SFInstrumentInfo,
        SFLoopInfo,
        # SF_LOOP_NONE, # Not directly used by tests
        # SF_LOOP_FORWARD, # Not directly used by tests
        # get_cue_markers as actual_get_cue_markers, # For patch target reference
        # get_instrument_info as actual_get_instrument_info,
        # get_loop_info as actual_get_loop_info,
    )
except ImportError:
    from core.vocal_chop_evaluator import ( # type: ignore
        VocalChopEvaluator,
        VocalChopIdealCharacteristics,
        # VocalChopEvaluationResult,
        # AnalyzedVocalStab,
    )
    from utils.soundfile_utils import ( # type: ignore
        SFCuePoint,
        SFInstrumentInfo,
        SFLoopInfo,
        # SF_LOOP_NONE,
        # SF_LOOP_FORWARD,
        # get_cue_markers as actual_get_cue_markers,
        # get_instrument_info as actual_get_instrument_info,
        # get_loop_info as actual_get_loop_info,
    )
# pylint: enable=import-error


# --- Fixtures ---


@pytest.fixture
def ideal_characteristics_fixture() -> VocalChopIdealCharacteristics:
    """Returns a default VocalChopIdealCharacteristics instance."""
    return VocalChopIdealCharacteristics()


@pytest.fixture
def evaluator_fixture( # pylint: disable=redefined-outer-name
    ideal_characteristics_fixture: VocalChopIdealCharacteristics,
) -> VocalChopEvaluator:
    """Returns a VocalChopEvaluator instance."""
    return VocalChopEvaluator(ideal_characteristics_fixture)


@pytest.fixture
def dummy_audio_data_fixture() -> Tuple[np.ndarray, int]:
    """Returns sample audio data (sine wave) and sample rate."""
    sr = 44100
    duration_seconds = 1.0
    frequency = 440  # A4
    y = np.sin(
        2
        * np.pi
        * frequency
        * np.linspace(0, duration_seconds, int(sr * duration_seconds)),
        dtype=np.float32,
    )
    return y, sr


@pytest.fixture
def temp_wav_file_fixture( # pylint: disable=redefined-outer-name
    tmp_path, dummy_audio_data_fixture: Tuple[np.ndarray, int]
) -> str:
    """Creates a temporary WAV file with dummy audio data."""
    y, sr = dummy_audio_data_fixture
    file_path = tmp_path / "test_audio.wav"
    soundfile.write(str(file_path), y, sr, format="WAV", subtype="PCM_16")
    return str(file_path)


# --- Test Cases ---

# pylint: disable=redefined-outer-name
def test_evaluate_basic_info(
    evaluator_fixture: VocalChopEvaluator,
    temp_wav_file_fixture: str,
    dummy_audio_data_fixture: Tuple[np.ndarray, int],
    mocker: Any,
):
    """Tests basic file info loading and initial state when no metadata is present."""
    _, sr = dummy_audio_data_fixture

    mocker.patch("src.utils.soundfile_utils.get_cue_markers", return_value=[])
    mocker.patch("src.utils.soundfile_utils.get_instrument_info", return_value=None)
    mocker.patch("src.utils.soundfile_utils.get_loop_info", return_value=None)
    mocker.patch("librosa.onset.onset_detect", return_value=np.array([]))

    result = evaluator_fixture.evaluate(temp_wav_file_fixture)

    assert result.sample_rate == sr
    assert result.channels == 1
    assert result.duration_ms == pytest.approx(1000.0)

    assert not result.metadata_tempo_present
    assert not result.metadata_key_present
    assert not result.cue_markers_present
    assert not result.cue_labels_present
    assert result.tempo is None
    assert result.key is None

    assert any(
        "Cue markers not found or stabs list empty" in issue for issue in result.issues
    )
    assert any(
        "Tempo estimated using librosa" in issue for issue in result.issues
    )
    assert any("Key estimated using librosa" in issue for issue in result.issues)

# pylint: disable=redefined-outer-name
def test_evaluate_with_full_metadata(
    evaluator_fixture: VocalChopEvaluator, temp_wav_file_fixture: str, mocker: Any
):
    """Tests evaluation when all relevant metadata is present."""
    mock_cues = [
        SFCuePoint(indx=1, position=100, name="Vocal 1".encode("utf-8")),
        SFCuePoint(indx=2, position=200, name="Vocal 2".encode("utf-8")),
        SFCuePoint(indx=3, position=300, name="Vocal 3".encode("utf-8")),
        SFCuePoint(indx=4, position=400, name="Vocal 4".encode("utf-8")),
    ]
    mock_instr_info = SFInstrumentInfo(basenote=60)
    mock_loop_info = SFLoopInfo(bpm=120.0)

    mocker.patch("src.utils.soundfile_utils.get_cue_markers", return_value=mock_cues)
    mocker.patch(
        "src.utils.soundfile_utils.get_instrument_info", return_value=mock_instr_info
    )
    mocker.patch("src.utils.soundfile_utils.get_loop_info", return_value=mock_loop_info)

    result = evaluator_fixture.evaluate(temp_wav_file_fixture)

    assert result.metadata_tempo_present
    assert result.metadata_key_present
    assert result.cue_markers_present
    assert result.cue_labels_present

    assert result.tempo == 120.0
    assert result.key == "C4"

    assert len(result.stabs) == 4
    assert result.stabs[0].label == "Vocal 1"
    assert result.stab_count_is_power_of_2

    assert not any(
        "Tempo metadata missing" in issue
        for issue in result.issues
        if "estimation" not in issue.lower()
    )
    assert not any(
        "Key metadata missing" in issue
        for issue in result.issues
        if "estimation" not in issue.lower()
    )
    assert not any("Cue markers missing" in issue for issue in result.issues)

# pylint: disable=redefined-outer-name
def test_evaluate_missing_cue_labels(
    evaluator_fixture: VocalChopEvaluator, temp_wav_file_fixture: str, mocker: Any
):
    """Tests evaluation when cue markers are present but lack labels."""
    mock_cues = [
        SFCuePoint(indx=1, position=100, name=b""),
        SFCuePoint(indx=2, position=200, name=b"\x00"),
    ]
    mocker.patch("src.utils.soundfile_utils.get_cue_markers", return_value=mock_cues)
    mocker.patch(
        "src.utils.soundfile_utils.get_instrument_info", return_value=None
    )
    mocker.patch("src.utils.soundfile_utils.get_loop_info", return_value=None)
    mocker.patch("librosa.onset.onset_detect", return_value=np.array([]))

    result = evaluator_fixture.evaluate(temp_wav_file_fixture)

    assert result.cue_markers_present
    assert not result.cue_labels_present
    assert any(
        "Cue labels missing" in issue
        for issue in result.issues
        if "ideal" in issue.lower()
    )

# pylint: disable=redefined-outer-name
def test_evaluate_stab_count_not_power_of_2(
    evaluator_fixture: VocalChopEvaluator, temp_wav_file_fixture: str, mocker: Any
):
    """Tests evaluation when the number of cues is not an ideal power of 2."""
    mock_cues = [
        SFCuePoint(indx=i, position=i * 100, name=f"Cue {i}".encode("utf-8"))
        for i in range(1, 4)
    ]
    mocker.patch("src.utils.soundfile_utils.get_cue_markers", return_value=mock_cues)
    mocker.patch(
        "src.utils.soundfile_utils.get_instrument_info",
        return_value=SFInstrumentInfo(basenote=60),
    )
    mocker.patch(
        "src.utils.soundfile_utils.get_loop_info", return_value=SFLoopInfo(bpm=120.0)
    )

    result = evaluator_fixture.evaluate(temp_wav_file_fixture)
    assert not result.stab_count_is_power_of_2
    assert any("not an expected power of 2" in issue for issue in result.issues)

# pylint: disable=redefined-outer-name
def test_evaluate_no_cues_onset_detection(
    evaluator_fixture: VocalChopEvaluator, tmp_path: Any, mocker: Any
):
    """Tests onset detection when no cue markers are found."""
    sr = 44100
    y1 = np.sin(np.linspace(0, 10 * np.pi, int(0.1 * sr)))
    silence = np.zeros(int(0.2 * sr))
    y = np.concatenate([y1, silence, y1, silence, y1]).astype(np.float32)

    onset_test_file = tmp_path / "onset_test.wav"
    soundfile.write(str(onset_test_file), y, sr)

    mocker.patch("src.utils.soundfile_utils.get_cue_markers", return_value=[])
    mocker.patch("src.utils.soundfile_utils.get_instrument_info", return_value=None)
    mocker.patch("src.utils.soundfile_utils.get_loop_info", return_value=None)

    spy_onset_detect = mocker.spy(librosa.onset, "onset_detect")

    result = evaluator_fixture.evaluate(str(onset_test_file))

    spy_onset_detect.assert_called_once()
    assert len(result.stabs) == 3
    assert any(
        "Stab detected by onset analysis" in stab.issues[0] for stab in result.stabs
    )
    assert any(
        "Cue markers not found or stabs list empty" in issue for issue in result.issues
    )
    assert not result.stab_count_is_power_of_2
    assert any(
        "Detected stab count (3) is not an ideal power of 2" in issue
        for issue in result.issues
    )

# pylint: disable=redefined-outer-name
def test_evaluate_zero_crossings(
    evaluator_fixture: VocalChopEvaluator, tmp_path: Any, mocker: Any
):
    """Tests zero-crossing detection for stabs."""
    sr = 44100
    y_clean_stab = np.sin(np.linspace(0, 2 * np.pi, int(0.1 * sr))).astype(np.float32)
    y_unclean_stab = (np.ones(int(0.1 * sr)) * 0.5).astype(np.float32)

    clean_file = tmp_path / "zc_clean.wav"
    unclean_file = tmp_path / "zc_unclean.wav"
    soundfile.write(str(clean_file), y_clean_stab, sr)
    soundfile.write(
        str(unclean_file),
        np.concatenate([y_unclean_stab, np.zeros(100), y_unclean_stab]),
        sr,
    )

    mock_cues_clean = [SFCuePoint(indx=1, position=0, name=b"clean")]
    mocker.patch(
        "src.utils.soundfile_utils.get_cue_markers", return_value=mock_cues_clean
    )
    mocker.patch("src.utils.soundfile_utils.get_instrument_info", return_value=None)
    mocker.patch("src.utils.soundfile_utils.get_loop_info", return_value=None)

    result_clean = evaluator_fixture.evaluate(str(clean_file))
    assert len(result_clean.stabs) == 1
    assert result_clean.stabs[0].has_clean_start_zero_crossing
    assert result_clean.stabs[0].has_clean_end_zero_crossing

    mock_cues_unclean = [
        SFCuePoint(indx=1, position=0, name=b"unclean1"),
        SFCuePoint(
            indx=2, position=len(y_unclean_stab) + 100, name=b"unclean2"
        ),
    ]
    mocker.patch(
        "src.utils.soundfile_utils.get_cue_markers", return_value=mock_cues_unclean
    )
    result_unclean = evaluator_fixture.evaluate(str(unclean_file))
    assert len(result_unclean.stabs) == 2
    assert not result_unclean.stabs[0].has_clean_start_zero_crossing
    assert not result_unclean.stabs[0].has_clean_end_zero_crossing
    assert any(
        "No clean start zero-crossing" in issue
        for issue in result_unclean.stabs[0].issues
    )
    assert any(
        "No clean end zero-crossing" in issue
        for issue in result_unclean.stabs[0].issues
    )
    assert not result_unclean.stabs[1].has_clean_start_zero_crossing
    assert not result_unclean.stabs[1].has_clean_end_zero_crossing


def test_evaluate_silence_duration(tmp_path: Any, mocker: Any):
    """Tests detection of short silence between stabs."""
    sr = 44100
    ideal_chars = VocalChopIdealCharacteristics(min_silence_duration_ms=75.0)
    evaluator = VocalChopEvaluator(ideal_chars)

    stab_sound = np.ones(int(0.1 * sr)) * 0.5
    short_silence = np.zeros(int(0.05 * sr))

    audio_data = np.concatenate([stab_sound, short_silence, stab_sound]).astype(
        np.float32
    )
    file_path = tmp_path / "short_silence_test.wav"
    soundfile.write(str(file_path), audio_data, sr)

    mock_cues = [
        SFCuePoint(indx=1, position=0, name=b"Stab1"),
        SFCuePoint(
            indx=2, position=len(stab_sound) + len(short_silence), name=b"Stab2"
        ),
    ]
    mocker.patch("src.utils.soundfile_utils.get_cue_markers", return_value=mock_cues)
    mocker.patch("src.utils.soundfile_utils.get_instrument_info", return_value=None)
    mocker.patch("src.utils.soundfile_utils.get_loop_info", return_value=None)

    result = evaluator.evaluate(str(file_path))

    assert any(
        "Silence after stab 'Stab1' is too short (50.00ms)" in issue
        for issue in result.issues
    )
    assert result.average_silence_between_stabs_ms == pytest.approx(50.0)

# pylint: disable=redefined-outer-name
def test_tempo_key_estimation(
    evaluator_fixture: VocalChopEvaluator, temp_wav_file_fixture: str, mocker: Any
):
    """Tests tempo and key estimation when metadata is missing."""
    mocker.patch(
        "src.utils.soundfile_utils.get_cue_markers", return_value=[]
    )
    mocker.patch(
        "src.utils.soundfile_utils.get_instrument_info", return_value=None
    )
    mocker.patch(
        "src.utils.soundfile_utils.get_loop_info", return_value=None
    )
    mocker.patch(
        "librosa.onset.onset_detect", return_value=np.array([])
    )

    spy_beat_track = mocker.spy(librosa.beat, "beat_track")
    spy_chroma_stft = mocker.spy(librosa.feature, "chroma_stft")

    result = evaluator_fixture.evaluate(temp_wav_file_fixture)

    spy_beat_track.assert_called_once()
    spy_chroma_stft.assert_called_once()

    assert result.tempo is not None
    assert result.key is not None
    assert any("Tempo estimated using librosa" in issue for issue in result.issues)
    assert any(
        "Key estimated using librosa (basic chroma)" in issue for issue in result.issues
    )

# pylint: disable=redefined-outer-name
def test_click_pop_stub(
    evaluator_fixture: VocalChopEvaluator, temp_wav_file_fixture: str, mocker: Any
):
    """Tests that click_pop_detected is False due to the stubbed detector."""
    mocker.patch(
        "src.utils.soundfile_utils.get_cue_markers",
        return_value=[SFCuePoint(indx=1, position=0, name=b"s")],
    )
    mocker.patch("src.utils.soundfile_utils.get_instrument_info", return_value=None)
    mocker.patch("src.utils.soundfile_utils.get_loop_info", return_value=None)

    spy_detect_clicks_pops = mocker.spy(evaluator_fixture, "_detect_clicks_pops")

    result = evaluator_fixture.evaluate(temp_wav_file_fixture)

    spy_detect_clicks_pops.assert_called()
    assert not result.click_pop_detected
    assert not any("Potential clicks/pops detected" in issue for issue in result.issues)


# TODO:
# - Test specific audio for denoising_recommended (requires noise in silence)
# - Test actual click/pop detection once implemented.
# - Test edge cases for stab definitions (e.g., stabs overlapping, file starting/ending with stab).
# - Test multi-channel files if specific channel handling is expected beyond mono conversion.
# - Test key estimation with more varied audio to see how robust basic chroma is.
# - Test error paths, e.g. if librosa.load fails
# - Test `ideal_characteristics` variations (e.g., require_cue_labels=False)
