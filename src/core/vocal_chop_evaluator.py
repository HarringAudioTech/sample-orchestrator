"""Module for evaluating vocal chop audio files based on ideal characteristics."""
import dataclasses
from dataclasses import field
from typing import List, Optional

import soundfile  # type: ignore # pylint: disable=import-error
import librosa  # type: ignore # pylint: disable=import-error
import numpy as np  # type: ignore # pylint: disable=import-error

# Assuming soundfile_utils.py is in src.utils
# Adjust if the project structure is different or if specific functions are needed.
# pylint: disable=import-error
try:
    from src.utils import soundfile_utils
except ImportError:
    from utils import soundfile_utils  # type: ignore
# pylint: enable=import-error


# pylint: disable=too-few-public-methods
@dataclasses.dataclass
class VocalChopIdealCharacteristics:
    """Stores ideal parameters for vocal chops."""

    min_silence_duration_ms: float = 75.0
    expected_stab_counts: List[int] = field(
        default_factory=lambda: [2, 4, 8, 16, 32, 64]
    )
    require_tempo_metadata: bool = True
    require_key_metadata: bool = True
    require_cue_labels: bool = True


# pylint: disable=too-few-public-methods
@dataclasses.dataclass
class AnalyzedVocalStab:
    """Stores information about each detected/analyzed vocal stab."""

    start_sample: int
    end_sample: int
    label: Optional[str] = None
    duration_ms: float = 0.0
    has_clean_start_zero_crossing: bool = False
    has_clean_end_zero_crossing: bool = False
    issues: List[str] = field(default_factory=list)


# pylint: disable=too-few-public-methods,too-many-instance-attributes
@dataclasses.dataclass
class VocalChopEvaluationResult:
    """Holds the overall evaluation output for a vocal chop file."""

    file_path: str
    overall_idealness_score: float = 0.0  # To be defined later
    issues: List[str] = field(default_factory=list)
    stabs: List[AnalyzedVocalStab] = field(default_factory=list)
    duration_ms: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    tempo: Optional[float] = None
    key: Optional[str] = None
    metadata_tempo_present: bool = False
    metadata_key_present: bool = False
    cue_markers_present: bool = False
    cue_labels_present: bool = False  # Specifically if labels exist for cues
    stab_count_is_power_of_2: bool = False
    average_silence_between_stabs_ms: Optional[float] = None
    denoising_recommended: bool = False
    click_pop_detected: bool = False


