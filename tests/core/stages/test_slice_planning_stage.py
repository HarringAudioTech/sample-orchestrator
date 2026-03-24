"""Tests for the SlicePlanningStage."""

import pytest

from src.core.stages.slice_planning_stage import SlicePlanningStage


@pytest.fixture
def planning_stage():
    return SlicePlanningStage()


class TestSlicePlanningStageProperties:
    def test_name(self, planning_stage):
        assert planning_stage.name == "slice_planning"

    def test_input_type(self, planning_stage):
        assert planning_stage.input_type == "onset_times"

    def test_output_type(self, planning_stage):
        assert planning_stage.output_type == "audio_segments"

    def test_default_params(self, planning_stage):
        params = planning_stage.default_params
        assert "project_type" in params
        assert "min_slice_duration" in params
        assert "max_slice_duration" in params


class TestSlicePlanningProcess:
    def test_one_shot_slices_from_onsets(self, planning_stage):
        """Test planning one-shot slices from onset times."""
        onsets = [0.0, 0.5, 1.0, 1.5, 2.0]
        result = planning_stage.process(onsets, {"project_type": "sample_pack"})

        assert len(result) == 5
        for segment in result:
            assert "start_time" in segment
            assert "end_time" in segment
            assert "type" in segment
            assert "metadata" in segment
            assert segment["type"] == "one_shot"

    def test_loop_slices_for_virtual_instrument(self, planning_stage):
        """Test planning loop slices for virtual instrument project type."""
        onsets = [0.0, 1.0, 2.0, 3.0]
        result = planning_stage.process(
            onsets, {"project_type": "virtual_instrument"}
        )

        assert len(result) == 1
        assert result[0]["type"] == "loop"

    def test_empty_onsets(self, planning_stage):
        """Test with empty onset list."""
        result = planning_stage.process([], {"project_type": "sample_pack"})
        assert result == []

    def test_single_onset(self, planning_stage):
        """Test with a single onset."""
        result = planning_stage.process([0.5], {"project_type": "sample_pack"})
        assert len(result) == 1
        assert result[0]["start_time"] == 0.5

    def test_numpy_array_input(self, planning_stage):
        """Test that numpy array inputs are handled."""
        import numpy as np

        onsets = np.array([0.0, 0.5, 1.0])
        result = planning_stage.process(onsets, {"project_type": "sample_pack"})
        assert len(result) == 3

    def test_respects_min_slice_duration(self, planning_stage):
        """Test that minimum slice duration is enforced."""
        onsets = [0.0, 0.01]  # Very close together
        params = {"project_type": "sample_pack", "min_slice_duration": 0.05}
        result = planning_stage.process(onsets, params)

        for segment in result:
            duration = segment["end_time"] - segment["start_time"]
            assert duration >= 0.05

    def test_project_type_from_context(self, planning_stage):
        """Test that project_type can come from context."""
        onsets = [0.0, 1.0, 2.0]
        context = {"project_type": "virtual_instrument"}
        result = planning_stage.process(onsets, {}, context)

        assert len(result) == 1
        assert result[0]["type"] == "loop"

    def test_project_type_enum_value(self, planning_stage):
        """Test that ProjectType enum values are handled."""
        from src.database.models import ProjectType

        onsets = [0.0, 1.0]
        context = {"project_type": ProjectType.SAMPLE_PACK}
        result = planning_stage.process(onsets, {}, context)

        assert len(result) == 2
        assert all(s["type"] == "one_shot" for s in result)
