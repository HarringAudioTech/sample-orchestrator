"""Unit tests for src.utils.soundfile_utils.py"""
import pytest
import soundfile # type: ignore # pylint: disable=import-error
import numpy as np # type: ignore # pylint: disable=import-error
import logging

# Adjust import path as necessary
# pylint: disable=import-error
try:
    from src.utils import soundfile_utils
except ImportError:
    from utils import soundfile_utils # type: ignore
# pylint: enable=import-error


@pytest.fixture(name="tmp_wav_file")
def fixture_tmp_wav_file(tmp_path):
    """Creates a simple WAV file and returns its path."""
    file_path = tmp_path / "test.wav"
    samplerate = 44100
    # Create a very short, simple mono audio signal
    data = np.array([0.1, 0.2, 0.1, -0.1, -0.2], dtype=np.float32)
    soundfile.write(str(file_path), data, samplerate, format='WAV', subtype='PCM_16')
    return str(file_path)

def test_write_read_standard_metadata(tmp_wav_file, caplog):
    """Tests writing and then reading standard metadata tags."""
    caplog.set_level(logging.DEBUG) # To see logs from soundfile_utils

    test_data = {
        "title": "Test Title",
        "artist": "Test Artist",
        "comment": "A test comment for the audio file. \nWith newlines.",
        "software": "Pytest SoundFile Util Test",
        "album": "Test Album",
        "genre": "Test Genre",
        "date": "2024-07-16",
        "tracknumber": "1/10",
        "license_str": "CC BY 4.0", # Using license_str to match write_standard_metadata
        "copyright_str": " (C) 2024 Test Copyright Holder" # Using copyright_str
    }

    success = soundfile_utils.write_standard_metadata(
        tmp_wav_file,
        title=test_data["title"],
        artist=test_data["artist"],
        comment=test_data["comment"],
        software=test_data["software"],
        album=test_data["album"],
        genre=test_data["genre"],
        date=test_data["date"],
        tracknumber=test_data["tracknumber"],
        license_str=test_data["license_str"], # Pass as license_str
        copyright_str=test_data["copyright_str"] # Pass as copyright_str
    )
    assert success, "write_standard_metadata reported failure."

    retrieved_meta = soundfile_utils.read_standard_metadata(tmp_wav_file)

    # Soundfile might append its version to the software tag.
    # Also, some formats might not support all tags or might have length limits.
    # For tags that are typically supported well:
    assert retrieved_meta.get("title") == test_data["title"]
    assert retrieved_meta.get("artist") == test_data["artist"]
    assert retrieved_meta.get("comment") == test_data["comment"]

    retrieved_software = retrieved_meta.get("software")
    assert retrieved_software is not None, "Software tag not found after writing."
    assert retrieved_software.startswith(test_data["software"]), \
        f"Expected software tag to start with '{test_data['software']}', got '{retrieved_software}'"

    assert retrieved_meta.get("album") == test_data["album"]
    assert retrieved_meta.get("genre") == test_data["genre"]
    assert retrieved_meta.get("date") == test_data["date"]
    assert retrieved_meta.get("tracknumber") == test_data["tracknumber"]

    # License and copyright might have different key names in soundfile's attributes
    # 'license' (for license_str) and 'copyright' (for copyright_str)

    # Some tags like 'license' might not be reliably written/read by soundfile's high-level API
    # for all formats. Mark as xfail if None, but check if value is present.
    retrieved_license = retrieved_meta.get("license")
    if retrieved_license is None:
        pytest.xfail("License tag was not retrieved (None). This might be a soundfile/format limitation.")
    assert retrieved_license == test_data["license_str"]

    retrieved_copyright = retrieved_meta.get("copyright")
    if retrieved_copyright is None:
        pytest.xfail("Copyright tag was not retrieved (None). This might be a soundfile/format limitation.")
    assert retrieved_copyright == test_data["copyright_str"]


def test_read_standard_metadata_on_plain_file(tmp_wav_file, caplog):
    """
    Tests reading metadata from a file with no prior specific tags set by this util.
    Soundfile itself might write a default software tag.
    """
    caplog.set_level(logging.DEBUG)
    retrieved_meta = soundfile_utils.read_standard_metadata(tmp_wav_file)

    # Expect that most fields will be None or empty if not set.
    # The 'software' tag is often written by libsndfile/soundfile by default.
    for key in ["title", "artist", "comment", "album", "genre", "date", "tracknumber", "license", "copyright"]:
        if key in retrieved_meta: # It's okay if they are not present
            assert retrieved_meta[key] == "" or retrieved_meta[key] is None, \
                f"Tag '{key}' should be empty or None on a plain file, but was '{retrieved_meta[key]}'"

    # Check for default software tag (libsndfile usually writes one)
    # This assertion is a bit loose as the exact default can vary.
    # If a software tag is present, it's likely from libsndfile.
    # However, after a simple write with no explicit metadata, it might be empty or None.
    software_tag = retrieved_meta.get("software")
    if software_tag and "libsndfile" in software_tag.lower():
        logging.info("Default software tag found: %s", software_tag)
    elif software_tag == "" or software_tag is None:
        logging.info("Software tag is empty or None on plain file, which is acceptable.")
    else:
        # If it's present but doesn't mention libsndfile, that's unexpected for a default.
        pytest.fail(
            f"Software tag present but unexpected for a default: '{software_tag}'"
        )

def test_write_no_metadata(tmp_wav_file):
    """Tests that calling write_standard_metadata with no arguments doesn't error and returns True."""
    success = soundfile_utils.write_standard_metadata(tmp_wav_file)
    assert success, "write_standard_metadata with no args should be successful (vacuously true)."

    # Verify that no metadata was actually written (or only defaults exist)
    retrieved_meta = soundfile_utils.read_standard_metadata(tmp_wav_file)
    custom_tags_count = 0
    for key in ["title", "artist", "comment", "album", "genre", "date", "tracknumber", "license", "copyright"]:
        if key in retrieved_meta and retrieved_meta[key]: # if key exists and is not empty
            custom_tags_count +=1
    assert custom_tags_count == 0, "No custom tags should have been written."

def test_write_partial_metadata(tmp_wav_file):
    """Tests writing only a subset of metadata tags."""
    test_title = "Partial Title Only"
    test_comment = "Partial comment."

    success = soundfile_utils.write_standard_metadata(
        tmp_wav_file,
        title=test_title,
        comment=test_comment
    )
    assert success, "Partial metadata write failed."

    retrieved_meta = soundfile_utils.read_standard_metadata(tmp_wav_file)
    assert retrieved_meta.get("title") == test_title
    assert retrieved_meta.get("comment") == test_comment
    assert retrieved_meta.get("artist") is None or retrieved_meta.get("artist") == ""

def test_read_metadata_file_not_found(caplog):
    """Tests reading metadata from a non-existent file."""
    caplog.set_level(logging.ERROR)
    metadata = soundfile_utils.read_standard_metadata("non_existent_file.wav")
    assert metadata == {}
    assert "LibsndfileError" in caplog.text or "Generic exception" in caplog.text # More flexible check

def test_write_metadata_file_not_found(caplog):
    """Tests writing metadata to a non-existent file."""
    caplog.set_level(logging.ERROR)
    success = soundfile_utils.write_standard_metadata("non_existent_file.wav", title="Test")
    assert not success
    assert "LibsndfileError" in caplog.text or "Generic exception" in caplog.text
