#!/usr/bin/env python
"""
Generates various WAV audio files for testing purposes.

This script creates:
1. A pure sine wave at A4 (440 Hz) for 1 second.
2. A sequence of C4, silence, and G4.
3. (Optionally) A short staccato C5 note.
"""

import os
import numpy as np
from scipy.io import wavfile
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_sine_wave(frequency: float, duration: float, samplerate: int = 44100, amplitude: float = 0.5) -> np.ndarray:
    """
    Generates a sine wave as a NumPy array scaled to 16-bit integer range.

    Args:
        frequency (float): Frequency of the sine wave in Hz.
        duration (float): Duration of the wave in seconds.
        samplerate (int): Samplerate in Hz. Defaults to 44100.
        amplitude (float): Amplitude of the wave (0.0 to 1.0). Defaults to 0.5.
                           This will be scaled to the 16-bit integer range.

    Returns:
        np.ndarray: A NumPy array of type np.int16 representing the sine wave.
    """
    logging.debug(f"Generating sine wave: freq={frequency}Hz, dur={duration}s, sr={samplerate}, amp={amplitude}")
    t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
    wave = amplitude * np.sin(2 * np.pi * frequency * t)
    
    # Scale to 16-bit integer range and convert type
    # Max value for int16 is 32767
    scaled_wave = np.int16(wave * 32767)
    return scaled_wave

def generate_silence(duration: float, samplerate: int = 44100) -> np.ndarray:
    """
    Generates silence as a NumPy array of np.int16.

    Args:
        duration (float): Duration of the silence in seconds.
        samplerate (int): Samplerate in Hz. Defaults to 44100.

    Returns:
        np.ndarray: A NumPy array of zeros of type np.int16.
    """
    logging.debug(f"Generating silence: dur={duration}s, sr={samplerate}")
    num_samples = int(samplerate * duration)
    silence = np.zeros(num_samples, dtype=np.int16)
    return silence

def save_wav(filepath: str, samplerate: int, data: np.ndarray):
    """
    Saves a NumPy array as a WAV file.

    Args:
        filepath (str): The path (including filename) to save the WAV file.
        samplerate (int): The samplerate of the audio data.
        data (np.ndarray): The audio data (NumPy array, should be np.int16).
    
    Raises:
        ValueError: If data is not np.int16 type.
    """
    if data.dtype != np.int16:
        # scipy.io.wavfile.write can handle float32 by normalizing,
        # but we explicitly want int16 for this script's purpose.
        # If floats are passed, they should be in range [-1, 1].
        # Forcing int16 makes our scaling in generate_sine_wave meaningful.
        raise ValueError(f"Data must be of type np.int16 for save_wav, got {data.dtype}")
    
    logging.debug(f"Saving WAV file to: {filepath}, samplerate: {samplerate}, data shape: {data.shape}")
    try:
        wavfile.write(filepath, samplerate, data)
        logging.info(f"Successfully saved: {filepath}")
    except Exception as e:
        logging.error(f"Error saving WAV file {filepath}: {e}", exc_info=True)
        raise

def main():
    """
    Main function to generate and save test audio files.
    """
    output_directory = "tests/fixtures/audio/generated/"
    os.makedirs(output_directory, exist_ok=True)
    logging.info(f"Ensured output directory exists: {output_directory}")

    samplerate = 44100 # Common samplerate for all files

    # --- Tone 1: A4_440Hz_1sec.wav ---
    a4_freq = 440.0
    a4_duration = 1.0
    a4_data = generate_sine_wave(a4_freq, a4_duration, samplerate)
    a4_filepath = os.path.join(output_directory, "A4_440Hz_1sec.wav")
    save_wav(a4_filepath, samplerate, a4_data)

    # --- Tone 2: C4_G4_sequence.wav ---
    c4_freq = 261.63
    g4_freq = 392.00
    c4_duration = 0.5
    silence_duration = 0.2
    g4_duration = 0.5

    c4_data = generate_sine_wave(c4_freq, c4_duration, samplerate)
    silence_data = generate_silence(silence_duration, samplerate)
    g4_data = generate_sine_wave(g4_freq, g4_duration, samplerate)
    
    sequence_data = np.concatenate((c4_data, silence_data, g4_data))
    sequence_filepath = os.path.join(output_directory, "C4_G4_sequence.wav")
    save_wav(sequence_filepath, samplerate, sequence_data)

    # --- Tone 3: Short_C5_Staccato.wav ---
    c5_freq = 523.25
    c5_staccato_duration = 0.15
    c5_staccato_data = generate_sine_wave(c5_freq, c5_staccato_duration, samplerate, amplitude=0.7) # Slightly higher amplitude for distinctness
    c5_staccato_filepath = os.path.join(output_directory, "Short_C5_Staccato.wav")
    save_wav(c5_staccato_filepath, samplerate, c5_staccato_data)
    
    logging.info("All specified audio files generated.")

if __name__ == '__main__':
    # Make the script executable by running: chmod +x tests/fixtures/audio/generate_audio.py
    # Then run: ./tests/fixtures/audio/generate_audio.py
    # Or: python tests/fixtures/audio/generate_audio.py
    main()
