import dataclasses
from dataclasses import field
from typing import List, Optional, Any
import soundfile
import librosa
import numpy as np
# Assuming soundfile_utils.py is in src.utils
# Adjust if the project structure is different or if specific functions are needed.
from src.utils import soundfile_utils


class VocalChopIdealCharacteristics:
    """Stores ideal parameters for vocal chops."""
    min_silence_duration_ms: float = 75.0
    expected_stab_counts: List[int] = [2, 4, 8, 16, 32, 64]  # powers of 2
    require_tempo_metadata: bool = True
    require_key_metadata: bool = True
    require_cue_labels: bool = True

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


class VocalChopEvaluator:
    def __init__(self, ideal_characteristics: VocalChopIdealCharacteristics):
        self.ideal_characteristics = ideal_characteristics

    def _detect_clicks_pops(self, audio_segment: np.ndarray, sample_rate: int) -> bool:
        # Placeholder for actual click/pop detection logic
        # TODO: Implement actual detection (e.g., high-frequency transient detection)
        # For now, this will not detect anything.
        # Example:
        #   high_freq_content = librosa.effects.preemphasis(audio_segment)
        #   rms = librosa.feature.rms(y=high_freq_content)
        #   if np.any(rms > threshold): return True
        return False

    def evaluate(self, file_path: str) -> VocalChopEvaluationResult:
        evaluation_result = VocalChopEvaluationResult(file_path=file_path)
        y = None
        sr = 0

        # Load Audio and Basic Info (using soundfile for metadata, librosa for audio array)
        try:
            with soundfile.SoundFile(file_path, 'r') as sf_file:
                evaluation_result.sample_rate = sf_file.samplerate
                sr = sf_file.samplerate # Store for librosa
                evaluation_result.channels = sf_file.channels
                evaluation_result.duration_ms = (sf_file.frames / sf_file.samplerate) * 1000
        except soundfile.LibsndfileError as e:
            evaluation_result.issues.append(f"Error loading audio file with soundfile: {e}")
            return evaluation_result # Cannot proceed
        except Exception as e: # Catch other potential errors during file info reading
            evaluation_result.issues.append(f"Unexpected error loading audio file info: {e}")
            return evaluation_result

        try:
            y, sr_librosa = librosa.load(file_path, sr=sr, mono=False) # Use sr from soundfile
            if sr_librosa != sr: # Should not happen if sr is passed correctly
                evaluation_result.issues.append(
                    f"Sample rate mismatch: soundfile ({sr}Hz), librosa ({sr_librosa}Hz)."
                )
                # Potentially handle this error more gracefully or re-load
                return evaluation_result
        except Exception as e:
            evaluation_result.issues.append(f"Error loading audio data with librosa: {e}")
            return evaluation_result # Cannot proceed without audio data

        y_mono: np.ndarray
        if y.ndim > 1:
            y_mono = librosa.to_mono(y)
        else:
            y_mono = y

        audio_duration_samples = len(y_mono)

        # Metadata Extraction
        cue_markers = soundfile_utils.get_cue_markers(file_path)
        if cue_markers:
            evaluation_result.cue_markers_present = True
            has_any_label = False
            for cue in cue_markers:
                label = None
                if cue.name and cue.name != b'\x00': # Check if name is not empty or just null bytes
                    try:
                        label = cue.name.decode('utf-8', errors='replace').strip()
                        if label: # Ensure label is not empty after strip
                             has_any_label = True
                    except Exception:
                        label = "Error decoding label" # Or keep None

                # For now, end_sample is not known from cues alone, set to start_sample or a placeholder
                # This will be updated by more detailed stab analysis later.
                evaluation_result.stabs.append(AnalyzedVocalStab(
                    start_sample=int(cue.position),
                    end_sample=int(cue.position), # Placeholder, to be updated
                    label=label
                ))
            if has_any_label:
                evaluation_result.cue_labels_present = True

        # Stab Boundary Refinement/Detection
        if evaluation_result.cue_markers_present and evaluation_result.stabs:
            # Estimate end_sample for cue-based stabs
            for i in range(len(evaluation_result.stabs) - 1):
                evaluation_result.stabs[i].end_sample = evaluation_result.stabs[i+1].start_sample
            evaluation_result.stabs[-1].end_sample = audio_duration_samples
        else: # No Cues Present (Stab Detection)
            evaluation_result.issues.append("Cue markers not found or stabs list empty, attempting onset detection.")
            try:
                onsets_samples = librosa.onset.onset_detect(y=y_mono, sr=sr, units='samples', backtrack=False)
                if len(onsets_samples) > 0:
                    for i, onset_sample in enumerate(onsets_samples):
                        start_s = int(onset_sample)
                        end_s = int(onsets_samples[i+1]) if i < len(onsets_samples) - 1 else audio_duration_samples
                        stab = AnalyzedVocalStab(start_sample=start_s, end_sample=end_s)
                        stab.issues.append("Stab detected by onset analysis, not from cues.")
                        evaluation_result.stabs.append(stab)

                    if len(evaluation_result.stabs) not in self.ideal_characteristics.expected_stab_counts:
                        evaluation_result.issues.append(
                            f"Detected stab count ({len(evaluation_result.stabs)}) is not an ideal power of 2."
                        )
                        evaluation_result.stab_count_is_power_of_2 = False
                    else:
                        evaluation_result.stab_count_is_power_of_2 = True
                else:
                    evaluation_result.issues.append("No onsets detected for automatic stab creation.")
            except Exception as e:
                evaluation_result.issues.append(f"Error during onset detection: {e}")

        # Zero-Crossing and Duration for Stabs
        zc_window_ms = 5 # 5ms window for zero-crossing check
        zc_window_samples = int((zc_window_ms / 1000.0) * sr)

        for i, stab in enumerate(evaluation_result.stabs):
            if stab.end_sample <= stab.start_sample: # Ensure end is after start
                stab.duration_ms = 0.0
                stab.issues.append("End sample is not after start sample. Duration is 0.")
            else:
                stab.duration_ms = ((stab.end_sample - stab.start_sample) / sr) * 1000

            # Zero-Crossing Check for start
            start_zc_segment = y_mono[max(0, stab.start_sample - zc_window_samples // 2) :
                                      min(audio_duration_samples, stab.start_sample + zc_window_samples // 2)]
            if len(start_zc_segment) > 0:
                if np.sum(librosa.zero_crossings(start_zc_segment)) > 0:
                    stab.has_clean_start_zero_crossing = True
                else:
                    stab.has_clean_start_zero_crossing = False
                    stab.issues.append("No clean start zero-crossing detected.")

            # Zero-Crossing Check for end
            end_zc_segment = y_mono[max(0, stab.end_sample - zc_window_samples // 2) :
                                    min(audio_duration_samples, stab.end_sample + zc_window_samples // 2)]
            if len(end_zc_segment) > 0:
                if np.sum(librosa.zero_crossings(end_zc_segment)) > 0:
                    stab.has_clean_end_zero_crossing = True
                else:
                    stab.has_clean_end_zero_crossing = False
                    stab.issues.append("No clean end zero-crossing detected.")

            # Basic Click/Pop Detection (Stub)
            stab_audio_segment = y_mono[stab.start_sample:stab.end_sample]
            if len(stab_audio_segment) > 0:
                if self._detect_clicks_pops(stab_audio_segment, sr):
                    evaluation_result.click_pop_detected = True # Mark at overall level
                    stab.issues.append("Potential clicks/pops detected in this stab.")
                    if "Potential clicks/pops detected in stabs" not in evaluation_result.issues:
                         evaluation_result.issues.append("Potential clicks/pops detected in stabs")


        # Silence Analysis (between stabs)
        if len(evaluation_result.stabs) > 1:
            total_silence_duration_ms = 0.0
            num_silence_segments = 0
            for i in range(len(evaluation_result.stabs) - 1):
                current_stab = evaluation_result.stabs[i]
                next_stab = evaluation_result.stabs[i+1]

                silence_start_sample = current_stab.end_sample
                silence_end_sample = next_stab.start_sample

                if silence_end_sample > silence_start_sample:
                    # silence_segment_audio = y_mono[silence_start_sample:silence_end_sample] # For RMS analysis later
                    silence_duration_samples = silence_end_sample - silence_start_sample
                    silence_duration_ms = (silence_duration_samples / sr) * 1000

                    if silence_duration_ms < self.ideal_characteristics.min_silence_duration_ms:
                        evaluation_result.issues.append(
                            f"Silence after stab '{current_stab.label or i+1}' is too short ({silence_duration_ms:.2f}ms)."
                        )
                    total_silence_duration_ms += silence_duration_ms
                    num_silence_segments += 1
                    # TODO: Analyze noise level of silence_segment_audio.
                    # rms_silence = librosa.feature.rms(y=silence_segment_audio)
                    # if np.mean(rms_silence) > noise_threshold:
                    #    evaluation_result.denoising_recommended = True
                    #    evaluation_result.issues.append("High noise level detected in silence between stabs.")
                else: # No silence or overlapping stabs based on current end_sample logic
                    evaluation_result.issues.append(
                        f"No silence or overlap between stab '{current_stab.label or i+1}' and '{next_stab.label or i+2}'."
                    )


            if num_silence_segments > 0:
                evaluation_result.average_silence_between_stabs_ms = total_silence_duration_ms / num_silence_segments
            else:
                evaluation_result.average_silence_between_stabs_ms = 0.0 # Or None if preferred
        elif len(evaluation_result.stabs) == 1:
             evaluation_result.average_silence_between_stabs_ms = None # Not applicable for single stab files


        # Tempo/Key Estimation (if not in metadata)
        if not evaluation_result.metadata_tempo_present:
            try:
                estimated_tempo, _ = librosa.beat.beat_track(y=y_mono, sr=sr)
                if estimated_tempo is not None and estimated_tempo > 0: # beat_track can return 0
                    evaluation_result.tempo = float(estimated_tempo)
                    evaluation_result.issues.append("Tempo estimated using librosa.")
                else:
                    evaluation_result.issues.append("Tempo estimation failed or returned zero.")
            except Exception as e:
                evaluation_result.issues.append(f"Error during tempo estimation: {e}")

        if not evaluation_result.metadata_key_present:
            # Basic key estimation using chroma features
            # More advanced key finding might be needed for accuracy
            try:
                chroma_stft = librosa.feature.chroma_stft(y=y_mono, sr=sr)
                # Summing chroma features across time to get a pitch class profile
                # Taking argmax of this profile gives the most prominent pitch class (0-11)
                # 0 = C, 1 = C#, ..., 11 = B
                # This is a simplification; does not account for major/minor.
                chroma_sum = np.sum(chroma_stft, axis=1)
                estimated_key_idx = np.argmax(chroma_sum)

                # Convert MIDI-like index (0-11 for C-B) to note name.
                # librosa.midi_to_note expects a full MIDI number.
                # We can map common MIDI numbers for C4, C#4 etc.
                # For simplicity, let's map 0-11 directly to note names.
                # C4 = 60. So, 60+estimated_key_idx for octave 4.
                evaluation_result.key = librosa.midi_to_note(60 + estimated_key_idx, octave=False, sharps=True)
                evaluation_result.issues.append("Key estimated using librosa (basic chroma).")
            except Exception as e:
                evaluation_result.issues.append(f"Error during key estimation: {e}")

        instrument_info = soundfile_utils.get_instrument_info(file_path)
        if instrument_info:
            if 0 <= instrument_info.basenote <= 127:
                try:
                    # Overwrite if estimated, or fill if not present and instrument info is valid.
                    key_from_instrument = librosa.midi_to_note(instrument_info.basenote)
                    if not evaluation_result.metadata_key_present or evaluation_result.key != key_from_instrument:
                        evaluation_result.key = key_from_instrument
                        evaluation_result.issues.append(f"Key from instrument metadata: {evaluation_result.key}")
                    evaluation_result.metadata_key_present = True
                except Exception:
                    evaluation_result.metadata_key_present = True
                except Exception:
                     evaluation_result.issues.append(f"Invalid root_key in loop_info: {loop_info.root_key}")


        # Idealness Checks (some might have been done based on cue presence earlier)
        if self.ideal_characteristics.require_tempo_metadata and \
           not evaluation_result.metadata_tempo_present and \
           evaluation_result.tempo is None : # Check if estimation also failed
            evaluation_result.issues.append(
                "Tempo metadata missing and estimation failed, but required by ideal characteristics."
            )

        if self.ideal_characteristics.require_key_metadata and \
           not evaluation_result.metadata_key_present and \
           evaluation_result.key is None: # Check if estimation also failed
            evaluation_result.issues.append(
                "Key metadata missing and estimation failed, but required by ideal characteristics."
            )

        # This check is now done after potential onset detection if cues were missing
        if not evaluation_result.stabs: # If still no stabs after cues and onsets
            evaluation_result.issues.append("No stabs found (neither from cues nor onset detection).")
        elif self.ideal_characteristics.require_cue_labels and \
            evaluation_result.cue_markers_present and not evaluation_result.cue_labels_present:
            # This specific check remains valid if cues were the source
            evaluation_result.issues.append(
                "Cue labels missing for cued stabs, but required by ideal characteristics."
            )
        # Stab count check is now performed within cue or onset detection logic.

        return evaluation_result
