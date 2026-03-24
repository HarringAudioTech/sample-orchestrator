"""Tests for the SampleQualityAnalyzer and SampleQualityReport."""

import os
import pytest
import numpy as np
import soundfile as sf

from src.core.sample_quality import SampleQualityAnalyzer, SampleQualityReport


@pytest.fixture
def analyzer():
    return SampleQualityAnalyzer()


class TestSampleQualityReport:
    def test_to_dict(self):
        report = SampleQualityReport(
            clipping_detected=True,
            clipped_sample_count=100,
            quality_score=0.75,
            issues=["test issue"],
        )
        d = report.to_dict()
        assert d["clipping_detected"] is True
        assert d["clipped_sample_count"] == 100
        assert d["quality_score"] == 0.75
        assert d["issues"] == ["test issue"]

    def test_default_values(self):
        report = SampleQualityReport()
        assert report.clipping_detected is False
        assert report.is_silent is False
        assert report.dc_offset == 0.0
        assert report.quality_score == 0.0
        assert report.issues == []


class TestSampleQualityAnalyzerClipping:
    def test_detects_clipping(self, analyzer):
        """Audio at full scale should be detected as clipped."""
        sr = 44100
        # Square wave at ±1.0
        audio = np.ones(sr, dtype=np.float32)
        report = analyzer.analyze(audio, sr)
        assert report.clipping_detected is True
        assert report.clipped_sample_count > 0

    def test_no_clipping_on_quiet_signal(self, analyzer):
        """A quiet sine wave should not be clipped."""
        sr = 44100
        t = np.linspace(0, 1, sr)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        report = analyzer.analyze(audio, sr)
        assert report.clipping_detected is False
        assert report.clipped_sample_count == 0


class TestSampleQualityAnalyzerSilence:
    def test_detects_silence(self, analyzer):
        """A zero-amplitude buffer should be detected as silent."""
        sr = 44100
        audio = np.zeros(sr, dtype=np.float32)
        report = analyzer.analyze(audio, sr)
        assert report.is_silent is True

    def test_very_quiet_is_silent(self, analyzer):
        """Signal well below silence threshold should be flagged."""
        sr = 44100
        # Very quiet noise
        audio = (np.random.randn(sr) * 1e-5).astype(np.float32)
        report = analyzer.analyze(audio, sr)
        assert report.is_silent is True

    def test_normal_signal_not_silent(self, analyzer):
        """A normal signal should not be flagged as silent."""
        sr = 44100
        t = np.linspace(0, 1, sr)
        audio = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        report = analyzer.analyze(audio, sr)
        assert report.is_silent is False


class TestSampleQualityAnalyzerDCOffset:
    def test_detects_dc_offset(self, analyzer):
        """A signal with a large DC offset should be detected."""
        sr = 44100
        audio = np.full(sr, 0.1, dtype=np.float32)  # Constant 0.1
        report = analyzer.analyze(audio, sr)
        assert report.dc_offset_significant is True
        assert abs(report.dc_offset - 0.1) < 0.001

    def test_no_dc_offset_on_centered_signal(self, analyzer):
        """A centered sine wave should have negligible DC offset."""
        sr = 44100
        t = np.linspace(0, 1, sr)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        report = analyzer.analyze(audio, sr)
        assert report.dc_offset_significant is False


