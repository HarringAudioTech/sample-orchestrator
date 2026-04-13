# Implementation Plan: Loop Generation Integration

## Phase 1: Environment and Dependencies
- [x] Task: Add `amanuensis` and `patchlab` as local pip editable dependencies in `pyproject.toml` (e.g. `pip install -e ../amanuensis`).
- [x] Task: Ensure the development environment can successfully import both `amanuensis` and `patchlab-python`.

## Phase 2: Amanuensis Integration (MIDI Generation)
- [x] Task: Create a service/wrapper in `src/core/` to interface with Amanuensis.
- [x] Task: Review and adapt the logic from `amanuensis/session_output/batch_loops.py` and `batch_kits.py` as the reference for generating the target MIDI lines.
- [x] Task: Implement generation of single-track monophonic MIDI loops (e.g., basslines, leads) using the reference logic.
- [x] Task: Implement generation of single-track polyphonic MIDI loops (e.g., chord progressions) using the reference logic.
- [x] Task: Add variations generation logic utilizing Amanuensis capabilities.
- [x] Task: Verify output MIDI files are correctly generated and stored.

## Phase 3: Synthesizer Manipulation & Python Audio Recording
- [x] Task: Create a service/wrapper in `src/core/` to interface with Patchlab solely for patch loading and parameter control.
- [x] Task: Build out robust audio recording infrastructure within Sample Orchestrator using Python (e.g., PyAudio/Soundfile).
- [x] Task: Coordinate Patchlab (to control the synth) and Amanuensis (to send MIDI), while Sample Orchestrator captures the resulting audio directly.
- [x] Task: Verify the Python-based audio capture accurately records the monophonic and polyphonic phrases without relying on Patchlab's vestigial capture.

## Phase 4: Output Organization
- [x] Task: Update the export pipeline to save generated audio loops alongside their source MIDI files.
- [x] Task: Implement metadata tagging (tempo, key, loop type) for the new loops.
- [x] Task: Verify output directory structures and ensure they are ready for future "Construction Kit" enhancements.

## Phase 5: Construction Kit Spectral EQ Pass
- [ ] Task: Create a utility (e.g., `src/core/spectral_eq.py`) to analyze and process audio stems within a section directory.
- [ ] Task: Implement spectral analysis using `librosa` to compute the average frequency power across bands for all stems in a section.
- [ ] Task: Develop logic to detect frequency masking between stems and generate dynamic EQ curves (using `pedalboard` filters like `PeakFilter` or `HighpassFilter`/`LowpassFilter`) to attenuate overlapping frequencies.
- [ ] Task: Prioritize frequencies based on instrument roles inferred from the filename or tags (e.g., Bass gets priority in low frequencies, Lead in mids/highs).
- [ ] Task: Integrate the EQ pass into `src/core/construction_kit_exporter.py` so that all `.wav` files within a `Song_Name/Section_Name` directory are processed together before the final zip archive is created.
- [ ] Task: Validate the resulting stems have improved separation and sit well together without significant masking.

## Phase 6: Python 3.14 & Distroless Docker Upgrade
- [ ] Task: Update Python version requirement from `3.12` to `3.14` in `.python-version`.
- [ ] Task: Update `python = "^3.12"` to `python = "^3.14"` in `pyproject.toml`.
- [ ] Task: Update Poetry lockfile (`poetry update`) and uv lockfile (`uv lock`) to reflect the new Python 3.14 requirement.
- [ ] Task: Update `Dockerfile` to use `FROM python:3.14-slim` to reduce footprint while supporting `apt-get` system dependencies like `ffmpeg` and `libasound2-dev`.
- [ ] Task: Update `Dockerfile.test` to use `FROM python:3.14-slim`.
- [ ] Task: Update `README.md` to reflect the Python 3.14 requirement and document the current slim Docker setup.
