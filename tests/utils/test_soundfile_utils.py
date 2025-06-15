"""Unit tests for src.utils.soundfile_utils."""
from typing import List
import pytest
import numpy as np  # type: ignore # pylint: disable=import-error
import soundfile  # type: ignore # pylint: disable=import-error

# Adjust the import path based on your project structure.
# This assumes 'src' is a top-level directory and Python's import resolution can find it.
# If running pytest from the project root, this should work.
# pylint: disable=import-error
try:
    from src.utils.soundfile_utils import (
        get_cue_markers,
        set_cue_markers,
        SFCuePoint,
        get_instrument_info,
        set_instrument_info,
        SFInstrumentInfo,
        SFInstrumentLoop,
        get_loop_info,
        set_loop_info,
        SFLoopInfo,
        SF_LOOP_FORWARD,
        SF_LOOP_NONE,  # Import any other needed constants
    )
except ImportError:
    # Fallback for different execution context or if path needs adjustment
    from utils.soundfile_utils import ( # type: ignore
        get_cue_markers,
        set_cue_markers,
        SFCuePoint,
        get_instrument_info,
        set_instrument_info,
        SFInstrumentInfo,
        SFInstrumentLoop,
        get_loop_info,
        set_loop_info,
        SFLoopInfo,
        SF_LOOP_FORWARD,
        SF_LOOP_NONE,
    )
# pylint: enable=import-error


@pytest.fixture
def tmp_wav_file(tmp_path):
    """Creates a simple, short, empty WAV file in a temporary directory."""
    file_path = tmp_path / "test.wav"
    samplerate = 44100
    channels = 1
    duration_seconds = 0.1  # Short duration is fine for metadata tests

    # Create silent audio data
    num_frames = int(samplerate * duration_seconds)
    data = np.zeros((num_frames, channels), dtype=np.float32)

    soundfile.write(str(file_path), data, samplerate, format="WAV", subtype="PCM_16")
    return str(file_path)  # Return as string, as functions expect path strings


def assert_sfcuepoint_almost_equal(cue1: SFCuePoint, cue2: SFCuePoint):
    """Asserts that two SFCuePoint objects are almost equal, handling name encoding."""
    assert cue1.indx == cue2.indx
    assert cue1.position == cue2.position
    assert cue1.fcc_chunk == cue2.fcc_chunk
    assert cue1.chunk_start == cue2.chunk_start
    assert cue1.block_start == cue2.block_start
    assert cue1.sample_offset == cue2.sample_offset

    # Decode names for comparison, handling potential null bytes
    name1_decoded = cue1.name.split(b"\x00", 1)[0].decode("utf-8", "replace")
    name2_decoded = cue2.name.split(b"\x00", 1)[0].decode("utf-8", "replace")
    assert name1_decoded == name2_decoded


def assert_cues_equal(list1: List[SFCuePoint], list2: List[SFCuePoint]):
    """Asserts that two lists of SFCuePoint objects are equal."""
    assert len(list1) == len(list2)
    for cue1, cue2 in zip(
        sorted(list1, key=lambda c: c.indx), sorted(list2, key=lambda c: c.indx)
    ):
        assert_sfcuepoint_almost_equal(cue1, cue2)


# --- Test Functions ---


def test_get_metadata_empty_file(tmp_wav_file): # pylint: disable=redefined-outer-name
    """Tests that getting metadata from a file with no prior metadata returns empty/None."""
    assert get_cue_markers(tmp_wav_file) == []
    assert get_instrument_info(tmp_wav_file) is None
    retrieved_loop_info = get_loop_info(tmp_wav_file)
    if retrieved_loop_info is not None:
        assert retrieved_loop_info.bpm == 0.0
        assert retrieved_loop_info.loop_mode == SF_LOOP_NONE
    else:
        assert retrieved_loop_info is None


def test_cue_markers_set_get(tmp_wav_file): # pylint: disable=redefined-outer-name
    """Tests setting and getting cue markers."""
    test_cues = [
        SFCuePoint(indx=1, position=1000, name="Cue 1".encode("utf-8")),
        SFCuePoint(indx=2, position=2000, name="Cue Marker Two".encode("utf-8")),
        SFCuePoint(
            indx=3, position=3000, name="Test Cue Γειά σου".encode("utf-8")
        ),
    ]

    success_set = set_cue_markers(tmp_wav_file, test_cues)
    assert success_set, "Setting cue markers failed."

    retrieved_cues = get_cue_markers(tmp_wav_file)
    assert_cues_equal(test_cues, retrieved_cues)


def test_set_empty_cues(tmp_wav_file): # pylint: disable=redefined-outer-name
    """Tests setting an empty list of cues, which should remove existing cues."""
    initial_cues = [SFCuePoint(indx=1, position=500, name="Initial".encode("utf-8"))]
    assert set_cue_markers(
        tmp_wav_file, initial_cues
    ), "Initial set_cue_markers failed."
    assert len(get_cue_markers(tmp_wav_file)) == 1, "Initial cues not set correctly."

    assert set_cue_markers(tmp_wav_file, []), "set_cue_markers with empty list failed."
    retrieved_cues_after_empty_set = get_cue_markers(tmp_wav_file)
    assert (
        retrieved_cues_after_empty_set == []
    ), "Cues were not cleared by setting an empty list."


