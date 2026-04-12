# Specification: Monophonic and Polyphonic Loop Generation Integration

## Overview
This track introduces foundational support for loop generation, moving Sample Orchestrator beyond drum one-shots. It integrates the external `amanuensis` and `patchlab` libraries to generate single-track monophonic and polyphonic MIDI loops, manipulate synthesizers, and render the resulting audio.

## Goals
- **MIDI Generation:** Use `amanuensis` to programmatically generate monophonic (bass, lead) and polyphonic (chords) MIDI lines with variations.
- **Synthesizer Manipulation:** Use `patchlab` to load patches and render audio from the generated MIDI.
- **Coordinated Output:** Export organized sample packs containing both the rendered audio loops and the original MIDI files.
- **Strict Boundary Enforcement:** Any necessary changes to `amanuensis` or `patchlab` MUST be handled via their respective GitHub issue trackers.

## Success Criteria
- **Loop Fidelity:** Clear, well-rendered monophonic and polyphonic loops accurately reflecting the generated MIDI.
- **Dependency Reliability:** Successful local integration of `amanuensis` and `patchlab` as Python dependencies.
- **Pipeline Completion:** A full end-to-end run from MIDI generation to synth rendering to structured file export.