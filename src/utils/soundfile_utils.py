"""
Utility functions for interacting with standard audio file metadata
using soundfile's high-level API.
"""

import logging
import soundfile  # type: ignore # pylint: disable=import-error

logger = logging.getLogger(__name__)


def write_standard_metadata(
    file_path: str,
    title: str = None,
    artist: str = None,
    comment: str = None,
    software: str = None,
    copyright_str: str = None,
    album: str = None,
    license_str: str = None,
    tracknumber: str = None,
    genre: str = None,
    date: str = None,  # Added date based on common tags
) -> bool:
    """
    Writes standard metadata tags to an audio file using soundfile's high-level API.
    Returns True if successful, False otherwise.
    """
    success_count = 0
    total_attempts = 0

    try:
        with soundfile.SoundFile(file_path, "r+") as sf_obj:
            metadata_map = {
                "title": title,
                "artist": artist,
                "comment": comment,
                "software": software,
                "copyright": copyright_str,  # SoundFile uses 'copyright'
                "album": album,
                "license": license_str,  # SoundFile uses 'license'
                "tracknumber": tracknumber,
                "genre": genre,
                "date": date,
            }

            for attr_name, value in metadata_map.items():
                if value is not None:
                    total_attempts += 1
                    try:
                        setattr(sf_obj, attr_name, value)
                        logger.debug(
                            "Successfully set metadata tag '%s' in %s",
                            attr_name,
                            file_path,
                        )
                        success_count += 1
                    except AttributeError:
                        logger.warning(
                            "Failed to set metadata tag '%s' on SoundFile object for %s. "
                            "The attribute might be read-only or not supported by the format.",
                            attr_name,
                            file_path,
                        )
                    except Exception as e:
                        logger.error(
                            "Error setting metadata tag '%s' in %s: %s",
                            attr_name,
                            file_path,
                            e,
                        )

            if total_attempts > 0:  # Only flush if we attempted to write something
                sf_obj.flush()
                logger.info("Metadata flush called for %s", file_path)

        # Consider successful if at least one attribute was attempted and set,
        # or if no attributes were attempted (vacuously true).
        # A more stringent check might be `success_count == total_attempts` if all must succeed.
        if total_attempts == 0:
            return True  # No metadata to write, so technically successful.
        return (
            success_count > 0
        )  # Or success_count == total_attempts for stricter success

    except soundfile.LibsndfileError as e:
        logger.error(
            "LibsndfileError in write_standard_metadata for %s: %s", file_path, e
        )
        return False
    except Exception as e:
        logger.error(
            "Generic exception in write_standard_metadata for %s: %s", file_path, e
        )
        return False


def read_standard_metadata(file_path: str) -> dict:
    """
    Reads standard metadata tags from an audio file.
    Attempts to use sf_obj.copy_metadata() if available, otherwise reads known tags.
    """
    metadata = {}
    try:
        with soundfile.SoundFile(file_path, "r") as sf_obj:
            # Check if copy_metadata method exists (newer soundfile versions)
            if hasattr(sf_obj, "copy_metadata") and callable(sf_obj.copy_metadata):
                logger.debug("Using copy_metadata() for %s", file_path)
                # copy_metadata might not exist or might not be callable in older versions
                # or if the file format doesn't support rich metadata copying this way.
                # It typically returns a dict-like object or a custom metadata object.
                # We'll try to convert it to a plain dict.
                copied_meta = sf_obj.copy_metadata()
                if copied_meta:  # Ensure it's not None or empty
                    if isinstance(copied_meta, dict):
                        return copied_meta
                    # If it's not a dict, iterate known attributes (as a fallback)
                    # or try to convert if it's a known type (e.g., soundfile.Metadata)
                    # For simplicity, we'll just fall through to manual attribute reading
                    # if it's not directly a dict.
                    logger.info(
                        "copy_metadata() for %s did not return a dict, trying manual.",
                        file_path,
                    )

            # Manually read known standard tags if copy_metadata wasn't suitable/available
            # These are common attributes exposed by SoundFile objects
            logger.debug("Manually reading metadata tags for %s", file_path)
            for attr_name in [
                "title",
                "artist",
                "comment",
                "software",
                "copyright",
                "album",
                "license",
                "tracknumber",
                "genre",
                "date",
            ]:
                try:
                    value = getattr(sf_obj, attr_name, None)
                    if value is not None:
                        metadata[attr_name] = value
                except Exception as e:
                    logger.debug(
                        "Could not read metadata tag '%s' from %s: %s",
                        attr_name,
                        file_path,
                        e,
                    )
    except soundfile.LibsndfileError as e:
        logger.error(
            "LibsndfileError in read_standard_metadata for %s: %s", file_path, e
        )
    except Exception as e:
        logger.error(
            "Generic exception in read_standard_metadata for %s: %s", file_path, e
        )
    return metadata


if __name__ == "__main__":
    # Example Usage
    logging.basicConfig(level=logging.DEBUG)
    DUMMY_FILE = "dummy_metadata_test.wav"

    # Create a dummy WAV file
    try:
        import numpy as np

        samplerate = 44100
        data = np.random.uniform(-0.5, 0.5, samplerate)  # 1 second of audio
        soundfile.write(DUMMY_FILE, data, samplerate)
        logger.info("Created dummy file: %s", DUMMY_FILE)
    except Exception as e:
        logger.error("Could not create dummy WAV file for example: %s", e)
        # exit() # Or handle more gracefully

    if soundfile.check_format(DUMMY_FILE):  # Check if file was created successfully
        # Write metadata
        logger.info("Attempting to write metadata to %s", DUMMY_FILE)
        write_success = write_standard_metadata(
            DUMMY_FILE,
            title="Test Title",
            artist="Test Artist",
            comment="This is a test comment with various details.",
            software="Metadata Test Script",
            date="2024-07-15",
            genre="Electronic",
        )
        if write_success:
            logger.info("Metadata written successfully (or partially).")
        else:
            logger.error("Failed to write metadata.")

        # Read metadata
        logger.info("Attempting to read metadata from %s", DUMMY_FILE)
        read_meta = read_standard_metadata(DUMMY_FILE)
        if read_meta:
            logger.info("Metadata read:")
            for key, value in read_meta.items():
                logger.info("  %s: %s", key, value)
        else:
            logger.warning("No metadata read or file empty/corrupt.")

        # Clean up dummy file
        try:
            import os

            os.remove(DUMMY_FILE)
            logger.info("Cleaned up dummy file: %s", DUMMY_FILE)
        except Exception as e:
            logger.error("Could not clean up dummy file %s: %s", DUMMY_FILE, e)
    else:
        logger.error(
            "Dummy file %s not found or is not a valid sound file.", DUMMY_FILE
        )
