# Audio Slicing Test Scripts

This directory contains scripts to test and demonstrate the audio slicing functionality.

## Prerequisites

1. Install the required Python packages:
   ```bash
   pip install -r requirements-test.txt
   ```

2. Ensure you have the main project dependencies installed (from the project root):
   ```bash
   pip install -e .
   ```

## Generating Test Audio

1. Run the test audio generator:
   ```bash
   python generate_test_audio.py --output ./test_audio/test_loop.wav --bpm 120
   ```

   This will create a test audio file with:
   - A drum loop (kick on 1 and 3, snare on 2 and 4)
   - A simple bassline
   - Some one-shot sounds
   - Silence at the end

## Running the Audio Slicing Test

1. Run the test script with the generated audio file:
   ```bash
   python test_audio_slicing.py ./test_audio/test_loop.wav --output-dir ./output_samples
   ```

2. The script will:
   - Create a test recording in the database
   - Process the audio file using the SlicingStage
   - Extract loops and one-shots
   - Save the extracted samples to the output directory
   - Print information about the extracted samples

## Expected Output

You should see output similar to:
```
2023-04-01 12:00:00,000 - __main__ - INFO - Created test recording with ID: 1
2023-04-01 12:00:00,100 - __main__ - INFO - Starting audio slicing for /path/to/test_loop.wav
2023-04-01 12:00:01,234 - SlicingStage - INFO - [SlicingStage] Loaded audio: 44100 Hz, 2 channels, 10.0 seconds
2023-04-01 12:00:02,345 - SlicingStage - INFO - [SlicingStage] Detected BPM: 120.0
2023-04-01 12:00:03,456 - SlicingStage - INFO - [SlicingStage] Created 8 samples from recording 1
2023-04-01 12:00:03,457 - __main__ - INFO - Created 8 samples:
1. test_loop_001.wav | Type: loop | BPM: 120.0 | Key: Cm | Duration: 2.00s
2. test_loop_002.wav | Type: one_shot | BPM: N/A | Key: N/A | Duration: 0.15s
...
```

## Verifying Results

1. Check the output directory for the extracted samples:
   ```bash
   ls -l ./output_samples/
   ```

2. You should see:
   - Multiple WAV files (one for each detected sample)
   - A mix of loop and one-shot samples
   - Properly named files with metadata in the filename

## Troubleshooting

- If you get import errors, ensure the project root is in your PYTHONPATH
- If the audio doesn't play correctly, check that you have the required audio codecs installed
- For database errors, make sure the database is properly configured in your environment variables
