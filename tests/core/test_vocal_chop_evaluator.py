"""Unit tests for src.core.vocal_chop_evaluator."""

from typing import Tuple, Any  # Removed List as it's not directly used by tests
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
        # VocalChopEvaluationResult,
        # AnalyzedVocalStab,
    )

    # Imports for SFCuePoint, SFInstrumentInfo, SFLoopInfo removed as they are no longer used
except ImportError:
    from core.vocal_chop_evaluator import (  # type: ignore
        VocalChopEvaluator,
        VocalChopIdealCharacteristics,
    )
# pylint: enable=import-error


# --- Fixtures ---


@pytest.fixture
def ideal_characteristics_fixture() -> VocalChopIdealCharacteristics:
    """Returns a default VocalChopIdealCharacteristics instance."""
    return VocalChopIdealCharacteristics()


@pytest.fixture
def evaluator_fixture(  # pylint: disable=redefined-outer-name
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
def temp_wav_file_fixture(  # pylint: disable=redefined-outer-name
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

    # Mock librosa functions that would be called since metadata is absent
    mocker.patch(
        "librosa.onset.onset_detect", return_value=np.array([])
    )  # No onsets found
    mocker.patch(
        "librosa.beat.beat_track", return_value=(0.0, np.array([]))
    )  # No tempo
    # Mock key estimation to return a default or None
    mocker.patch(
        "librosa.feature.chroma_stft", return_value=np.random.rand(12, 10)
    )  # Dummy chroma
    mocker.patch("librosa.midi_to_note", return_value="C")

    result = evaluator_fixture.evaluate(temp_wav_file_fixture)

    assert result.sample_rate == sr
    assert result.channels == 1
    assert result.duration_ms == pytest.approx(1000.0)

    assert not result.metadata_tempo_present
    assert not result.metadata_key_present
    assert not result.metadata_tempo_present  # Detailed metadata flags will be False
    assert not result.metadata_key_present
    assert not result.cue_markers_present
    assert not result.cue_labels_present

    # Check if tempo estimation was attempted and if it failed (due to mock returning 0.0)
    assert result.tempo is None
    assert any(
        "Tempo estimation failed or returned zero" in issue for issue in result.issues
    )

    # Check if key estimation was attempted (mocked to return "C")
    assert result.key == "C"
    assert any("Key estimated using librosa" in issue for issue in result.issues)

    # Check for the specific issue related to no detailed cues
    assert any(
        "Detailed cue marker metadata (e.g. from CUE chunks) is no longer read" in issue
        for issue in result.issues
    )


# pylint: disable=redefined-outer-name
def test_evaluate_with_onsets_and_estimations(  # Renamed from test_evaluate_with_full_metadata
    evaluator_fixture: VocalChopEvaluator, temp_wav_file_fixture: str, mocker: Any
):
    """Tests evaluation when onsets are detected and tempo/key are estimated."""
    # Mock onset detection to return 4 onsets
    mock_onsets = np.array([100, 200, 300, 400]) * (
        44100 // 1000
    )  # Positions in samples
    mocker.patch("librosa.onset.onset_detect", return_value=mock_onsets)

    # Mock tempo estimation
    mocker.patch("librosa.beat.beat_track", return_value=(120.0, np.array([])))

    # Mock key estimation (chroma_stft -> argmax -> midi_to_note)
    # Simplified: just mock the final midi_to_note conversion
    mocker.patch("librosa.midi_to_note", return_value="Cmaj")  # Example key

    result = evaluator_fixture.evaluate(temp_wav_file_fixture)

    assert (
        not result.metadata_tempo_present
    )  # Will be false as we don't read detailed metadata
    assert not result.metadata_key_present  # Will be false
    assert not result.cue_markers_present  # Will be false
    assert not result.cue_labels_present  # Will be false

    assert result.tempo == 120.0
    assert result.key == "Cmaj"

    assert len(result.stabs) == 4
    # Stab labels will be None as they are not derived from onsets
    assert result.stabs[0].label is None
    assert result.stab_count_is_power_of_2  # 4 is a power of 2

    assert any("Tempo estimated using librosa" in issue for issue in result.issues)
    assert any("Key estimated using librosa" in issue for issue in result.issues)
    assert "Stab detected by onset analysis, not from cues." in result.stabs[0].issues


# pylint: disable=redefined-outer-name
def test_evaluate_missing_cue_labels(  # This test's premise is now less relevant
    evaluator_fixture: VocalChopEvaluator, temp_wav_file_fixture: str, mocker: Any
):
    """
    Original: Tests evaluation when cue markers are present but lack labels.
    New: Since detailed cues aren't read, this tests that cue_labels_present is false
    and relevant issue is logged if ideal_characteristics.require_cue_labels is True.
    """
    # Onsets will be detected instead of cues
    mocker.patch("librosa.onset.onset_detect", return_value=np.array([100, 200]))
    mocker.patch("librosa.beat.beat_track", return_value=(120.0, np.array([])))
    mocker.patch("librosa.midi_to_note", return_value="Cmaj")

    evaluator_fixture.ideal_characteristics.require_cue_labels = (
        True  # Ensure it's required
    )
    result = evaluator_fixture.evaluate(temp_wav_file_fixture)

    assert not result.cue_markers_present  # Detailed cues are not read
    assert not result.cue_labels_present  # Thus, no labels from them

    # The issue "Cue labels missing..." is logged if ideal_characteristics.require_cue_labels is True
    # AND cue_markers_present is True. Since cue_markers_present is now always False (for detailed cues),
    # this specific issue might not be logged. Instead, the general "Detailed cue marker metadata..." is logged.
    # The check for require_cue_labels might still add an issue if cue_markers_present was true.
    # Let's verify the evaluator's logic for this:
    # if (self.ideal_characteristics.require_cue_labels and
    #     evaluation_result.cue_markers_present and  <-- this will be false
    #     not evaluation_result.cue_labels_present):
    # So, the specific "Cue labels missing..." issue won't be logged under current logic.
    # This test might need to be re-thought or removed if it no longer tests a unique state.
    # For now, let's assert the state.
    assert not any(
        "Cue labels missing" in issue
        for issue in result.issues
        if "ideal" in issue.lower()
    )


# pylint: disable=redefined-outer-name
def test_evaluate_stab_count_not_power_of_2(
    evaluator_fixture: VocalChopEvaluator, temp_wav_file_fixture: str, mocker: Any
):
    """Tests evaluation when the number of detected onsets is not an ideal power of 2."""
    # Mock onset detection to return 3 onsets
    mock_onsets = np.array([100, 200, 300]) * (44100 // 1000)
    mocker.patch("librosa.onset.onset_detect", return_value=mock_onsets)
    mocker.patch(
        "librosa.beat.beat_track", return_value=(120.0, np.array([]))
    )  # Mock tempo/key for completeness
    mocker.patch("librosa.midi_to_note", return_value="Cmaj")

    result = evaluator_fixture.evaluate(temp_wav_file_fixture)
    assert not result.stab_count_is_power_of_2
    assert any(
        "Detected stab count (3) is not an ideal power of 2" in issue
        for issue in result.issues
    )


# pylint: disable=redefined-outer-name
def test_evaluate_no_cues_onset_detection(  # This test remains largely the same
    evaluator_fixture: VocalChopEvaluator, tmp_path: Any, mocker: Any
):
    """Tests onset detection when (as is now standard) no detailed cue markers are read."""
    sr = 44100
    y1 = np.sin(np.linspace(0, 10 * np.pi, int(0.1 * sr)))
    silence = np.zeros(int(0.2 * sr))
    y = np.concatenate([y1, silence, y1, silence, y1]).astype(np.float32)

    onset_test_file = tmp_path / "onset_test.wav"
    soundfile.write(str(onset_test_file), y, sr)

    # No need to mock soundfile_utils.get_cue_markers anymore
    mocker.patch(
        "librosa.beat.beat_track", return_value=(120.0, np.array([]))
    )  # Mock tempo/key
    mocker.patch("librosa.midi_to_note", return_value="Cmaj")

    # Mock onset detection to return 3 onsets for this test's purpose
    mock_onsets = np.array(
        [0, len(y1) + len(silence), len(y1) * 2 + len(silence) * 2]
    ).astype(int)
    mocker.patch("librosa.onset.onset_detect", return_value=mock_onsets)

    result = evaluator_fixture.evaluate(str(onset_test_file))

    assert len(result.stabs) == 3  # Expect 3 onsets as per mock
    assert all(
        "Stab detected by onset analysis, not from cues." in stab.issues
        for stab in result.stabs
    )
    assert any(
        "Detailed cue marker metadata (e.g. from CUE chunks) is no longer read" in issue
        for issue in result.issues
    )
    assert not result.stab_count_is_power_of_2  # 3 is not power of 2
    assert any(
        "Detected stab count (3) is not an ideal power of 2"
        in issue  # Check specific message
        for issue in result.issues
    )


# pylint: disable=redefined-outer-name
def test_evaluate_zero_crossings(
    evaluator_fixture: VocalChopEvaluator, tmp_path: Any, mocker: Any
):
    """Tests zero-crossing detection for stabs defined by onsets."""
    sr = 44100
    # Ensure y_clean_stab starts at 0, goes positive, comes back to 0, goes negative, and ends clearly negative.
    # Phase: 0 -> 1.9*pi. Length: 0.1 sec.
    # Starts at sin(0)=0. Ends at sin(1.9*pi) which is negative. Max at 0.5pi, min at 1.5pi. Crosses 0 at pi.
    y_clean_stab = np.sin(np.linspace(0, 1.9 * np.pi, int(0.1 * sr))).astype(np.float32)
    y_unclean_stab = (np.ones(int(0.1 * sr)) * 0.5).astype(np.float32)  # No ZCs

    clean_file = tmp_path / "zc_clean.wav"
    unclean_file = tmp_path / "zc_unclean.wav"
    soundfile.write(str(clean_file), y_clean_stab, sr)
    soundfile.write(
        str(unclean_file),
        np.concatenate(
            [y_unclean_stab, np.zeros(sr // 100), y_unclean_stab]
        ),  # Added sr//100 for sample rate
        sr,
    )

    # Mock tempo/key estimation for both test cases
    mocker.patch("librosa.beat.beat_track", return_value=(120.0, np.array([])))
    mocker.patch("librosa.midi_to_note", return_value="Cmaj")

    # Test for clean file: one stab covering the whole file
    mocker.patch("librosa.onset.onset_detect", return_value=np.array([0]))
    result_clean = evaluator_fixture.evaluate(str(clean_file))
    assert len(result_clean.stabs) == 1
    # librosa.zero_crossings (x_curr * x_prev < 0) doesn't count crossing if one sample is 0.0
    # A sine wave starting at 0.0 will thus not show a ZC at the very start by this definition.
    assert not result_clean.stabs[0].has_clean_start_zero_crossing
    assert not result_clean.stabs[
        0
    ].has_clean_end_zero_crossing  # Similarly for end if it lands on 0.0

    # Test for unclean file: two stabs corresponding to y_unclean_stab segments
    onsets_unclean = np.array([0, len(y_unclean_stab) + sr // 100])
    mocker.patch("librosa.onset.onset_detect", return_value=onsets_unclean)
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
    # The end of the second unclean stab might coincide with file end, which could be a ZC if padded with zeros by soundfile write.
    # For a raw ones-array, its end won't be a ZC. Test data ends with y_unclean_stab.
    assert not result_unclean.stabs[
        1
    ].has_clean_start_zero_crossing  # This was duplicated, keep one
    assert not result_unclean.stabs[1].has_clean_end_zero_crossing


def test_evaluate_silence_duration(tmp_path: Any, mocker: Any):
    """
    Tests silence analysis. Given current evaluator logic for onsets,
    stabs run from one onset to the next. So, "silence between stabs" will be zero.
    This test will verify that "No silence or overlap" is logged.
    """
    sr = 44100
    ideal_chars = VocalChopIdealCharacteristics(
        min_silence_duration_ms=75.0
    )  # Min silence is 75ms
    evaluator = VocalChopEvaluator(ideal_chars)

    stab_sound = np.ones(int(0.1 * sr)) * 0.5  # 100ms stab
    actual_silence_between_stabs = np.zeros(int(0.05 * sr))  # 50ms silence

    # Audio: STAB | SHORT_SILENCE | STAB
    audio_data = np.concatenate(
        [stab_sound, actual_silence_between_stabs, stab_sound]
    ).astype(np.float32)
    file_path = tmp_path / "short_silence_test.wav"
    soundfile.write(str(file_path), audio_data, sr)

    # Mock onsets to be at the start of each actual audio stab
    onset1_start = 0
    onset2_start = len(stab_sound) + len(actual_silence_between_stabs)
    mock_onsets = np.array([onset1_start, onset2_start])

    mocker.patch("librosa.onset.onset_detect", return_value=mock_onsets)
    mocker.patch("librosa.beat.beat_track", return_value=(120.0, np.array([])))
    mocker.patch("librosa.midi_to_note", return_value="Cmaj")

    result = evaluator.evaluate(str(file_path))
    # print("DEBUG: Issues for silence duration test:", result.issues) # Keep for debugging if needed

    assert len(result.stabs) == 2

    # Given evaluator's current stab definition (onset to next onset),
    # stab[0].end_sample will be onset2_start.
    # stab[1].start_sample will be onset2_start.
    # Thus, silence_start_sample == silence_end_sample in the evaluator's loop.
    expected_issue_message = "No silence or overlap between stab '1' and '2'."
    assert any(expected_issue_message in issue for issue in result.issues)
    assert (
        result.average_silence_between_stabs_ms == 0.0
    )  # Because no positive silence segments found


# pylint: disable=redefined-outer-name
def test_tempo_key_estimation(  # This test should still be valid
    evaluator_fixture: VocalChopEvaluator, temp_wav_file_fixture: str, mocker: Any
):
    """Tests tempo and key estimation when metadata is (effectively) missing."""
    # Ensure no onsets are detected to simplify focus on tempo/key estimation
    mocker.patch("librosa.onset.onset_detect", return_value=np.array([]))

    # Remove spies, just rely on mocks and check results
    mocker.patch("librosa.beat.beat_track", return_value=(135.0, np.array([])))
    dummy_chroma = np.random.rand(12, 100)
    mocker.patch("librosa.feature.chroma_stft", return_value=dummy_chroma)
    mocker.patch("librosa.midi_to_note", return_value="A#")

    result = evaluator_fixture.evaluate(temp_wav_file_fixture)

    # Check that librosa functions were called (indirectly, by checking their effect)
    assert result.tempo == 135.0  # Verifies beat_track mock was used
    assert result.key == "A#"  # Verifies chroma_stft and midi_to_note mocks were used
    assert any("Tempo estimated using librosa" in issue for issue in result.issues)
    assert any(
        "Key estimated using librosa (basic chroma)" in issue for issue in result.issues
    )


# pylint: disable=redefined-outer-name
def test_click_pop_stub(  # This test should still be valid
    evaluator_fixture: VocalChopEvaluator, temp_wav_file_fixture: str, mocker: Any
):
    """Tests that click_pop_detected is False due to the stubbed detector."""
    # Mock onsets to create at least one stab for the detector to run on
    mocker.patch("librosa.onset.onset_detect", return_value=np.array([0]))
    mocker.patch("librosa.beat.beat_track", return_value=(120.0, np.array([])))
    mocker.patch("librosa.midi_to_note", return_value="Cmaj")

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
