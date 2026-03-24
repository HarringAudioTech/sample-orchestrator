"""
Loop detection and scoring module.

Detects multiple candidate loops from a larger audio segment, scores each
using a set of heuristics, and selects the best N candidates. Follows the
same evaluator pattern as vocal_chop_evaluator.py.
"""

import dataclasses
from dataclasses import field
from typing import Dict, List, Optional, Tuple

import librosa
import numpy as np
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: Dict[str, float] = {
    "beat_alignment": 0.20,
    "spectral_similarity": 0.25,
    "duration_quantization": 0.20,
    "zero_crossing_cleanliness": 0.05,
    "rms_energy_consistency": 0.10,
    "onset_regularity": 0.10,
    "spectral_stability": 0.10,
}


@dataclasses.dataclass
class LoopCandidate:
    """A single candidate loop region detected from audio."""

    start_sample: int
    end_sample: int
    start_time: float  # seconds
    end_time: float  # seconds
    duration: float  # seconds
    duration_bars: float  # estimated musical bars at detected BPM
    bpm: float  # BPM used for bar calculation


@dataclasses.dataclass
class LoopHeuristicScores:
    """Individual heuristic scores for a loop candidate. All 0.0–1.0."""

    beat_alignment: float = 0.0
    spectral_similarity: float = 0.0
    duration_quantization: float = 0.0
    zero_crossing_cleanliness: float = 0.0
    rms_energy_consistency: float = 0.0
    onset_regularity: float = 0.0
    spectral_stability: float = 0.0


@dataclasses.dataclass
class ScoredLoopCandidate:
    """A loop candidate with its heuristic scores and overall score."""

    candidate: LoopCandidate
    scores: LoopHeuristicScores
    overall_score: float = 0.0  # weighted combination, 0.0–1.0
    issues: List[str] = field(default_factory=list)
    rank: int = 0  # 1-based rank after selection


@dataclasses.dataclass
class LoopDetectionResult:
    """Overall result of loop detection and scoring for an audio segment."""

    audio_path: str
    sample_rate: int
    duration: float  # seconds
    detected_bpm: float
    all_candidates: List[ScoredLoopCandidate] = field(default_factory=list)
    selected_candidates: List[ScoredLoopCandidate] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------

def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two 1-D vectors, clipped to [0, 1]."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return _clamp(float(np.dot(a, b) / (norm_a * norm_b)))


# ---------------------------------------------------------------------------
# LoopEvaluator
# ---------------------------------------------------------------------------