def test_instrument_info_set_get(tmp_wav_file): # pylint: disable=redefined-outer-name
    """Tests setting and getting instrument information."""
    test_instr_info = SFInstrumentInfo(
        gain=1,
        basenote=60,  # MIDI C4
        detune=5,
        velocity_lo=20,
        velocity_hi=100,
        key_lo=10,
        key_hi=110,
        loop_count=1,
        loops=[SFInstrumentLoop(mode=SF_LOOP_FORWARD, start=100, end=200, count=0)],
    )

    success_set = set_instrument_info(tmp_wav_file, test_instr_info)
    assert success_set, "Setting instrument info failed."

    retrieved_instr_info = get_instrument_info(tmp_wav_file)
    assert retrieved_instr_info is not None, "Getting instrument info returned None."

    assert retrieved_instr_info.gain == test_instr_info.gain
    assert retrieved_instr_info.basenote == test_instr_info.basenote
    assert retrieved_instr_info.detune == test_instr_info.detune
    assert retrieved_instr_info.velocity_lo == test_instr_info.velocity_lo
    assert retrieved_instr_info.velocity_hi == test_instr_info.velocity_hi
    assert retrieved_instr_info.key_lo == test_instr_info.key_lo
    assert retrieved_instr_info.key_hi == test_instr_info.key_hi
    assert retrieved_instr_info.loop_count == test_instr_info.loop_count

    assert len(retrieved_instr_info.loops) == test_instr_info.loop_count
    if (
        test_instr_info.loop_count > 0 and retrieved_instr_info.loops
    ):
        assert retrieved_instr_info.loops[0].mode == test_instr_info.loops[0].mode
        assert retrieved_instr_info.loops[0].start == test_instr_info.loops[0].start
        assert retrieved_instr_info.loops[0].end == test_instr_info.loops[0].end
        assert retrieved_instr_info.loops[0].count == test_instr_info.loops[0].count


def test_loop_info_set_get(tmp_wav_file): # pylint: disable=redefined-outer-name
    """Tests setting and getting loop information."""
    test_loop_info = SFLoopInfo(
        time_sig_num=3,
        time_sig_den=4,
        loop_mode=SF_LOOP_FORWARD,
        num_beats=16,
        bpm=125.5,
        root_key=69,  # MIDI A4
        future=(1, 2, 3, 4, 5, 6),
    )

    success_set = set_loop_info(tmp_wav_file, test_loop_info)
    assert success_set, "Setting loop info failed."

    retrieved_loop_info = get_loop_info(tmp_wav_file)
    assert retrieved_loop_info is not None, "Getting loop info returned None."

    assert retrieved_loop_info.time_sig_num == test_loop_info.time_sig_num
    assert retrieved_loop_info.time_sig_den == test_loop_info.time_sig_den
    assert retrieved_loop_info.loop_mode == test_loop_info.loop_mode
    assert retrieved_loop_info.num_beats == test_loop_info.num_beats
    assert pytest.approx(retrieved_loop_info.bpm) == test_loop_info.bpm
    assert retrieved_loop_info.root_key == test_loop_info.root_key
    assert tuple(retrieved_loop_info.future) == test_loop_info.future


def test_unicode_cue_names(tmp_wav_file): # pylint: disable=redefined-outer-name
    """Tests setting cue names with various unicode characters."""
    unicode_label = "Test Γειά σου 世界"
    test_cues = [SFCuePoint(indx=1, position=100, name=unicode_label.encode("utf-8"))]

    assert set_cue_markers(
        tmp_wav_file, test_cues
    ), "Setting unicode cue marker failed."
    retrieved_cues = get_cue_markers(tmp_wav_file)
    assert len(retrieved_cues) == 1

    retrieved_name = (
        retrieved_cues[0].name.split(b"\x00", 1)[0].decode("utf-8", "replace")
    )
    assert retrieved_name == unicode_label


# TODO: Add more tests:
# - Edge cases for sample positions (e.g., 0, end of file).
# - Maximum number of cues (if there's a limit enforced by the utils or libsndfile SF_CUES).
# - Different audio file formats if the utils are expected to support them for metadata.
# - Error handling: What happens if set_* functions are called on a read-only file?
#   (Requires opening file in 'r' mode, then trying to set - soundfile_utils should handle this).
# - Behavior of get_* functions when a file has malformed metadata chunks (hard to test).
# - Test with different data types for audio if that affects metadata writing.
#   The current tmp_wav_file uses float32 then written as PCM_16.
# - Test SFInstrumentInfo with more loops.
# - Test basenote and other char fields in SFInstrumentInfo with tricky values.
# - Test SFLoopInfo with SF_LOOP_NONE and other loop modes.
# - Test name field truncation in SFCuePoint if a name > 255 bytes is provided.


def test_cue_name_truncation(tmp_wav_file): # pylint: disable=redefined-outer-name
    """Tests that cue names are properly truncated if too long."""
    long_name = "a" * 300
    expected_name_bytes = long_name.encode('utf-8')[:255]


    cue_with_long_name = SFCuePoint(
        indx=1, position=100, name=long_name.encode("utf-8")
    )

    set_success = set_cue_markers(tmp_wav_file, [cue_with_long_name])
    assert set_success

    retrieved_cues = get_cue_markers(tmp_wav_file)
    assert len(retrieved_cues) == 1

    assert retrieved_cues[0].name == expected_name_bytes
    assert (
        len(retrieved_cues[0].name) == 255
    )