# pylint: disable=too-few-public-methods
class VocalChopEvaluator:
    """Evaluates vocal chop files against ideal characteristics."""
    def __init__(self, ideal_characteristics: VocalChopIdealCharacteristics):
        self.ideal_characteristics = ideal_characteristics

    def _detect_clicks_pops(self, audio_segment: np.ndarray, sample_rate: int) -> bool:  # pylint: disable=unused-argument
        """
        Detects clicks and pops in an audio segment.
        Uses a simple high-frequency transient detection based on the 
        absolute second derivative (discontinuity detection).
        """
        if len(audio_segment) < 3:
            return False
            
        # Calculate second derivative to find sudden discontinuities
        # d2[n] = x[n] - 2*x[n-1] + x[n-2]
        d2 = np.abs(np.diff(audio_segment, n=2))
        
        # A threshold of 0.5 is quite high for normalized audio (-6dB delta)
        # but prevents too many false positives on legitimate transients.
        # We also check against local average to be more robust.
        threshold = 0.1
        
        if np.any(d2 > threshold):
            # Verify it's a spike by checking if it's much larger than its neighbors
            # (simple outlier detection)
            max_idx = np.argmax(d2)
            # Use a slightly larger window for local mean and smaller multiplier
            local_mean = np.mean(d2[max(0, max_idx-20):min(len(d2), max_idx+20)])
            if d2[max_idx] > local_mean * 5:
                return True
                
        return False

    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    def evaluate(self, file_path: str) -> VocalChopEvaluationResult:  # noqa: C901
        """
        Evaluates a vocal chop file based on various characteristics.

        Args:
            file_path: Path to the audio file to evaluate.

        Returns:
            A VocalChopEvaluationResult object containing the analysis.
        """
        evaluation_result = VocalChopEvaluationResult(file_path=file_path)
        y = None
        sr = 0

        try:
            with soundfile.SoundFile(file_path, "r") as sf_file:
                evaluation_result.sample_rate = sf_file.samplerate
                sr = sf_file.samplerate
                evaluation_result.channels = sf_file.channels
                evaluation_result.duration_ms = (
                    sf_file.frames / sf_file.samplerate
                ) * 1000
        except soundfile.LibsndfileError as e:
            evaluation_result.issues.append(
                f"Error loading audio file with soundfile: {e}"
            )
            return evaluation_result
        except Exception as e:
            evaluation_result.issues.append(
                f"Unexpected error loading audio file info: {e}"
            )
            return evaluation_result

        try:
            y, sr_librosa = librosa.load(file_path, sr=sr, mono=False)
            if sr_librosa != sr:
                evaluation_result.issues.append(
                    f"Sample rate mismatch: soundfile ({sr}Hz), librosa ({sr_librosa}Hz)."
                )
                return evaluation_result
        except Exception as e:  # pylint: disable=broad-except
            evaluation_result.issues.append(
                f"Error loading audio data with librosa: {e}"
            )
            return evaluation_result

        y_mono: np.ndarray
        if y.ndim > 1:
            y_mono = librosa.to_mono(y)
        else:
            y_mono = y

        audio_duration_samples = len(y_mono)

        # --- Commented out CFFI-based metadata reading ---
        # cue_markers = soundfile_utils.get_cue_markers(file_path)
        # if cue_markers:
        #     evaluation_result.cue_markers_present = True
        #     has_any_label = False
        #     for cue in cue_markers:
        #         label = None
        #         if cue.name and cue.name != b"\x00":
        #             try:
        #                 label = cue.name.decode("utf-8", errors="replace").strip()
        #                 if label:
        #                     has_any_label = True
        #             except Exception:  # pylint: disable=broad-except
        #                 label = "Error decoding label"
        #         evaluation_result.stabs.append(
        #             AnalyzedVocalStab(
        #                 start_sample=int(cue.position),
        #                 end_sample=int(cue.position),
        #                 label=label,
        #             )
        #         )
        #     if has_any_label:
        #         evaluation_result.cue_labels_present = True

        # if evaluation_result.cue_markers_present and evaluation_result.stabs:
        #     for i in range(len(evaluation_result.stabs) - 1):
        #         evaluation_result.stabs[i].end_sample = evaluation_result.stabs[
        #             i + 1
        #         ].start_sample
        #     if evaluation_result.stabs:
        #         evaluation_result.stabs[-1].end_sample = audio_duration_samples
        # else:
        # evaluation_result.issues.append( # This will now always be the case
        # "Cue markers not found or stabs list empty, attempting onset detection."
        # )
        # --- End of commented out CFFI-based metadata reading ---

        # Always attempt onset detection as cues are no longer read this way
        evaluation_result.issues.append(
            "Detailed cue marker metadata (e.g. from CUE chunks) is no longer read. "
            "Attempting onset detection for stab boundaries."
        )
        try:
            onsets_samples = librosa.onset.onset_detect(
                y=y_mono, sr=sr, units="samples", backtrack=False
            )
            if len(onsets_samples) > 0:
                for i, onset_sample in enumerate(onsets_samples):
                    start_s = int(onset_sample)
                    end_s = (
                        int(onsets_samples[i + 1])
                        if i < len(onsets_samples) - 1
                        else audio_duration_samples
                    )
                    stab = AnalyzedVocalStab(start_sample=start_s, end_sample=end_s)
                    stab.issues.append(
                        "Stab detected by onset analysis, not from cues."
                    )
                    evaluation_result.stabs.append(stab)

                if (
                    len(evaluation_result.stabs)
                    not in self.ideal_characteristics.expected_stab_counts
                ):
                    evaluation_result.issues.append(
                        f"Detected stab count ({len(evaluation_result.stabs)}) "
                        f"is not an ideal power of 2."
                    )
                    evaluation_result.stab_count_is_power_of_2 = False
                else:
                    evaluation_result.stab_count_is_power_of_2 = True
            else:
                evaluation_result.issues.append(
                    "No onsets detected for automatic stab creation."
                )
        except Exception as e:  # pylint: disable=broad-except
            evaluation_result.issues.append(f"Error during onset detection: {e}")
        # If no stabs from onset detection, then it's an issue.
        if not evaluation_result.stabs:
            evaluation_result.issues.append(
                "No stabs derived from onset detection. Further analysis might be limited."
            )


        zc_window_ms = 5
        zc_window_samples = int((zc_window_ms / 1000.0) * sr)

        for i, stab in enumerate(evaluation_result.stabs):
            if stab.end_sample <= stab.start_sample:
                stab.duration_ms = 0.0
                stab.issues.append(
                    "End sample is not after start sample. Duration is 0."
                )
            else:
                stab.duration_ms = ((stab.end_sample - stab.start_sample) / sr) * 1000

            start_zc_segment = y_mono[
                max(0, stab.start_sample - zc_window_samples // 2) : min(
                    audio_duration_samples, stab.start_sample + zc_window_samples // 2
                )
            ]
            if len(start_zc_segment) > 0:
                if np.sum(librosa.zero_crossings(start_zc_segment, pad=False)) > 0: # Added pad=False
                    stab.has_clean_start_zero_crossing = True
                else:
                    stab.has_clean_start_zero_crossing = False
                    stab.issues.append("No clean start zero-crossing detected.")

            end_zc_segment = y_mono[
                max(0, stab.end_sample - zc_window_samples // 2) : min(
                    audio_duration_samples, stab.end_sample + zc_window_samples // 2
                )
            ]
            if len(end_zc_segment) > 0:
                if np.sum(librosa.zero_crossings(end_zc_segment, pad=False)) > 0: # Added pad=False
                    stab.has_clean_end_zero_crossing = True
                else:
                    stab.has_clean_end_zero_crossing = False
                    stab.issues.append("No clean end zero-crossing detected.")

            stab_audio_segment = y_mono[stab.start_sample : stab.end_sample]
            if len(stab_audio_segment) > 0:
                if self._detect_clicks_pops(stab_audio_segment, sr):
                    evaluation_result.click_pop_detected = True
                    stab.issues.append("Potential clicks/pops detected in this stab.")
                    if (
                        "Potential clicks/pops detected in stabs"
                        not in evaluation_result.issues
                    ):
                        evaluation_result.issues.append(
                            "Potential clicks/pops detected in stabs"
                        )

        if len(evaluation_result.stabs) > 1:
            total_silence_duration_ms = 0.0
            num_silence_segments = 0
            for i in range(len(evaluation_result.stabs) - 1):
                current_stab = evaluation_result.stabs[i]
                next_stab = evaluation_result.stabs[i + 1]
                silence_start_sample = current_stab.end_sample
                silence_end_sample = next_stab.start_sample

                if silence_end_sample > silence_start_sample:
                    silence_duration_samples = silence_end_sample - silence_start_sample
                    silence_duration_ms = (silence_duration_samples / sr) * 1000
                    if (
                        silence_duration_ms
                        < self.ideal_characteristics.min_silence_duration_ms
                    ):
                        evaluation_result.issues.append(
                            f"Silence after stab '{current_stab.label or i+1}' "
                            f"is too short ({silence_duration_ms:.2f}ms)."
                        )
                    total_silence_duration_ms += silence_duration_ms
                    num_silence_segments += 1
                else:
                    evaluation_result.issues.append(
                        f"No silence or overlap between stab '{current_stab.label or i+1}' "
                        f"and '{next_stab.label or i+2}'."
                    )
            if num_silence_segments > 0:
                evaluation_result.average_silence_between_stabs_ms = (
                    total_silence_duration_ms / num_silence_segments
                )
            else:
                evaluation_result.average_silence_between_stabs_ms = 0.0
        elif len(evaluation_result.stabs) == 1:
            evaluation_result.average_silence_between_stabs_ms = None

        if not evaluation_result.metadata_tempo_present:
            try:
                estimated_tempo, _ = librosa.beat.beat_track(y=y_mono, sr=sr)
                if (
                    estimated_tempo is not None and estimated_tempo > 0
                ):
                    evaluation_result.tempo = float(estimated_tempo)
                    evaluation_result.issues.append("Tempo estimated using librosa.")
                else:
                    evaluation_result.issues.append(
                        "Tempo estimation failed or returned zero."
                    )
            except Exception as e:  # pylint: disable=broad-except
                evaluation_result.issues.append(f"Error during tempo estimation: {e}")

        if not evaluation_result.metadata_key_present:
            try:
                chroma_stft = librosa.feature.chroma_stft(y=y_mono, sr=sr)
                chroma_sum = np.sum(chroma_stft, axis=1)
                estimated_key_idx = np.argmax(chroma_sum)
                # Removed 'sharps' argument for librosa compatibility
                evaluation_result.key = librosa.midi_to_note(
                    60 + estimated_key_idx, octave=False
                )
                evaluation_result.issues.append(
                    "Key estimated using librosa (basic chroma)."
                )
            except Exception as e:  # pylint: disable=broad-except
                evaluation_result.issues.append(f"Error during key estimation: {e}")

        # --- Commented out CFFI-based detailed metadata reading ---
        # instrument_info = soundfile_utils.get_instrument_info(file_path)
        # if instrument_info:
        #     if 0 <= instrument_info.basenote <= 127:
        #         try:
        #             key_from_instrument = librosa.midi_to_note(instrument_info.basenote)
        #             if (
        #                 not evaluation_result.metadata_key_present
        #                 or evaluation_result.key != key_from_instrument
        #             ):
        #                 evaluation_result.key = key_from_instrument
        #                 evaluation_result.issues.append(
        #                     f"Key from instrument metadata: {evaluation_result.key}"
        #                 )
        #             evaluation_result.metadata_key_present = True
        #         except Exception:  # pylint: disable=broad-except
        #             evaluation_result.issues.append(
        #                 f"Invalid basenote in instrument_info: {instrument_info.basenote}"
        #             )

        # actual_loop_info = soundfile_utils.get_loop_info(file_path)
        # if actual_loop_info:
        #     if actual_loop_info.bpm > 0:
        #         if (
        #             not evaluation_result.metadata_tempo_present
        #             or evaluation_result.tempo != actual_loop_info.bpm
        #         ):
        #             evaluation_result.tempo = actual_loop_info.bpm
        #             evaluation_result.issues.append(
        #                 f"Tempo from loop metadata: {actual_loop_info.bpm} BPM."
        #             )
        #         evaluation_result.metadata_tempo_present = True

        #     if not evaluation_result.metadata_key_present and \
        #        (0 <= actual_loop_info.root_key <= 127):
        #         try:
        #             evaluation_result.key = librosa.midi_to_note(actual_loop_info.root_key)
        #             evaluation_result.metadata_key_present = True
        #             evaluation_result.issues.append(
        #                 f"Key from loop metadata: {evaluation_result.key}"
        #             )
        #         except Exception:  # pylint: disable=broad-except
        #              evaluation_result.issues.append(
        #                  f"Invalid root_key in loop_info: {actual_loop_info.root_key}"
        #             )
        # --- End of commented out CFFI-based detailed metadata reading ---

        # Standard metadata (like title, artist, comment which might contain key/tempo)
        # would be read by a different mechanism if needed here, possibly using
        # soundfile_utils.read_standard_metadata() if we decide evaluator needs it.
        # For now, tempo/key rely on librosa estimation if not already set by (now removed)
        # detailed metadata. The flags metadata_tempo_present and metadata_key_present
        # will remain mostly False unless standard tags are parsed for this info.

        if (
            self.ideal_characteristics.require_tempo_metadata
            and not evaluation_result.metadata_tempo_present
            and evaluation_result.tempo is None
        ):
            evaluation_result.issues.append(
                "Tempo metadata missing and estimation failed, "
                "but required by ideal characteristics."
            )

        if (
            self.ideal_characteristics.require_key_metadata
            and not evaluation_result.metadata_key_present
            and evaluation_result.key is None
        ):
            evaluation_result.issues.append(
                "Key metadata missing and estimation failed, "
                "but required by ideal characteristics."
            )

        if not evaluation_result.stabs:
            evaluation_result.issues.append(
                "No stabs found (neither from cues nor onset detection)."
            )
        elif (
            self.ideal_characteristics.require_cue_labels
            and evaluation_result.cue_markers_present
            and not evaluation_result.cue_labels_present
        ):
            evaluation_result.issues.append(
                "Cue labels missing for cued stabs, "
                "but required by ideal characteristics."
            )

        return evaluation_result
