"""Tests for the SlicingStage."""

import os
import json
import tempfile
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from src.core.stages.slicing_stage import SlicingStage
from src.database.models import SampleModel, RecordingModel, SampleStatus


@pytest.fixture
def slicing_stage():
    """Create a SlicingStage instance."""
    return SlicingStage()


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = MagicMock()
    recording = MagicMock(spec=RecordingModel)
    recording.id = 1
    recording.file_path = "/test/audio.wav"
    recording.name = "test_audio.wav"
    session.get.return_value = recording
    return session


@pytest.fixture
def mock_context(mock_db_session, tmp_path):
    """Create a mock context with all required keys."""
    return {
        "db_session": mock_db_session,
        "recording_id": 1,
        "project_id": 1,
        "output_sample_dir": str(tmp_path / "samples"),
    }


class TestSlicingStageProperties:
    def test_name(self, slicing_stage):
        assert slicing_stage.name == "slicing"

    def test_input_type(self, slicing_stage):
        assert slicing_stage.input_type == "file_path"

    def test_output_type(self, slicing_stage):
        assert slicing_stage.output_type == "list_of_sample_data"

    def test_default_params_has_expected_keys(self, slicing_stage):
        params = slicing_stage.default_params
        assert "bit_depth" in params
        assert "normalize" in params
        assert "sample_type" in params
        assert params["bit_depth"] == 24


class TestSlicingStageValidation:
    def test_raises_without_context(self, slicing_stage):
        with pytest.raises(ValueError, match="Context is required"):
            slicing_stage.process("test.wav", {}, None)

    def test_raises_missing_db_session(self, slicing_stage):
        context = {
            "recording_id": 1,
            "project_id": 1,
            "output_sample_dir": "/tmp",
        }
        with pytest.raises(ValueError, match="Missing required key 'db_session'"):
            slicing_stage.process("test.wav", {}, context)

    def test_raises_missing_recording_id(self, slicing_stage):
        context = {
            "db_session": MagicMock(),
            "project_id": 1,
            "output_sample_dir": "/tmp",
        }
        with pytest.raises(ValueError, match="Missing required key 'recording_id'"):
            slicing_stage.process("test.wav", {}, context)

    def test_raises_recording_not_found(self, slicing_stage, mock_context):
        mock_context["db_session"].get.return_value = None
        with pytest.raises(ValueError, match="Recording with id 1 not found"):
            slicing_stage.process("test.wav", {}, mock_context)


class TestSlicingStageProcessing:
    def test_slice_with_predefined_points(self, slicing_stage, mock_context, tmp_path):
        """Test slicing with explicit slice points."""
        stage = SlicingStage()

        # Set up test audio data
        sr = 44100
        duration = 3.0
        test_audio = np.sin(
            2 * np.pi * 440 * np.linspace(0, duration, int(sr * duration))
        ).astype(np.float32)
        stage._test_audio_data = (test_audio, sr)

        slice_points = [
            {"start": 0.0, "end": 1.0},
            {"start": 1.0, "end": 2.0},
            {"start": 2.0, "end": 3.0},
        ]

        result = stage.process(
            "test_audio.wav",
            {"slice_points": slice_points},
            mock_context,
        )

        assert len(result) == 3
        for sample in result:
            assert "file_path" in sample
            assert "start_time" in sample
            assert "end_time" in sample
            assert "sample_type" in sample
            assert sample["status"] == "processed"

    def test_slice_with_start_time_end_time_keys(
        self, slicing_stage, mock_context, tmp_path
    ):
        """Test that slice points with start_time/end_time keys also work."""
        stage = SlicingStage()
        sr = 44100
        test_audio = np.zeros(sr * 2, dtype=np.float32)
        stage._test_audio_data = (test_audio, sr)

        slice_points = [
            {"start_time": 0.0, "end_time": 1.0},
            {"start_time": 1.0, "end_time": 2.0},
        ]

        result = stage.process(
            "test_audio.wav",
            {"slice_points": slice_points},
            mock_context,
        )

        assert len(result) == 2

    def test_empty_slice_points_returns_empty(self, slicing_stage, mock_context):
        """Test that providing empty slice points detects onsets automatically."""
        stage = SlicingStage()
        sr = 44100
        test_audio = np.zeros(sr * 2, dtype=np.float32)
        stage._test_audio_data = (test_audio, sr)
        stage._test_onsets = np.array([0, 22050, 44100])

        result = stage.process("test_audio.wav", {}, mock_context)
        assert isinstance(result, list)

    def test_skips_too_short_slices(self, slicing_stage, mock_context):
        """Test that slices shorter than min_sample_length_ms are skipped."""
        stage = SlicingStage()
        sr = 44100
        test_audio = np.zeros(sr * 2, dtype=np.float32)
        stage._test_audio_data = (test_audio, sr)

        slice_points = [
            {"start": 0.0, "end": 0.01},  # 10ms - below default 100ms min
        ]

        result = stage.process(
            "test_audio.wav",
            {"slice_points": slice_points, "min_sample_length_ms": 100},
            mock_context,
        )

        assert len(result) == 0

    def test_sample_type_from_slice_metadata(self, slicing_stage, mock_context):
        """Test that sample type is pulled from slice point metadata."""
        stage = SlicingStage()
        sr = 44100
        test_audio = np.zeros(sr * 2, dtype=np.float32)
        stage._test_audio_data = (test_audio, sr)

        slice_points = [
            {"start": 0.0, "end": 1.0, "type": "loop"},
        ]

        result = stage.process(
            "test_audio.wav",
            {"slice_points": slice_points},
            mock_context,
        )

        assert len(result) == 1
        assert result[0]["sample_type"] == "loop"


class TestAudioFileSaving:
    def test_save_audio_slice(self, slicing_stage, tmp_path):
        """Test that audio slices are saved correctly."""
        sr = 44100
        audio = np.sin(
            2 * np.pi * 440 * np.linspace(0, 1, sr)
        ).astype(np.float32)
        output_path = str(tmp_path / "output" / "test_slice.wav")

        slicing_stage._save_audio_slice(
            audio_data=audio,
            sample_rate=sr,
            output_path=output_path,
            bit_depth=24,
        )

        assert os.path.exists(output_path)

    def test_save_audio_slice_16bit(self, slicing_stage, tmp_path):
        """Test saving 16-bit audio."""
        sr = 44100
        audio = np.zeros(sr, dtype=np.float32)
        output_path = str(tmp_path / "test_16bit.wav")

        slicing_stage._save_audio_slice(
            audio_data=audio,
            sample_rate=sr,
            output_path=output_path,
            bit_depth=16,
        )

        assert os.path.exists(output_path)
