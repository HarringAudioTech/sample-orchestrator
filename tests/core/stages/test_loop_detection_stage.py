"""Tests for LoopDetectionStage."""

import numpy as np
import pytest
import soundfile as sf
from unittest.mock import MagicMock, patch

from src.core.stages.loop_detection_stage import LoopDetectionStage
from src.core.loop_evaluator import (
    LoopCandidate,
    LoopDetectionResult,
    LoopHeuristicScores,
    ScoredLoopCandidate,
)

SR = 22050


@pytest.fixture
def stage():
    return LoopDetectionStage()


@pytest.fixture
def click_wav(tmp_path):
    """Write an 8-second click track at 120 BPM."""
    beat_interval = 0.5  # 120 BPM
    duration = 8.0
    n_samples = int(SR * duration)
    y = np.zeros(n_samples, dtype=np.float32)
    click_len = min(int(0.005 * SR), 110)
    t = 0.0
    while t < duration:
        idx = int(t * SR)
        end = min(idx + click_len, n_samples)
        y[idx:end] = 0.8 * np.sin(
            2 * np.pi * 1000 * np.arange(end - idx) / SR
        )
        t += beat_interval
    path = str(tmp_path / "click.wav")
    sf.write(path, y, SR)
    return path


# ---------------------------------------------------------------------------
# Stage property tests
# ---------------------------------------------------------------------------


class TestStageProperties:
    def test_name(self, stage):
        assert stage.name == "loop_detection"

    def test_description(self, stage):
        assert "loop" in stage.description.lower()

    def test_input_type(self, stage):
        assert stage.input_type == "file_path"

    def test_output_type(self, stage):
        assert stage.output_type == "slice_points"

    def test_default_params(self, stage):
        params = stage.default_params
        assert "max_candidates" in params
        assert "min_loop_duration" in params
        assert "max_loop_duration" in params
        assert "min_score" in params


# ---------------------------------------------------------------------------
# Registration test
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_stage_is_registered(self):
        from src.core.stage_runner import STAGE_REGISTRY

        # The import of the module triggers registration.
        assert LoopDetectionStage in STAGE_REGISTRY.values()


# ---------------------------------------------------------------------------
# Process output format tests
# ---------------------------------------------------------------------------


class TestProcess:
    def test_returns_list_of_dicts(self, stage, click_wav):
        result = stage.process(click_wav)
        assert isinstance(result, list)
        # May be empty if min_score filters everything, but should be a list
        for item in result:
            assert isinstance(item, dict)

    def test_slice_point_format(self, stage, click_wav):
        result = stage.process(click_wav, params={"min_score": 0.0})
        if not result:
            pytest.skip("No candidates returned")
        item = result[0]
        assert "start_time" in item
        assert "end_time" in item
        assert item["type"] == "loop"
        assert "metadata" in item
        meta = item["metadata"]
        assert "confidence" in meta
        assert meta["source"] == "loop_detection"
        assert "loop_scores" in meta
        assert "rank" in meta

    def test_context_receives_result(self, stage, click_wav):
        context = {}
        stage.process(click_wav, context=context)
        assert "loop_detection_result" in context
        assert isinstance(context["loop_detection_result"], LoopDetectionResult)

    def test_max_candidates_param(self, stage, click_wav):
        result = stage.process(click_wav, params={"max_candidates": 2, "min_score": 0.0})
        assert len(result) <= 2

    def test_nonexistent_file_returns_empty(self, stage):
        result = stage.process("/nonexistent/audio.wav")
        assert result == []


# ---------------------------------------------------------------------------
# Mocked evaluator tests (fast, no librosa)
# ---------------------------------------------------------------------------


class TestWithMockedEvaluator:
    def test_process_with_mock(self, stage):
        mock_result = LoopDetectionResult(
            audio_path="/test.wav",
            sample_rate=SR,
            duration=8.0,
            detected_bpm=120.0,
            selected_candidates=[
                ScoredLoopCandidate(
                    candidate=LoopCandidate(
                        start_sample=0, end_sample=2 * SR,
                        start_time=0.0, end_time=2.0,
                        duration=2.0, duration_bars=1.0, bpm=120.0,
                    ),
                    scores=LoopHeuristicScores(
                        beat_alignment=0.9,
                        spectral_similarity=0.8,
                        duration_quantization=1.0,
                        zero_crossing_cleanliness=1.0,
                        rms_energy_consistency=0.7,
                        onset_regularity=0.6,
                        spectral_stability=0.5,
                    ),
                    overall_score=0.82,
                    rank=1,
                ),
            ],
        )

        with patch("src.core.stages.loop_detection_stage.LoopEvaluator") as MockEval:
            mock_instance = MockEval.return_value
            mock_instance.evaluate.return_value = mock_result
            result = stage.process("/test.wav")

        assert len(result) == 1
        assert result[0]["start_time"] == 0.0
        assert result[0]["end_time"] == 2.0
        assert result[0]["type"] == "loop"
        assert result[0]["metadata"]["confidence"] == pytest.approx(0.82)
        assert result[0]["metadata"]["rank"] == 1
        assert result[0]["metadata"]["loop_scores"]["beat_alignment"] == 0.9
