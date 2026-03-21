"""Tests for the IntelligentSlicingStage."""

import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from src.core.stages.intelligent_slicing_stage import IntelligentSlicingStage
from src.database.models import RecordingModel


@pytest.fixture
def stage():
    return IntelligentSlicingStage()


@pytest.fixture
def mock_context(tmp_path):
    session = MagicMock()
    recording = MagicMock(spec=RecordingModel)
    recording.id = 1
    recording.file_path = "/test/audio.wav"
    session.get.return_value = recording
    return {
        "db_session": session,
        "recording_id": 1,
        "project_id": 1,
        "output_sample_dir": str(tmp_path / "samples"),
    }


class TestIntelligentSlicingStageProperties:
    def test_name(self, stage):
        assert stage.name == "intelligent_slicing"

    def test_input_type(self, stage):
        assert stage.input_type == "file_path"

    def test_output_type(self, stage):
        assert stage.output_type == "list_of_sample_data"

    def test_description(self, stage):
        assert "intelligent" in stage.description.lower()


class TestIntelligentSlicingRegistration:
    def test_registered_in_stage_registry(self):
        from src.core.stage_runner import STAGE_REGISTRY

        assert "intelligent_slicing" in STAGE_REGISTRY


class TestIntelligentSlicingProcess:
    @patch("src.core.stages.intelligent_slicing_stage.OnsetDetectionStage")
    @patch("src.core.stages.intelligent_slicing_stage.SlicingStage")
    @patch("src.core.stages.intelligent_slicing_stage.QualityControlStage")
    def test_full_pipeline(self, MockQC, MockSlicing, MockOnset, stage, mock_context):
        """Test that the full pipeline is called in order."""
        # Mock onset detection
        mock_onset = MockOnset.return_value
        mock_onset.process.return_value = [0.0, 0.5, 1.0, 1.5]

        # Mock slicing
        mock_slicing = MockSlicing.return_value
        slicing_result = [
            {"id": 1, "file_path": "/test/slice_001.wav", "start_time": 0.0, "end_time": 0.5},
            {"id": 2, "file_path": "/test/slice_002.wav", "start_time": 0.5, "end_time": 1.0},
        ]
        mock_slicing.process.return_value = slicing_result

        # Mock QC to pass everything through
        mock_qc = MockQC.return_value
        mock_qc.process.return_value = slicing_result

        result = stage.process("/test/audio.wav", {}, mock_context)

        assert len(result) == 2
        mock_onset.process.assert_called_once()
        mock_slicing.process.assert_called_once()
        mock_qc.process.assert_called_once()

    @patch("src.core.stages.intelligent_slicing_stage.OnsetDetectionStage")
    @patch("src.core.stages.intelligent_slicing_stage.SlicingStage")
    def test_passes_params_to_substages(
        self, MockSlicing, MockOnset, stage, mock_context
    ):
        """Test that sub-stage params are passed correctly."""
        mock_onset = MockOnset.return_value
        mock_onset.process.return_value = [0.0, 1.0]

        mock_slicing = MockSlicing.return_value
        mock_slicing.process.return_value = []

        custom_params = {
            "onset_detection": {"sr": 48000},
            "slicing": {"bit_depth": 16},
            "enable_quality_control": False,
        }

        stage.process("/test/audio.wav", custom_params, mock_context)

        # Verify onset detection got its params
        onset_call_params = mock_onset.process.call_args[0][1]
        assert onset_call_params.get("sr") == 48000

    @patch("src.core.stages.intelligent_slicing_stage.OnsetDetectionStage")
    @patch("src.core.stages.intelligent_slicing_stage.SlicingStage")
    def test_no_onsets_returns_empty(
        self, MockSlicing, MockOnset, stage, mock_context
    ):
        """Test that no onsets produces empty result."""
        mock_onset = MockOnset.return_value
        mock_onset.process.return_value = []

        mock_slicing = MockSlicing.return_value
        mock_slicing.process.return_value = []

        result = stage.process("/test/audio.wav", {}, mock_context)
        assert result == []
