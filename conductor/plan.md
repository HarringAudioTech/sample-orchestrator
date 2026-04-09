# Implementation Plan: Enhance Drum One-Shot Slicing and Classification Core

## Phase 1: High-Precision One-Shot Slicing
- [x] Task: Refine `onset_detection` parameters for drum hits.
    - [x] Adjust FFT and hop length for sharper transient detection.
    - [x] Implement zero-crossing snapping for all slice points.
- [x] Task: Implement transient-preserving micro-fades for all slices.
- [~] Task: Conductor - User Manual Verification 'High-Precision One-Shot Slicing' (Protocol in workflow.md)

## Phase 2: Enhanced Instrument Classification
- [ ] Task: Expand the classification engine with initial spectral analysis.
    - [ ] Implement basic spectral centroid analysis for frequency-based classification.
    - [ ] Improve duration-based heuristics for different drum types.
- [ ] Task: Implement a more robust tagging system for classified samples.
- [ ] Task: Conductor - User Manual Verification 'Enhanced Instrument Classification' (Protocol in workflow.md)

## Phase 3: Metadata & Database Integration
- [ ] Task: Ensure all slice points and classifications are correctly stored in the database.
- [ ] Task: Implement bulk export of classified samples with standardized naming.
- [ ] Task: Conductor - User Manual Verification 'Metadata & Database Integration' (Protocol in workflow.md)