class LoopEvaluator:
    """Detects, scores and selects the best loop candidates from audio."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        min_loop_duration: float = 0.5,
        max_loop_duration: float = 32.0,
        max_raw_candidates: int = 200,
    ):
        self.weights = dict(DEFAULT_WEIGHTS)
        if weights:
            self.weights.update(weights)
        self.min_loop_duration = min_loop_duration
        self.max_loop_duration = max_loop_duration
        self.max_raw_candidates = max_raw_candidates

    # ------------------------------------------------------------------
    # Candidate detection
    # ------------------------------------------------------------------

    def detect_candidates(
        self,
        y: np.ndarray,
        sr: int,
        bpm: float,
    ) -> List[LoopCandidate]:
        """Generate candidate loops using a beat-grid search.

        For each pair of beats that are N bars apart (N in {1, 2, 4, 8, 16}),
        create a candidate if within duration bounds.  Falls back to a fixed-
        interval grid when fewer than 4 beats are detected.
        """
        bar_duration = (60.0 / bpm) * 4 if bpm > 0 else 2.0  # 4/4 time
        audio_duration = len(y) / sr

        # Get beat positions
        beat_times = self._get_beat_times(y, sr)

        candidates: List[LoopCandidate] = []

        bar_counts = [1, 2, 4, 8, 16]

        if len(beat_times) >= 4:
            # Beat-grid search: pair beats that are N bars apart
            for n_bars in bar_counts:
                target_dur = n_bars * bar_duration
                if target_dur < self.min_loop_duration or target_dur > self.max_loop_duration:
                    continue
                # Tolerance: 15% of bar duration
                tol = 0.15 * bar_duration
                for i, start_t in enumerate(beat_times):
                    for j in range(i + 1, len(beat_times)):
                        dur = beat_times[j] - start_t
                        if dur < target_dur - tol:
                            continue
                        if dur > target_dur + tol:
                            break  # beat_times is sorted
                        candidates.append(self._make_candidate(
                            start_t, beat_times[j], sr, bpm, bar_duration,
                        ))
                        if len(candidates) >= self.max_raw_candidates:
                            return candidates
        else:
            # Fallback: fixed-interval grid from BPM
            logger.info("Fewer than 4 beats detected; using fixed-interval grid")
            for n_bars in bar_counts:
                target_dur = n_bars * bar_duration
                if target_dur < self.min_loop_duration or target_dur > self.max_loop_duration:
                    continue
                step = bar_duration  # step by 1 bar
                start_t = 0.0
                while start_t + target_dur <= audio_duration:
                    end_t = start_t + target_dur
                    candidates.append(self._make_candidate(
                        start_t, end_t, sr, bpm, bar_duration,
                    ))
                    start_t += step
                    if len(candidates) >= self.max_raw_candidates:
                        return candidates

        return candidates

    # ------------------------------------------------------------------
    # Scoring
    # ------------------------------------------------------------------

    def score_candidate(
        self,
        candidate: LoopCandidate,
        y: np.ndarray,
        sr: int,
        beat_times: np.ndarray,
    ) -> ScoredLoopCandidate:
        """Score a single candidate using all heuristics."""
        s = LoopHeuristicScores()
        issues: List[str] = []
        loop_audio = y[candidate.start_sample:candidate.end_sample]

        if len(loop_audio) == 0:
            issues.append("Empty loop audio")
            return ScoredLoopCandidate(candidate=candidate, scores=s, issues=issues)

        s.beat_alignment = self._score_beat_alignment(candidate, beat_times)
        s.spectral_similarity = self._score_spectral_similarity(loop_audio, sr)
        s.duration_quantization = self._score_duration_quantization(candidate)
        s.zero_crossing_cleanliness = self._score_zero_crossings(
            y, candidate.start_sample, candidate.end_sample, sr,
        )
        s.rms_energy_consistency = self._score_rms_consistency(loop_audio)
        s.onset_regularity = self._score_onset_regularity(loop_audio, sr)
        s.spectral_stability = self._score_spectral_stability(loop_audio, sr)

        overall = sum(
            self.weights.get(name, 0.0) * getattr(s, name)
            for name in dataclasses.asdict(s)
        )
        overall = _clamp(overall)

        return ScoredLoopCandidate(
            candidate=candidate,
            scores=s,
            overall_score=overall,
            issues=issues,
        )

    def score_candidates(
        self,
        candidates: List[LoopCandidate],
        y: np.ndarray,
        sr: int,
    ) -> List[ScoredLoopCandidate]:
        """Score a list of candidates."""
        beat_times = self._get_beat_times(y, sr)
        return [self.score_candidate(c, y, sr, beat_times) for c in candidates]

    # ------------------------------------------------------------------
    # Selection (pick best N)
    # ------------------------------------------------------------------

    def select_best(
        self,
        scored: List[ScoredLoopCandidate],
        n: int = 5,
        min_score: float = 0.3,
        overlap_threshold: float = 0.5,
    ) -> List[ScoredLoopCandidate]:
        """Select top-N non-overlapping candidates via greedy NMS."""
        filtered = [s for s in scored if s.overall_score >= min_score]
        filtered.sort(key=lambda s: s.overall_score, reverse=True)

        selected: List[ScoredLoopCandidate] = []
        for sc in filtered:
            if len(selected) >= n:
                break
            if any(self._overlap_ratio(sc, existing) > overlap_threshold for existing in selected):
                continue
            selected.append(sc)

        # Assign ranks
        for i, sc in enumerate(selected):
            sc.rank = i + 1

        return selected

    # ------------------------------------------------------------------
    # Full evaluation entry point
    # ------------------------------------------------------------------

    def evaluate(
        self,
        audio_path: str,
        sr: Optional[int] = None,
        n: int = 5,
        min_score: float = 0.3,
        overlap_threshold: float = 0.5,
    ) -> LoopDetectionResult:
        """Full pipeline: load → detect → score → select."""
        issues: List[str] = []

        try:
            y, sr_loaded = librosa.load(audio_path, sr=sr, mono=True)
        except Exception as e:
            return LoopDetectionResult(
                audio_path=audio_path,
                sample_rate=sr or 0,
                duration=0.0,
                detected_bpm=0.0,
                issues=[f"Failed to load audio: {e}"],
            )

        sr = sr_loaded
        audio_duration = len(y) / sr

        # Detect BPM
        bpm = self._detect_bpm(y, sr)
        if bpm <= 0:
            issues.append("BPM detection failed; using 120 BPM fallback")
            bpm = 120.0

        # Detect candidates
        candidates = self.detect_candidates(y, sr, bpm)
        if not candidates:
            issues.append("No loop candidates detected")
            return LoopDetectionResult(
                audio_path=audio_path,
                sample_rate=sr,
                duration=audio_duration,
                detected_bpm=bpm,
                issues=issues,
            )

        # Score candidates
        scored = self.score_candidates(candidates, y, sr)

        # Select best N
        selected = self.select_best(scored, n=n, min_score=min_score,
                                    overlap_threshold=overlap_threshold)

        return LoopDetectionResult(
            audio_path=audio_path,
            sample_rate=sr,
            duration=audio_duration,
            detected_bpm=bpm,
            all_candidates=scored,
            selected_candidates=selected,
            issues=issues,
        )

    # ------------------------------------------------------------------
    # Individual heuristics
    # ------------------------------------------------------------------

    def _score_beat_alignment(
        self,
        candidate: LoopCandidate,
        beat_times: np.ndarray,
    ) -> float:
        """Score how well loop boundaries align with detected beats."""
        if len(beat_times) == 0:
            return 0.3  # neutral when no beats

        beat_period = np.median(np.diff(beat_times)) if len(beat_times) > 1 else 0.5

        start_dist = float(np.min(np.abs(beat_times - candidate.start_time)))
        end_dist = float(np.min(np.abs(beat_times - candidate.end_time)))

        start_score = _clamp(1.0 - start_dist / beat_period)
        end_score = _clamp(1.0 - end_dist / beat_period)
        return (start_score + end_score) / 2.0

    def _score_spectral_similarity(
        self,
        loop_audio: np.ndarray,
        sr: int,
        window_ms: float = 50.0,
    ) -> float:
        """Cosine similarity of MFCC features at loop start vs end."""
        window_samples = max(int((window_ms / 1000.0) * sr), 512)
        if len(loop_audio) < window_samples * 2:
            return 0.0

        start_window = loop_audio[:window_samples]
        end_window = loop_audio[-window_samples:]

        try:
            mfcc_start = np.mean(librosa.feature.mfcc(
                y=start_window, sr=sr, n_mfcc=13,
            ), axis=1)
            mfcc_end = np.mean(librosa.feature.mfcc(
                y=end_window, sr=sr, n_mfcc=13,
            ), axis=1)
        except Exception:
            return 0.0

        return _cosine_similarity(mfcc_start, mfcc_end)

    def _score_duration_quantization(self, candidate: LoopCandidate) -> float:
        """Score how close the duration is to a whole number of bars."""
        if candidate.bpm <= 0:
            return 0.3

        bar_duration = (60.0 / candidate.bpm) * 4
        if bar_duration <= 0:
            return 0.3

        # Find nearest power-of-2 bar count
        bars_float = candidate.duration / bar_duration
        best_dist = float("inf")
        for n_bars in [1, 2, 4, 8, 16]:
            dist = abs(bars_float - n_bars)
            if dist < best_dist:
                best_dist = dist

        return _clamp(1.0 - best_dist / max(bars_float, 1.0))

    def _score_zero_crossings(
        self,
        y: np.ndarray,
        start_sample: int,
        end_sample: int,
        sr: int,
        window_ms: float = 5.0,
    ) -> float:
        """Score whether zero crossings exist near the loop boundaries."""
        window = max(int((window_ms / 1000.0) * sr), 1)
        score = 0.0

        # Check start
        s_lo = max(0, start_sample - window // 2)
        s_hi = min(len(y), start_sample + window // 2)
        if s_hi > s_lo and np.any(librosa.zero_crossings(y[s_lo:s_hi], pad=False)):
            score += 0.5

        # Check end
        e_lo = max(0, end_sample - window // 2)
        e_hi = min(len(y), end_sample + window // 2)
        if e_hi > e_lo and np.any(librosa.zero_crossings(y[e_lo:e_hi], pad=False)):
            score += 0.5

        return score

    def _score_rms_consistency(
        self,
        loop_audio: np.ndarray,
        n_frames: int = 16,
    ) -> float:
        """Score energy consistency across the loop."""
        if len(loop_audio) < n_frames:
            return 0.3

        frame_len = len(loop_audio) // n_frames
        rms_values = []
        for i in range(n_frames):
            frame = loop_audio[i * frame_len:(i + 1) * frame_len]
            rms_values.append(float(np.sqrt(np.mean(frame ** 2))))

        rms_arr = np.array(rms_values)
        mean_rms = np.mean(rms_arr)
        if mean_rms < 1e-10:
            return 0.3  # silence

        cv = float(np.std(rms_arr) / mean_rms)
        return _clamp(1.0 - cv)

    def _score_onset_regularity(
        self,
        loop_audio: np.ndarray,
        sr: int,
    ) -> float:
        """Score regularity of detected onsets within the loop."""
        try:
            onsets = librosa.onset.onset_detect(
                y=loop_audio, sr=sr, units="time", backtrack=False,
            )
        except Exception:
            return 0.3

        if len(onsets) < 2:
            return 0.3  # neutral – can't measure regularity

        iois = np.diff(onsets)
        mean_ioi = np.mean(iois)
        if mean_ioi < 1e-10:
            return 0.3

        cv = float(np.std(iois) / mean_ioi)
        return _clamp(1.0 - cv)

    def _score_spectral_stability(
        self,
        loop_audio: np.ndarray,
        sr: int,
    ) -> float:
        """Score spectral stability (low flux = stable content)."""
        try:
            S = librosa.feature.melspectrogram(y=loop_audio, sr=sr, n_mels=64)
        except Exception:
            return 0.3

        if S.shape[1] < 2:
            return 0.3

        # Frame-to-frame flux
        flux = np.mean(np.abs(np.diff(S, axis=1)))
        mean_energy = np.mean(S) + 1e-10
        normalised_flux = flux / mean_energy

        return _clamp(1.0 - normalised_flux)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _get_beat_times(self, y: np.ndarray, sr: int) -> np.ndarray:
        """Return beat positions in seconds."""
        try:
            _, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            return librosa.frames_to_time(beat_frames, sr=sr)
        except Exception:
            return np.array([])

    @staticmethod
    def _detect_bpm(y: np.ndarray, sr: int) -> float:
        """Detect BPM with heuristic tempo correction."""
        try:
            tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
            tempo = float(np.atleast_1d(tempo)[0]) if hasattr(tempo, '__iter__') else float(tempo)
            if tempo < 40:
                tempo *= 2
            elif tempo > 200:
                tempo /= 2
            return tempo
        except Exception:
            return 0.0

    @staticmethod
    def _make_candidate(
        start_time: float,
        end_time: float,
        sr: int,
        bpm: float,
        bar_duration: float,
    ) -> LoopCandidate:
        duration = end_time - start_time
        return LoopCandidate(
            start_sample=int(start_time * sr),
            end_sample=int(end_time * sr),
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            duration_bars=duration / bar_duration if bar_duration > 0 else 0.0,
            bpm=bpm,
        )

    @staticmethod
    def _overlap_ratio(
        a: ScoredLoopCandidate,
        b: ScoredLoopCandidate,
    ) -> float:
        """Overlap as fraction of the shorter candidate's duration."""
        ca, cb = a.candidate, b.candidate
        overlap_start = max(ca.start_time, cb.start_time)
        overlap_end = min(ca.end_time, cb.end_time)
        overlap = max(0.0, overlap_end - overlap_start)
        shorter = min(ca.duration, cb.duration)
        if shorter <= 0:
            return 0.0
        return overlap / shorter
