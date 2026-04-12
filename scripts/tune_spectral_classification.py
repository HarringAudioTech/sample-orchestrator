import os
import sys
from pathlib import Path
import numpy as np
import librosa
import json

def analyze_file(file_path):
    y, sr = librosa.load(file_path, sr=None)
    
    # Compute spectral features
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
    flatness = librosa.feature.spectral_flatness(y=y)
    
    return {
        "centroid": float(np.mean(centroid)),
        "flatness": float(np.mean(flatness)),
        "duration": float(librosa.get_duration(y=y, sr=sr))
    }

def main():
    ground_truth_dir = Path("test_audio/ground_truth_drums")
    if not ground_truth_dir.exists():
        print(f"Directory {ground_truth_dir} not found.")
        return

    results = {
        "kick": [],
        "snare": [],
        "hihat": [],
        "tom": [],
        "perc": []
    }

    for file in ground_truth_dir.glob("*.wav"):
        name = file.name.lower()
        category = None
        if "kick" in name:
            category = "kick"
        elif "snare" in name:
            category = "snare"
        elif "hat" in name:
            category = "hihat"
        elif "tom" in name:
            category = "tom"
        elif "perc" in name:
            category = "perc"
        
        if category:
            print(f"Analyzing {file.name} as {category}...")
            features = analyze_file(file)
            results[category].append({
                "name": file.name,
                "features": features
            })

    # Summary report
    print("\n--- Spectral Analysis Summary ---")
    summary = {}
    for cat, items in results.items():
        if not items:
            continue
        
        centroids = [item["features"]["centroid"] for item in items]
        flatnesses = [item["features"]["flatness"] for item in items]
        durations = [item["features"]["duration"] for item in items]
        
        summary[cat] = {
            "centroid": {
                "min": min(centroids),
                "max": max(centroids),
                "mean": sum(centroids) / len(centroids)
            },
            "flatness": {
                "min": min(flatnesses),
                "max": max(flatnesses),
                "mean": sum(flatnesses) / len(flatnesses)
            },
            "duration": {
                "min": min(durations),
                "max": max(durations),
                "mean": sum(durations) / len(durations)
            }
        }
        
        print(f"\nCategory: {cat.upper()} ({len(items)} samples)")
        for item in sorted(items, key=lambda x: x["features"]["centroid"]):
            print(f"  {item['name']:30} Centroid: {item['features']['centroid']:8.2f} Flatness: {item['features']['flatness']:8.6f}")
        
        print(f"  ---")
        print(f"  Centroid: min={summary[cat]['centroid']['min']:.2f}, max={summary[cat]['centroid']['max']:.2f}, mean={summary[cat]['centroid']['mean']:.2f}")
        print(f"  Flatness: min={summary[cat]['flatness']['min']:.6f}, max={summary[cat]['flatness']['max']:.6f}, mean={summary[cat]['flatness']['mean']:.6f}")
        print(f"  Duration: min={summary[cat]['duration']['min']:.3f}, max={summary[cat]['duration']['max']:.3f}, mean={summary[cat]['duration']['mean']:.3f}")

    # Propose thresholds
    print("\n--- Proposed Thresholds ---")
    
    if "kick" in summary and ("snare" in summary or "hihat" in summary):
        # Kick max centroid should be above kick max but below snare/hat min
        kick_max_c = summary["kick"]["centroid"]["max"]
        # Find the next lowest centroid that isn't a kick
        others = []
        for cat in ["snare", "hihat", "tom", "perc"]:
            if cat in summary:
                others.append(summary[cat]["centroid"]["min"])
        
        if others:
            other_min_c = min(others)
            suggested_kick_limit = (kick_max_c + other_min_c) / 2
            print(f"Suggested kick_max_centroid: {suggested_kick_limit:.0f} (Midpoint between Kick max {kick_max_c:.0f} and {other_min_c:.0f})")
        else:
            print(f"Suggested kick_max_centroid: {kick_max_c * 1.2:.0f} (Kick max {kick_max_c:.0f} + 20% margin)")

    if "hihat" in summary:
        hat_min_c = summary["hihat"]["centroid"]["min"]
        # Find the highest centroid that isn't a hat
        others = []
        for cat in ["kick", "snare", "tom", "perc"]:
            if cat in summary:
                others.append(summary[cat]["centroid"]["max"])
        
        if others:
            other_max_c = max(others)
            suggested_hat_limit = (hat_min_c + other_max_c) / 2
            print(f"Suggested hat_min_centroid: {suggested_hat_limit:.0f} (Midpoint between Hat min {hat_min_c:.0f} and {other_max_c:.0f})")
        else:
            print(f"Suggested hat_min_centroid: {hat_min_c * 0.8:.0f} (Hat min {hat_min_c:.0f} - 20% margin)")

    if "snare" in summary:
        # Snares usually have higher flatness than kicks or toms
        snare_min_f = summary["snare"]["flatness"]["min"]
        print(f"Suggested snare_min_flatness: {snare_min_f * 0.9:.4f} (Snare min {snare_min_f:.4f} - 10% margin)")

if __name__ == "__main__":
    main()
