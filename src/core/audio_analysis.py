"""
Audio analysis utilities for sample processing.

This module provides functions for analyzing audio files to extract useful metadata
for sample pack creation, including BPM, key, loudness, and loop points.
"""

import numpy as np
import librosa
import librosa.display
import soundfile as sf
from typing import Dict, List, Tuple, Optional, Union
import logging

logger = logging.getLogger(__name__)

def detect_bpm(audio_path: str, sr: Optional[int] = None) -> float:
    """
    Detect the BPM of an audio file.
    
    Args:
        audio_path: Path to the audio file
        sr: Sample rate (None to use file's native sample rate)
        
    Returns:
        float: Detected BPM
    """
    try:
        y, sr = librosa.load(audio_path, sr=sr, mono=True)
        
        # First, get an estimate of the tempo
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        
        # If the estimate seems too fast or slow, try a different approach
        if tempo < 40:
            # Possibly half-time detection, try doubling
            tempo *= 2
        elif tempo > 200:
            # Possibly double-time detection, try halving
            tempo /= 2
            
        return float(tempo)
    except Exception as e:
        logger.warning(f"BPM detection failed: {str(e)}")
        return 0.0

def detect_key(audio_path: str, sr: Optional[int] = None) -> str:
    """
    Detect the musical key of an audio file.
    
    Args:
        audio_path: Path to the audio file
        sr: Sample rate (None to use file's native sample rate)
        
    Returns:
        str: Detected key (e.g., "C", "D#m", etc.)
    """
    try:
        y, sr = librosa.load(audio_path, sr=sr, mono=True)
        
        # Compute the constant-Q transform
        cqt = np.abs(librosa.cqt(y, sr=sr))
        
        # Get the chromagram
        chroma = librosa.feature.chroma_cqt(C=cqt, sr=sr)
        
        # Get the average over time
        chroma_avg = np.mean(chroma, axis=1)
        
        # Get the pitch class with maximum energy
        pitch_class = np.argmax(chroma_avg)
        
        # Determine if it's major or minor
        # This is a simple heuristic - in a real app you'd want something more sophisticated
        major_third = (pitch_class + 4) % 12
        minor_third = (pitch_class + 3) % 12
        
        # Check which third is more prominent
        if chroma_avg[major_third % 12] > chroma_avg[minor_third % 12]:
            mode = "major"
        else:
            mode = "minor"
        
        # Map pitch class to note name
        notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        note = notes[pitch_class]
        
        return f"{note}{'' if mode == 'major' else 'm'}"
    except Exception as e:
        logger.warning(f"Key detection failed: {str(e)}")
        return ""

def detect_loop_points(
    audio_path: str,
    sr: Optional[int] = None,
    n: int = 5,
    min_score: float = 0.3,
) -> List[Dict[str, Union[int, float]]]:
    """
    Detect potential loop regions in an audio file.

    Uses :class:`~src.core.loop_evaluator.LoopEvaluator` to find multiple
    candidate loops, score them with heuristics, and return the best *n*.

    Args:
        audio_path: Path to the audio file.
        sr: Sample rate (None to use the file's native rate).
        n: Maximum number of loop candidates to return.
        min_score: Minimum overall score for a candidate to be included.

    Returns:
        List of dicts, each containing::

            {'loop_start': int,   # sample index
             'loop_end': int,     # sample index
             'confidence': float, # 0.0 – 1.0
             'start_time': float, # seconds
             'end_time': float,   # seconds
             'duration_bars': float,
             'bpm': float}

        Ordered by descending confidence.  Returns an empty list on failure.
    """
    try:
        from src.core.loop_evaluator import LoopEvaluator

        evaluator = LoopEvaluator()
        result = evaluator.evaluate(audio_path, sr=sr, n=n, min_score=min_score)

        loops: List[Dict[str, Union[int, float]]] = []
        for sc in result.selected_candidates:
            loops.append({
                'loop_start': sc.candidate.start_sample,
                'loop_end': sc.candidate.end_sample,
                'confidence': sc.overall_score,
                'start_time': sc.candidate.start_time,
                'end_time': sc.candidate.end_time,
                'duration_bars': sc.candidate.duration_bars,
                'bpm': sc.candidate.bpm,
            })
        return loops
    except Exception as e:
        logger.warning(f"Loop detection failed: {str(e)}")
        return []


