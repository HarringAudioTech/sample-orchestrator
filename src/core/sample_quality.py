"""
Sample quality analysis for audio processing pipelines.

Provides general-purpose quality metrics for any audio sample:
clipping detection, DC offset, silence detection, SNR estimation,
dynamic range, and a composite quality score.
"""

import dataclasses
import logging
from dataclasses import field
from typing import List, Optional, Dict, Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class SampleQualityReport:
    """Quality analysis results for a single audio sample."""

    # Clipping
    clipping_detected: bool = False
    clipped_sample_count: int = 0
    clipped_sample_ratio: float = 0.0

    # DC offset
    dc_offset: float = 0.0
    dc_offset_significant: bool = False

    # Silence / noise floor
    is_silent: bool = False
    rms_level_db: float = -120.0
    peak_level_db: float = -120.0
    noise_floor_db: float = -120.0

    # Dynamic range
    dynamic_range_db: float = 0.0

    # SNR
    estimated_snr_db: float = 0.0

    # Zero-crossing rate (can indicate corruption or unusual content)
    zero_crossing_rate: float = 0.0

    # Composite score (0.0 = worst, 1.0 = best)
    quality_score: float = 0.0

    # Issues found
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a JSON-serializable dictionary."""
        return {
            "clipping_detected": self.clipping_detected,
            "clipped_sample_count": self.clipped_sample_count,
            "clipped_sample_ratio": self.clipped_sample_ratio,
            "dc_offset": round(self.dc_offset, 6),
            "dc_offset_significant": self.dc_offset_significant,
            "is_silent": self.is_silent,
            "rms_level_db": round(self.rms_level_db, 2),
            "peak_level_db": round(self.peak_level_db, 2),
            "noise_floor_db": round(self.noise_floor_db, 2),
            "dynamic_range_db": round(self.dynamic_range_db, 2),
            "estimated_snr_db": round(self.estimated_snr_db, 2),
            "zero_crossing_rate": round(self.zero_crossing_rate, 4),
            "quality_score": round(self.quality_score, 3),
            "issues": self.issues,
        }


class SampleQualityAnalyzer:
    """Analyzes audio samples for quality issues.

    Configurable thresholds control what constitutes a quality issue.
    """

    def __init__(
        self,
        silence_threshold_db: float = -60.0,
        dc_offset_threshold: float = 0.01,
        clipping_threshold: float = 0.99,
        min_dynamic_range_db: float = 6.0,
        min_snr_db: float = 10.0,
    ):
        """
        Args:
            silence_threshold_db: RMS below this is considered silent.
            dc_offset_threshold: Absolute mean above this is significant DC offset.
            clipping_threshold: Absolute sample values above this are clipped.
            min_dynamic_range_db: Minimum acceptable dynamic range.
            min_snr_db: Minimum acceptable signal-to-noise ratio.
        """
        self.silence_threshold_db = silence_threshold_db
        self.dc_offset_threshold = dc_offset_threshold
        self.clipping_threshold = clipping_threshold
        self.min_dynamic_range_db = min_dynamic_range_db
        self.min_snr_db = min_snr_db

    def analyze(
        self,
        audio_data: np.ndarray,
        sample_rate: int,
    ) -> SampleQualityReport:
        """Analyze an audio buffer and return a quality report.

        Args:
            audio_data: Audio samples as a 1D numpy array (mono, float).
            sample_rate: Sample rate in Hz.

        Returns:
            SampleQualityReport with all metrics populated.
        """
        report = SampleQualityReport()

        if len(audio_data) == 0:
            report.is_silent = True
            report.issues.append("Audio buffer is empty")
            report.quality_score = 0.0
            return report

        abs_audio = np.abs(audio_data)

        # --- Peak level ---
        peak = float(np.max(abs_audio))
        if peak > 0:
            report.peak_level_db = float(20.0 * np.log10(peak))
        else:
            report.peak_level_db = -120.0

        # --- RMS level ---
        rms = float(np.sqrt(np.mean(audio_data ** 2)))
        if rms > 0:
            report.rms_level_db = float(20.0 * np.log10(rms))
        else:
            report.rms_level_db = -120.0

        # --- Silence detection ---
        if report.rms_level_db < self.silence_threshold_db:
            report.is_silent = True
            report.issues.append(
                f"Sample is silent or noise-only (RMS: {report.rms_level_db:.1f} dB)"
            )

        # --- Clipping detection ---
        clipped_mask = abs_audio >= self.clipping_threshold
        report.clipped_sample_count = int(np.sum(clipped_mask))
        report.clipped_sample_ratio = report.clipped_sample_count / len(audio_data)
        if report.clipped_sample_count > 0:
            report.clipping_detected = True
            report.issues.append(
                f"Clipping detected: {report.clipped_sample_count} samples "
                f"({report.clipped_sample_ratio * 100:.2f}%)"
            )

        # --- DC offset ---
        report.dc_offset = float(np.mean(audio_data))
        if abs(report.dc_offset) > self.dc_offset_threshold:
            report.dc_offset_significant = True
            report.issues.append(
                f"Significant DC offset: {report.dc_offset:.4f}"
            )

        # --- Noise floor estimation ---
        # Use the 5th percentile of absolute values as noise floor
        noise_floor = float(np.percentile(abs_audio, 5))
        if noise_floor > 0:
            report.noise_floor_db = float(20.0 * np.log10(noise_floor))
        else:
            report.noise_floor_db = -120.0

        # --- Dynamic range ---
        report.dynamic_range_db = report.peak_level_db - report.noise_floor_db
        if (
            report.dynamic_range_db < self.min_dynamic_range_db
            and not report.is_silent
        ):
            report.issues.append(
                f"Low dynamic range: {report.dynamic_range_db:.1f} dB "
                f"(minimum: {self.min_dynamic_range_db:.1f} dB)"
            )

        # --- SNR estimation ---
        # Estimate signal power from top 50% of frames, noise from bottom 10%
        if len(audio_data) >= 1024:
            frame_size = min(1024, len(audio_data) // 4)
            n_frames = len(audio_data) // frame_size
            if n_frames > 1:
                frames = audio_data[: n_frames * frame_size].reshape(n_frames, frame_size)
                frame_rms = np.sqrt(np.mean(frames ** 2, axis=1))
                sorted_rms = np.sort(frame_rms)

                noise_rms = float(np.mean(sorted_rms[: max(1, n_frames // 10)]))
                signal_rms = float(np.mean(sorted_rms[n_frames // 2 :]))

                if noise_rms > 0 and signal_rms > noise_rms:
                    report.estimated_snr_db = float(
                        20.0 * np.log10(signal_rms / noise_rms)
                    )
                elif noise_rms == 0 and signal_rms > 0:
                    report.estimated_snr_db = 96.0  # effectively clean
                else:
                    report.estimated_snr_db = 0.0

                if (
                    report.estimated_snr_db < self.min_snr_db
                    and not report.is_silent
                ):
                    report.issues.append(
                        f"Low SNR: {report.estimated_snr_db:.1f} dB "
                        f"(minimum: {self.min_snr_db:.1f} dB)"
                    )

        # --- Zero-crossing rate ---
        if len(audio_data) > 1:
            zero_crossings = np.sum(
                np.abs(np.diff(np.sign(audio_data))) > 0
            )
            report.zero_crossing_rate = float(zero_crossings / len(audio_data))

        # --- Composite quality score ---
        report.quality_score = self._compute_quality_score(report)

        return report

    def _compute_quality_score(self, report: SampleQualityReport) -> float:
        """Compute a composite quality score from 0.0 to 1.0.

        Scoring breakdown:
        - Not silent: 30 points
        - No clipping: 25 points
        - No DC offset: 10 points
        - Good dynamic range: 20 points
        - Good SNR: 15 points
        """
        score = 0.0
        max_score = 100.0

        # Silence (30 points)
        if not report.is_silent:
            score += 30.0

        # Clipping (25 points)
        if not report.clipping_detected:
            score += 25.0
        elif report.clipped_sample_ratio < 0.001:
            score += 15.0  # Minor clipping
        elif report.clipped_sample_ratio < 0.01:
            score += 5.0  # Moderate clipping

        # DC offset (10 points)
        if not report.dc_offset_significant:
            score += 10.0
        elif abs(report.dc_offset) < self.dc_offset_threshold * 5:
            score += 5.0

        # Dynamic range (20 points)
        if report.dynamic_range_db >= self.min_dynamic_range_db:
            score += 20.0
        elif report.dynamic_range_db >= self.min_dynamic_range_db * 0.5:
            score += 10.0

        # SNR (15 points)
        if report.estimated_snr_db >= self.min_snr_db:
            score += 15.0
        elif report.estimated_snr_db >= self.min_snr_db * 0.5:
            score += 7.0

        return round(score / max_score, 3)

    def analyze_file(
        self,
        file_path: str,
        target_sr: int = 44100,
    ) -> SampleQualityReport:
        """Analyze an audio file and return a quality report.

        Args:
            file_path: Path to the audio file.
            target_sr: Target sample rate for loading.

        Returns:
            SampleQualityReport with all metrics populated.
        """
        import librosa

        try:
            y, sr = librosa.load(file_path, sr=target_sr, mono=True)
            return self.analyze(y, sr)
        except Exception as e:
            report = SampleQualityReport()
            report.quality_score = 0.0
            report.issues.append(f"Failed to load audio file: {str(e)}")
            return report
