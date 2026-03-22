"""Tests for the LoopEvaluator loop detection and scoring module."""

import dataclasses
import os
import numpy as np
import pytest
import soundfile as sf

from src.core.loop_evaluator import (
    LoopCandidate,
    LoopDetectionResult,
    LoopEvaluator,
    LoopHeuristicScores,
    ScoredLoopCandidate,
    _clamp,
    _cosine_similarity,
)


# ---------------------------------------------------------------------------
# Fixtures – synthetic audio generators
# ---------------------------------------------------------------------------

SR = 22050  # sample rate shared by test helpers


def _sine_wave(freq: float, duration: float, sr: int = SR) -> np.ndarray:
    """Generate a pure sine tone."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    return 0.5 * np.sin(2 * np.pi * freq * t)


def _click_track(bpm: float, duration: float, sr: int = SR) -> np.ndarray:
    """Generate a click track at a given BPM (one click per beat)."""
    beat_interval = 60.0 / bpm
    n_samples = int(sr * duration)
    y = np.zeros(n_samples, dtype=np.float32)
    click_len = min(int(0.005 * sr), 110)  # 5 ms click
    t = 0.0
    while t < duration:
        idx = int(t * sr)
        end = min(idx + click_len, n_samples)
        y[idx:end] = 0.8 * np.sin(
            2 * np.pi * 1000 * np.arange(end - idx) / sr
        )
        t += beat_interval
    return y


@pytest.fixture
def sine_wav(tmp_path):
    """Write a 4-second 440 Hz sine wave and return the path."""
    path = str(tmp_path / "sine.wav")
    y = _sine_wave(440.0, 4.0)
    sf.write(path, y, SR)
    return path


@pytest.fixture
def click_wav(tmp_path):
    """Write an 8-second click track at 120 BPM and return the path."""
    path = str(tmp_path / "click.wav")
    y = _click_track(120.0, 8.0)
    sf.write(path, y, SR)
    return path


@pytest.fixture
def repeating_wav(tmp_path):
    """A 4-bar repeating pattern (2 s per bar @ 120 BPM → 8 s total)."""
    bar_dur = 2.0  # 120 BPM, 4/4
    pattern = _sine_wave(440.0, bar_dur) + 0.3 * _click_track(120.0, bar_dur)
    y = np.tile(pattern, 4)
    path = str(tmp_path / "repeating.wav")
    sf.write(path, y, SR)
    return path


@pytest.fixture
def short_wav(tmp_path):
    """A very short file (0.1 s) below minimum loop duration."""
    path = str(tmp_path / "short.wav")
    y = _sine_wave(440.0, 0.1)
    sf.write(path, y, SR)
    return path


@pytest.fixture
def evaluator():
    return LoopEvaluator()


# ---------------------------------------------------------------------------
# Utility tests
# ---------------------------------------------------------------------------


class TestUtilities:
    def test_clamp_within_range(self):
        assert _clamp(0.5) == 0.5

    def test_clamp_below_zero(self):
        assert _clamp(-0.3) == 0.0

    def test_clamp_above_one(self):
        assert _clamp(1.5) == 1.0

    def test_cosine_similarity_identical(self):
        v = np.array([1.0, 2.0, 3.0])
        assert _cosine_similarity(v, v) == pytest.approx(1.0, abs=0.01)

    def test_cosine_similarity_orthogonal(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert _cosine_similarity(a, b) == pytest.approx(0.0, abs=0.01)

    def test_cosine_similarity_zero_vector(self):
        a = np.array([0.0, 0.0])
        b = np.array([1.0, 2.0])
        assert _cosine_similarity(a, b) == 0.0


# ---------------------------------------------------------------------------
# Candidate detection tests
# ---------------------------------------------------------------------------


class TestCandidateDetection:
    def test_produces_candidates_from_click_track(self, evaluator):
        y = _click_track(120.0, 8.0)
        candidates = evaluator.detect_candidates(y, SR, bpm=120.0)
        assert len(candidates) > 0

    def test_candidates_within_duration_bounds(self, evaluator):
        y = _click_track(120.0, 8.0)
        candidates = evaluator.detect_candidates(y, SR, bpm=120.0)
        for c in candidates:
            assert c.duration >= evaluator.min_loop_duration - 0.5
            assert c.duration <= evaluator.max_loop_duration + 0.5

    def test_fallback_grid_with_silence(self, evaluator):
        """Silence has no beats → should use fallback grid."""
        y = np.zeros(int(SR * 4.0), dtype=np.float32)
        candidates = evaluator.detect_candidates(y, SR, bpm=120.0)
        # Should still produce candidates from the grid
        assert len(candidates) > 0

    def test_respects_max_raw_candidates(self):
        evaluator = LoopEvaluator(max_raw_candidates=5)
        y = _click_track(120.0, 16.0)
        candidates = evaluator.detect_candidates(y, SR, bpm=120.0)
        assert len(candidates) <= 5

    def test_candidate_fields_populated(self, evaluator):
        y = _click_track(120.0, 8.0)
        candidates = evaluator.detect_candidates(y, SR, bpm=120.0)
        c = candidates[0]
        assert c.bpm == 120.0
        assert c.start_time >= 0.0
        assert c.end_time > c.start_time
        assert c.start_sample >= 0
        assert c.end_sample > c.start_sample
        assert c.duration > 0
        assert c.duration_bars > 0


# ---------------------------------------------------------------------------
# Individual heuristic tests
# ---------------------------------------------------------------------------


class TestHeuristics:
    def test_beat_alignment_on_beat_scores_higher(self, evaluator):
        """A candidate aligned to beats should score higher than one off-beat."""
        y = _click_track(120.0, 8.0)
        beat_times = evaluator._get_beat_times(y, SR)
        if len(beat_times) < 4:
            pytest.skip("Not enough beats detected")

        # On-beat candidate
        on_beat = LoopCandidate(
            start_sample=int(beat_times[0] * SR),
            end_sample=int(beat_times[3] * SR),
            start_time=beat_times[0],
            end_time=beat_times[3],
            duration=beat_times[3] - beat_times[0],
            duration_bars=1.0,
            bpm=120.0,
        )
        # Off-beat candidate (shifted by half a beat)
        shift = 0.25  # 250 ms
        off_beat = LoopCandidate(
            start_sample=int((beat_times[0] + shift) * SR),
            end_sample=int((beat_times[3] + shift) * SR),
            start_time=beat_times[0] + shift,
            end_time=beat_times[3] + shift,
            duration=beat_times[3] - beat_times[0],
            duration_bars=1.0,
            bpm=120.0,
        )

        score_on = evaluator._score_beat_alignment(on_beat, beat_times)
        score_off = evaluator._score_beat_alignment(off_beat, beat_times)
        assert score_on > score_off

    def test_spectral_similarity_identical_boundaries(self, evaluator):
        """A repeating pattern should have high spectral similarity at boundaries."""
        bar = _sine_wave(440.0, 2.0)
        loop_audio = np.tile(bar, 2)
        score = evaluator._score_spectral_similarity(loop_audio, SR)
        assert score > 0.7

    def test_spectral_similarity_different_boundaries(self, evaluator):
        """Different tones at start and end should score lower than identical."""
        # Use widely separated frequencies so MFCCs diverge
        start = _sine_wave(200.0, 1.0)
        end = _sine_wave(4000.0, 1.0)
        loop_audio = np.concatenate([start, end])
        score_diff = evaluator._score_spectral_similarity(loop_audio, SR)
        # Identical boundaries for comparison
        identical = np.tile(_sine_wave(440.0, 1.0), 2)
        score_same = evaluator._score_spectral_similarity(identical, SR)
        assert score_diff < score_same

    def test_duration_quantization_exact_bars(self, evaluator):
        """Exactly 4 bars at 120 BPM → high score."""
        bar_dur = 2.0  # 120 BPM, 4/4
        c = LoopCandidate(
            start_sample=0, end_sample=int(4 * bar_dur * SR),
            start_time=0.0, end_time=4 * bar_dur,
            duration=4 * bar_dur, duration_bars=4.0, bpm=120.0,
        )
        score = evaluator._score_duration_quantization(c)
        assert score > 0.9

    def test_duration_quantization_fractional_bars(self, evaluator):
        """3.5 bars → lower score than whole bars."""
        bar_dur = 2.0
        c = LoopCandidate(
            start_sample=0, end_sample=int(3.5 * bar_dur * SR),
            start_time=0.0, end_time=3.5 * bar_dur,
            duration=3.5 * bar_dur, duration_bars=3.5, bpm=120.0,
        )
        score = evaluator._score_duration_quantization(c)
        assert score < 0.9

    def test_zero_crossings_sine_wave(self, evaluator):
        """A sine wave has many zero crossings → should score 1.0."""
        y = _sine_wave(440.0, 2.0)
        score = evaluator._score_zero_crossings(y, 0, len(y), SR)
        assert score == pytest.approx(1.0)

    def test_rms_consistency_constant_tone(self, evaluator):
        """A constant-amplitude sine wave should have high RMS consistency."""
        loop = _sine_wave(440.0, 2.0)
        score = evaluator._score_rms_consistency(loop)
        assert score > 0.8

    def test_rms_consistency_with_spike(self, evaluator):
        """A loud spike should reduce RMS consistency."""
        loop = _sine_wave(440.0, 2.0)
        spike_start = len(loop) // 4
        loop[spike_start:spike_start + 500] = 5.0  # big spike
        score = evaluator._score_rms_consistency(loop)
        score_clean = evaluator._score_rms_consistency(_sine_wave(440.0, 2.0))
        assert score < score_clean

    def test_onset_regularity_click_track(self, evaluator):
        """Regular click track should score high for onset regularity."""
        loop = _click_track(120.0, 4.0)
        score = evaluator._score_onset_regularity(loop, SR)
        # Should be fairly high since onsets are regular
        assert score > 0.3

    def test_onset_regularity_silence(self, evaluator):
        """Silence (no onsets) → neutral score."""
        loop = np.zeros(int(SR * 2.0))
        score = evaluator._score_onset_regularity(loop, SR)
        assert score == pytest.approx(0.3)

    def test_spectral_stability_steady_tone(self, evaluator):
        """A steady sine tone should have high spectral stability."""
        loop = _sine_wave(440.0, 2.0)
        score = evaluator._score_spectral_stability(loop, SR)
        assert score > 0.5


# ---------------------------------------------------------------------------
# Overall scoring tests
# ---------------------------------------------------------------------------


class TestScoring:
    def test_overall_score_is_weighted_sum(self, evaluator):
        y = _click_track(120.0, 8.0)
        candidates = evaluator.detect_candidates(y, SR, bpm=120.0)
        if not candidates:
            pytest.skip("No candidates produced")

        beat_times = evaluator._get_beat_times(y, SR)
        scored = evaluator.score_candidate(candidates[0], y, SR, beat_times)

        # Manually compute expected
        expected = sum(
            evaluator.weights.get(name, 0.0) * getattr(scored.scores, name)
            for name in dataclasses.asdict(scored.scores)
        )
        assert scored.overall_score == pytest.approx(expected, abs=0.01)

    def test_score_candidates_returns_same_length(self, evaluator):
        y = _click_track(120.0, 8.0)
        candidates = evaluator.detect_candidates(y, SR, bpm=120.0)
        scored = evaluator.score_candidates(candidates, y, SR)
        assert len(scored) == len(candidates)


# ---------------------------------------------------------------------------
# Selection tests (pick best N)
# ---------------------------------------------------------------------------


class TestSelection:
    def _make_scored(self, start, end, score, bpm=120.0):
        c = LoopCandidate(
            start_sample=int(start * SR), end_sample=int(end * SR),
            start_time=start, end_time=end,
            duration=end - start, duration_bars=(end - start) / 2.0,
            bpm=bpm,
        )
        return ScoredLoopCandidate(
            candidate=c,
            scores=LoopHeuristicScores(),
            overall_score=score,
        )

    def test_select_best_returns_sorted(self, evaluator):
        scored = [
            self._make_scored(0, 2, 0.5),
            self._make_scored(4, 6, 0.9),
            self._make_scored(8, 10, 0.7),
        ]
        selected = evaluator.select_best(scored, n=3)
        assert [s.overall_score for s in selected] == [0.9, 0.7, 0.5]

    def test_select_best_respects_n(self, evaluator):
        scored = [self._make_scored(i * 4, i * 4 + 2, 0.8 - i * 0.1) for i in range(10)]
        selected = evaluator.select_best(scored, n=3)
        assert len(selected) <= 3

    def test_select_best_filters_min_score(self, evaluator):
        scored = [
            self._make_scored(0, 2, 0.1),
            self._make_scored(4, 6, 0.2),
            self._make_scored(8, 10, 0.8),
        ]
        selected = evaluator.select_best(scored, n=5, min_score=0.5)
        assert len(selected) == 1
        assert selected[0].overall_score == 0.8

    def test_select_best_suppresses_overlap(self, evaluator):
        """Two fully overlapping candidates → only the better one is selected."""
        scored = [
            self._make_scored(0, 4, 0.9),
            self._make_scored(0, 4, 0.7),  # exact overlap
        ]
        selected = evaluator.select_best(scored, n=5, overlap_threshold=0.5)
        assert len(selected) == 1
        assert selected[0].overall_score == 0.9

    def test_select_best_allows_non_overlapping(self, evaluator):
        """Non-overlapping candidates should both be selected."""
        scored = [
            self._make_scored(0, 2, 0.8),
            self._make_scored(4, 6, 0.7),
        ]
        selected = evaluator.select_best(scored, n=5, overlap_threshold=0.5)
        assert len(selected) == 2

    def test_ranks_are_assigned(self, evaluator):
        scored = [
            self._make_scored(0, 2, 0.6),
            self._make_scored(4, 6, 0.9),
        ]
        selected = evaluator.select_best(scored, n=5)
        assert selected[0].rank == 1
        assert selected[1].rank == 2


# ---------------------------------------------------------------------------
# Full evaluate() tests
# ---------------------------------------------------------------------------


class TestEvaluate:
    def test_evaluate_returns_result(self, evaluator, click_wav):
        result = evaluator.evaluate(click_wav)
        assert isinstance(result, LoopDetectionResult)
        assert result.sample_rate > 0
        assert result.duration > 0
        assert result.detected_bpm > 0

    def test_evaluate_with_repeating_pattern(self, evaluator, repeating_wav):
        result = evaluator.evaluate(repeating_wav, n=3)
        assert len(result.selected_candidates) > 0
        assert len(result.selected_candidates) <= 3
        # Best candidate should have a non-trivial score
        assert result.selected_candidates[0].overall_score > 0.0

    def test_evaluate_short_audio(self, evaluator, short_wav):
        """Very short audio may produce no valid candidates."""
        result = evaluator.evaluate(short_wav)
        # Either no candidates or they all have very low scores
        assert isinstance(result, LoopDetectionResult)

    def test_evaluate_nonexistent_file(self, evaluator):
        result = evaluator.evaluate("/nonexistent/file.wav")
        assert len(result.issues) > 0
        assert "Failed to load" in result.issues[0]

    def test_evaluate_n_greater_than_available(self, evaluator, sine_wav):
        """Requesting more candidates than available should not error."""
        result = evaluator.evaluate(sine_wav, n=100)
        assert len(result.selected_candidates) <= 100
        assert isinstance(result, LoopDetectionResult)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_zero_bpm(self, evaluator):
        """BPM of 0 should use fallback."""
        y = _sine_wave(440.0, 4.0)
        candidates = evaluator.detect_candidates(y, SR, bpm=0.0)
        # Uses fallback bar_duration of 2.0
        assert isinstance(candidates, list)

    def test_empty_audio(self, evaluator):
        y = np.array([], dtype=np.float32)
        candidates = evaluator.detect_candidates(y, SR, bpm=120.0)
        assert candidates == []

    def test_overlap_ratio_no_overlap(self, evaluator):
        a = ScoredLoopCandidate(
            candidate=LoopCandidate(0, SR, 0.0, 1.0, 1.0, 0.5, 120.0),
            scores=LoopHeuristicScores(),
        )
        b = ScoredLoopCandidate(
            candidate=LoopCandidate(3 * SR, 4 * SR, 3.0, 4.0, 1.0, 0.5, 120.0),
            scores=LoopHeuristicScores(),
        )
        assert LoopEvaluator._overlap_ratio(a, b) == 0.0

    def test_overlap_ratio_full_overlap(self, evaluator):
        a = ScoredLoopCandidate(
            candidate=LoopCandidate(0, 2 * SR, 0.0, 2.0, 2.0, 1.0, 120.0),
            scores=LoopHeuristicScores(),
        )
        b = ScoredLoopCandidate(
            candidate=LoopCandidate(0, 2 * SR, 0.0, 2.0, 2.0, 1.0, 120.0),
            scores=LoopHeuristicScores(),
        )
        assert LoopEvaluator._overlap_ratio(a, b) == pytest.approx(1.0)