def detect_best_loop_point(
    audio_path: str, sr: Optional[int] = None
) -> Dict[str, Union[int, float]]:
    """
    Convenience wrapper returning only the single best loop point.

    Backward-compatible with the old ``detect_loop_points()`` return format.

    Returns:
        Dict with ``loop_start``, ``loop_end``, ``confidence`` or empty dict.
    """
    loops = detect_loop_points(audio_path, sr=sr, n=1)
    if loops:
        return loops[0]
    return {}

def analyze_audio_metadata(audio_path: str, sr: Optional[int] = None) -> Dict[str, any]:
    """
    Extract comprehensive metadata from an audio file.
    
    Args:
        audio_path: Path to the audio file
        sr: Sample rate (None to use file's native sample rate)
        
    Returns:
        Dict containing audio metadata:
        {
            'duration': float,  # in seconds
            'sample_rate': int,
            'channels': int,
            'bit_depth': int,
            'bpm': float,
            'key': str,
            'loudness': float,  # in LUFS
            'dynamic_range': float,  # in dB
            'is_loop': bool,
            'loop_points': Optional[Dict],  # see detect_loop_points()
            'transient_positions': List[float]  # in seconds
        }
    """
    try:
        # Get basic file info
        info = sf.info(audio_path)
        
        # Load audio for analysis
        y, sr = librosa.load(audio_path, sr=sr, mono=True)
        
        # Detect BPM and key
        bpm = detect_bpm(audio_path, sr)
        key = detect_key(audio_path, sr)
        
        # Detect loop points (returns list of candidates now)
        loop_candidates = detect_loop_points(audio_path, sr)
        best_loop = loop_candidates[0] if loop_candidates else None

        # Calculate loudness (simplified RMS)
        rms = np.sqrt(np.mean(y**2))
        loudness = 20 * np.log10(rms) if rms > 0 else -120

        # Calculate dynamic range (simplified)
        peak = np.max(np.abs(y))
        noise_floor = np.percentile(np.abs(y), 5)  # 5th percentile as noise floor
        dynamic_range = 20 * np.log10(peak / noise_floor) if noise_floor > 0 else 0

        # Detect transients (onsets)
        onset_frames = librosa.onset.onset_detect(y=y, sr=sr, units='time')

        return {
            'duration': float(info.duration),
            'sample_rate': int(info.samplerate),
            'channels': info.channels,
            'bit_depth': _parse_bit_depth(info.subtype),
            'bpm': bpm,
            'key': key,
            'loudness': float(loudness),
            'dynamic_range': float(dynamic_range),
            'is_loop': best_loop is not None and best_loop.get('confidence', 0) > 0.7,
            'loop_points': best_loop,
            'loop_candidates': loop_candidates,
            'transient_positions': list(onset_frames)
        }
    except Exception as e:
        logger.error(f"Audio analysis failed: {str(e)}", exc_info=True)
        raise

def _parse_bit_depth(subtype_str):
    """Extract bit depth from soundfile info.subtype string."""
    import re
    if not subtype_str:
        return None
    # Look for a number in the subtype string
    match = re.search(r'(\d+)', subtype_str)
    if match:
        return int(match.group(1))
    # Fallback for float types
    if 'FLOAT' in subtype_str.upper():
        return 32
    return None

def normalize_audio(y: np.ndarray, target_lufs: float = -14.0) -> np.ndarray:
    """
    Normalize audio to a target LUFS level.
    
    Args:
        y: Audio data
        target_lufs: Target LUFS level
        
    Returns:
        Normalized audio data
    """
    # Simple normalization - in a real app you'd want to use a proper LUFS meter
    peak = np.max(np.abs(y))
    if peak > 0:
        return y * (10 ** (target_lufs / 20.0)) / peak
    return y
