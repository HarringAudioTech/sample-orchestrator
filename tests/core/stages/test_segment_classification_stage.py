"""Tests for the SegmentClassificationStage."""

import pytest

from src.core.stages.segment_classification_stage import SegmentClassificationStage


@pytest.fixture
def classification_stage():
    return SegmentClassificationStage()


class TestSegmentClassificationProperties:
    def test_name(self, classification_stage):
        assert classification_stage.name == "segment_classification"

    def test_input_type(self, classification_stage):
        assert classification_stage.input_type == "audio_segments"

    def test_output_type(self, classification_stage):
        assert classification_stage.output_type == "classified_segments"


class TestSegmentClassification:
    def test_short_segments_classified_as_one_shot(self, classification_stage):
        """Segments shorter than max_one_shot_duration should be one-shots."""
        segments = [
            {"start_time": 0.0, "end_time": 0.5, "type": "one_shot", "metadata": {}},
            {"start_time": 0.5, "end_time": 1.5, "type": "one_shot", "metadata": {}},
        ]
        result = classification_stage.process(segments)

        assert len(result) == 2
        assert result[0]["type"] == "one_shot"
        assert result[1]["type"] == "one_shot"
        assert result[0]["metadata"]["classification_confidence"] > 0

    def test_long_segments_classified_as_ambient(self, classification_stage):
        """Segments longer than ambient_min_duration should be ambient."""
        segments = [
            {"start_time": 0.0, "end_time": 10.0, "type": "one_shot", "metadata": {}},
        ]
        result = classification_stage.process(segments)

        assert result[0]["type"] == "ambient"

    def test_medium_segments_classified_as_loop(self, classification_stage):
        """Segments between one-shot and ambient should be loops."""
        segments = [
            {"start_time": 0.0, "end_time": 3.0, "type": "one_shot", "metadata": {}},
        ]
        result = classification_stage.process(segments)

        assert result[0]["type"] == "loop"

    def test_metadata_added_to_segments(self, classification_stage):
        """Segments without metadata dict get one added."""
        segments = [
            {"start_time": 0.0, "end_time": 1.0},
        ]
        result = classification_stage.process(segments)

        assert "metadata" in result[0]
        assert "classification_confidence" in result[0]["metadata"]
        assert "classification_reason" in result[0]["metadata"]

    def test_empty_input(self, classification_stage):
        """Empty input returns empty output."""
        result = classification_stage.process([])
        assert result == []

    def test_project_type_from_context(self, classification_stage):
        """Test that project_type can come from context."""
        segments = [
            {"start_time": 0.0, "end_time": 1.0, "type": "one_shot", "metadata": {}},
        ]
        context = {"project_type": "sample_pack"}
        result = classification_stage.process(segments, {}, context)

        assert len(result) == 1
