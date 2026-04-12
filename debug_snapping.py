import librosa
import numpy as np

def debug_snapping():
    test_file = "test_audio/drum_loop.wav"
    sr = 44100
    y, _ = librosa.load(test_file, sr=sr)
    
    sample_idx = 55274
    window_size = 1024
    start = max(0, sample_idx - window_size)
    end = min(len(y), sample_idx + window_size)
    
    segment = y[start:end]
    signbit = np.signbit(segment)
    sign_changes = np.where(np.diff(signbit))[0]
    
    print(f"Sample index: {sample_idx}")
    print(f"Value at sample: {y[sample_idx]}")
    print(f"Number of sign changes in window: {len(sign_changes)}")
    
    if len(sign_changes) > 0:
        crossings = []
        for i in sign_changes:
            if np.abs(segment[i]) < np.abs(segment[i+1]):
                crossings.append(i + start)
            else:
                crossings.append(i + 1 + start)
        
        crossings = np.array(crossings)
        closest_idx = crossings[np.argmin(np.abs(crossings - sample_idx))]
        print(f"Closest zero crossing found at index: {closest_idx}")
        print(f"Value at closest crossing: {y[closest_idx]}")
        
        # Check signs of neighbors
        if closest_idx > 0 and closest_idx < len(y) - 1:
            print(f"Signs at closest crossing (i-1, i, i+1): {np.sign(y[closest_idx-1])}, {np.sign(y[closest_idx])}, {np.sign(y[closest_idx+1])}")
    else:
        print("No sign changes in window.")
        min_abs_idx = np.argmin(np.abs(segment)) + start
        print(f"Minimum absolute value found at index: {min_abs_idx}, value: {y[min_abs_idx]}")

if __name__ == "__main__":
    debug_snapping()
