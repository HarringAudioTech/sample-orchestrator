"""
Utility for dynamic spectral EQ to prevent masking between audio stems in a construction kit section.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

import numpy as np
import librosa
import soundfile as sf
from pedalboard import Pedalboard, HighpassFilter, LowpassFilter, PeakFilter
from pedalboard.io import AudioFile

logger = logging.getLogger(__name__)

class SpectralEQ:
    """
    Analyzes multiple audio stems and applies EQ to reduce frequency masking.
    """

    def __init__(self, sample_rate: int = 44100):
        self.sample_rate = sample_rate
        self.n_fft = 2048
        self.hop_length = 512

    def process_section(self, section_dir: Path):
        """
        Processes all WAV files in a section directory to reduce masking.
        """
        wav_files = list(section_dir.glob("*.wav"))
        if len(wav_files) <= 1:
            logger.info(f"Skipping spectral EQ for {section_dir}: only {len(wav_files)} stem(s) found.")
            return

        logger.info(f"Applying spectral EQ to {len(wav_files)} stems in {section_dir}")
        
        # 1. Load and analyze all stems
        stems_data = {}
        for wav_path in wav_files:
            try:
                y, sr = librosa.load(str(wav_path), sr=self.sample_rate)
                # Compute average power spectrum
                stft = np.abs(librosa.stft(y, n_fft=self.n_fft, hop_length=self.hop_length))
                avg_spectrum = np.mean(stft, axis=1)
                
                role = self._infer_role(wav_path.name)
                stems_data[wav_path] = {
                    "y": y,
                    "sr": sr,
                    "spectrum": avg_spectrum,
                    "role": role,
                    "priority": self._get_priority(role)
                }
            except Exception as e:
                logger.error(f"Error analyzing {wav_path}: {e}")

        if not stems_data:
            return

        # 2. Identify masking and calculate EQ for each stem
        freqs = librosa.fft_frequencies(sr=self.sample_rate, n_fft=self.n_fft)
        
        for target_path, target_info in stems_data.items():
            board = Pedalboard()
            target_spectrum = target_info["spectrum"]
            
            # Apply basic highpass for non-bass roles
            if target_info["role"] not in ["bass", "sub", "kick", "drums"]:
                board.append(HighpassFilter(cutoff_frequency_hz=100.0))

            # Identify clashing frequencies with higher-priority stems
            for other_path, other_info in stems_data.items():
                if target_path == other_path:
                    continue
                
                # If other stem has higher priority or is in a "dominant" role
                if other_info["priority"] > target_info["priority"]:
                    # Find frequency bands where other stem is loud
                    other_spectrum = other_info["spectrum"]
                    
                    # Normalize spectra for comparison
                    target_norm = target_spectrum / (np.max(target_spectrum) + 1e-6)
                    other_norm = other_spectrum / (np.max(other_spectrum) + 1e-6)
                    
                    # Find peaks in other spectrum that overlap with target
                    clash_mask = (other_norm > 0.3) & (target_norm > 0.2)
                    
                    if np.any(clash_mask):
                        # Find the strongest clash frequency
                        clash_idx = np.argmax(other_norm * clash_mask)
                        clash_freq = freqs[clash_idx]
                        
                        # Apply a dip in the target stem
                        # Limit clash freq to reasonable EQ range (20Hz - 20kHz)
                        if 20 <= clash_freq <= 20000:
                            # Avoid dipping bass in bass stems, etc.
                            if target_info["role"] == "bass" and clash_freq < 150:
                                continue
                                
                            board.append(PeakFilter(
                                cutoff_frequency_hz=float(clash_freq),
                                gain_db=-3.0,
                                q=1.0
                            ))
            
            # 3. Apply EQ and overwrite file
            if len(board) > 0:
                try:
                    effected = board(target_info["y"], target_info["sr"])
                    sf.write(str(target_path), effected.T if len(effected.shape) > 1 else effected, target_info["sr"])
                    logger.info(f"Applied EQ to {target_path.name}")
                except Exception as e:
                    logger.error(f"Error applying EQ to {target_path}: {e}")

    def _infer_role(self, filename: str) -> str:
        """Infers the instrument role from the filename."""
        name = filename.lower()
        if "bass" in name or "sub" in name:
            return "bass"
        if "lead" in name or "melody" in name or "synth" in name:
            return "lead"
        if "chord" in name or "pad" in name or "piano" in name:
            return "chords"
        if "kick" in name:
            return "kick"
        if "drum" in name or "perc" in name or "loop" in name:
            return "drums"
        if "vocal" in name or "vox" in name:
            return "vocal"
        return "other"

    def _get_priority(self, role: str) -> int:
        """Returns a priority score for the role (higher = more dominant)."""
        priorities = {
            "vocal": 10,
            "kick": 9,
            "bass": 8,
            "lead": 7,
            "drums": 6,
            "chords": 5,
            "other": 4
        }
        return priorities.get(role, 4)