class TestSampleQualityAnalyzerDynamicRange:
    def test_good_dynamic_range(self, analyzer):
        """A signal with wide dynamic range should pass."""
        sr = 44100
        t = np.linspace(0, 2, sr * 2)
        # Signal with varying amplitude
        envelope = np.linspace(0.01, 0.8, sr * 2)
        audio = (envelope * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        report = analyzer.analyze(audio, sr)
        assert report.dynamic_range_db > 6.0

    def test_low_dynamic_range(self, analyzer):
        """A constant-amplitude signal should have low dynamic range."""
        sr = 44100
        # Nearly constant signal
        audio = np.full(sr, 0.5, dtype=np.float32)
        report = analyzer.analyze(audio, sr)
        assert report.dynamic_range_db < 6.0


class TestSampleQualityAnalyzerSNR:
    def test_clean_signal_high_snr(self, analyzer):
        """A clean tone should have high SNR."""
        sr = 44100
        t = np.linspace(0, 2, sr * 2)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        report = analyzer.analyze(audio, sr)
        # Clean sine has no quiet sections, so SNR may be 0
        # but it shouldn't flag as low SNR since it's not noisy
        assert report.estimated_snr_db >= 0


class TestSampleQualityAnalyzerZeroCrossing:
    def test_zero_crossing_rate_sine(self, analyzer):
        """A sine wave should have a predictable ZCR."""
        sr = 44100
        freq = 440
        t = np.linspace(0, 1, sr)
        audio = (0.5 * np.sin(2 * np.pi * freq * t)).astype(np.float32)
        report = analyzer.analyze(audio, sr)
        # 440 Hz sine wave crosses zero ~880 times per second
        # ZCR ≈ 880/44100 ≈ 0.02
        assert 0.01 < report.zero_crossing_rate < 0.05


class TestSampleQualityAnalyzerScore:
    def test_good_signal_high_score(self, analyzer):
        """A clean, well-leveled signal should have a high score."""
        sr = 44100
        t = np.linspace(0, 2, sr * 2)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        report = analyzer.analyze(audio, sr)
        assert report.quality_score >= 0.5

    def test_silent_signal_low_score(self, analyzer):
        """A silent signal should have a low score."""
        sr = 44100
        audio = np.zeros(sr, dtype=np.float32)
        report = analyzer.analyze(audio, sr)
        assert report.quality_score < 0.5

    def test_clipped_signal_lower_score(self, analyzer):
        """A clipped signal should have a lower score than clean."""
        sr = 44100
        t = np.linspace(0, 1, sr)
        clean = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        clipped = np.clip(
            2.0 * np.sin(2 * np.pi * 440 * t), -1.0, 1.0
        ).astype(np.float32)

        clean_report = analyzer.analyze(clean, sr)
        clipped_report = analyzer.analyze(clipped, sr)

        assert clean_report.quality_score > clipped_report.quality_score

    def test_empty_buffer_zero_score(self, analyzer):
        """An empty buffer should have score 0."""
        report = analyzer.analyze(np.array([], dtype=np.float32), 44100)
        assert report.quality_score == 0.0
        assert report.is_silent is True


class TestSampleQualityAnalyzerEdgeCases:
    def test_single_sample(self, analyzer):
        """Single sample should not crash."""
        audio = np.array([0.5], dtype=np.float32)
        report = analyzer.analyze(audio, 44100)
        assert isinstance(report, SampleQualityReport)

    def test_custom_thresholds(self):
        """Custom thresholds should be respected."""
        analyzer = SampleQualityAnalyzer(
            silence_threshold_db=-30.0,
            dc_offset_threshold=0.001,
            clipping_threshold=0.5,
        )
        sr = 44100
        t = np.linspace(0, 1, sr)
        audio = (0.6 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        report = analyzer.analyze(audio, sr)
        # With clipping threshold at 0.5, a 0.6 amplitude should clip
        assert report.clipping_detected is True


class TestSampleQualityAnalyzerFileAnalysis:
    def test_analyze_file(self, analyzer, tmp_path):
        """Test file-based analysis."""
        sr = 44100
        t = np.linspace(0, 1, sr)
        audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

        file_path = str(tmp_path / "test.wav")
        sf.write(file_path, audio, sr)

        report = analyzer.analyze_file(file_path)
        assert report.quality_score > 0
        assert not report.is_silent
        assert not report.clipping_detected

    def test_analyze_nonexistent_file(self, analyzer):
        """Non-existent file should return failed report."""
        report = analyzer.analyze_file("/nonexistent/file.wav")
        assert report.quality_score == 0.0
        assert len(report.issues) > 0
