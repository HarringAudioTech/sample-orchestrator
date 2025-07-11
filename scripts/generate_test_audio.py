"""
Generate test audio files for testing the audio slicing functionality.

This script creates audio files with different sections that should be detected as:
- Loops (repeating patterns)
- One-shots (single hits)
- Silence (should be ignored)
"""

import os
import numpy as np
import soundfile as sf
from scipy import signal

def generate_sine_wave(freq, duration, sample_rate=44100, amplitude=0.5):
    """Generate a sine wave with the given frequency and duration."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    return amplitude * np.sin(2 * np.pi * freq * t)

def generate_drum_hit(duration=0.1, sample_rate=44100, freq=100, decay=0.9):
    """Generate a simple drum hit sound."""
    t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    env = np.exp(-5 * t / duration)  # Exponential decay envelope
    tone = np.sin(2 * np.pi * freq * t) * env
    noise = np.random.uniform(-1, 1, len(t)) * (1 - env) * 0.5
    return (tone + noise) * 0.5

def generate_test_audio(output_path, bpm=120, sample_rate=44100):
    """Generate a test audio file with different sections."""
    # Calculate samples per beat
    spb = int((60 / bpm) * sample_rate)
    
    # Initialize output array (stereo)
    length = spb * 16  # 16 beats
    audio = np.zeros((length, 2))
    
    # 1. Add a simple drum loop (kick on 1 and 3, snare on 2 and 4)
    for i in range(0, 16, 2):
        # Kick drum on beats 1 and 3
        if i % 4 == 0:
            hit = generate_drum_hit(0.2, sample_rate, 60, 0.8)
        # Snare drum on beats 2 and 4
        else:
            hit = generate_drum_hit(0.15, sample_rate, 200, 0.7)
        
        start = i * spb // 2
        end = start + len(hit)
        if end <= length:
            audio[start:end, 0] += hit[:length-start]
            audio[start:end, 1] += hit[:length-start]
    
    # 2. Add a bassline (simple sine wave)
    for i in range(0, 16, 2):
        note_freq = 55.0 * (2 ** (i % 4))  # Simple pattern
        duration = 0.5 if i % 4 == 0 else 0.25  # Vary note lengths
        
        start = i * spb // 2
        end = start + int(duration * sample_rate)
        if end > length:
            end = length
        
        t = np.linspace(0, duration, end - start, endpoint=False)
        note = 0.3 * np.sin(2 * np.pi * note_freq * t)
        env = np.ones_like(note)
        env[-int(0.05 * sample_rate):] = np.linspace(1, 0, int(0.05 * sample_rate))
        
        audio[start:end, 0] += note * env
        audio[start:end, 1] += note * env
    
    # 3. Add some one-shot sounds
    one_shot_positions = [spb * 8, spb * 12, spb * 14]
    for pos in one_shot_positions:
        hit = generate_drum_hit(0.3, sample_rate, 300, 0.6)
        end = pos + len(hit)
        if end <= length:
            audio[pos:end, 0] += hit[:length-pos] * 0.7
            audio[pos:end, 1] += hit[:length-pos] * 0.7
    
    # 4. Add some silence at the end
    audio[spb * 15:, :] = 0
    
    # Normalize to prevent clipping
    max_val = np.max(np.abs(audio))
    if max_val > 0.9:
        audio = audio * (0.9 / max_val)
    
    # Write to file
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    sf.write(output_path, audio, sample_rate, 'PCM_24')
    print(f"Generated test audio: {output_path}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate test audio files')
    parser.add_argument('--output', default='./test_audio/test_loop.wav',
                       help='Output file path')
    parser.add_argument('--bpm', type=int, default=120,
                       help='Tempo in BPM')
    
    args = parser.parse_args()
    generate_test_audio(args.output, args.bpm)
