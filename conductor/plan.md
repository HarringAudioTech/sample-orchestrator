# Implementation Plan: Enhance Drum One-Shot Slicing and Classification Core

## Phase 1: High-Precision One-Shot Slicing [checkpoint: 5531259]
- [x] Task: Refine `onset_detection` parameters for drum hits.
    - [x] Adjust FFT and hop length for sharper transient detection.
    - [x] Implement zero-crossing snapping for all slice points.
- [x] Task: Implement transient-preserving micro-fades for all slices.
- [x] Task: Conductor - User Manual Verification 'High-Precision One-Shot Slicing' (Protocol in workflow.md)

## Phase 2: Enhanced Instrument Classification
- [x] Task: Expand the classification engine with initial spectral analysis.
    - [x] Implement basic spectral centroid analysis for frequency-based classification.
    - [x] Improve duration-based heuristics for different drum types.
- [x] Task: Implement a more robust tagging system for classified samples.
- [x] Task: Conductor - User Manual Verification 'Enhanced Instrument Classification' (Protocol in workflow.md)

## Phase 3: Metadata & Database Integration
- [x] Task: Ensure all slice points and classifications are correctly stored in the database.
- [ ] Task: Implement bulk export of classified samples with standardized naming.
- [ ] Task: Conductor - User Manual Verification 'Metadata & Database Integration' (Protocol in workflow.md)

---

# Construction Kits Roadmap 2026

## Objective
Add support for Construction Kits by implementing a Flexible Manifest system driven by a Dynamic Rules Builder UI, ensuring all required loops, samples, and MIDI variations are generated, tracked, and packaged.

## Key Files & Context
- `src/database/models.py`
- `src/core/manifest_evaluator.py` (New)
- `src/ui/routes.py`, `src/ui/dashboard_routes.py`
- `src/templates/projects/manifest_builder.html` (New)
- `src/templates/projects/dashboard.html`

## Proposed Solution
Implement a tag-based flexible manifest system where users define the target composition of their Construction Kit using dynamic rules (e.g., "Require 3 variations of Bass for Verse 1 in C Minor"). The backend will dynamically match generated/recorded loops to these requirements based on their metadata.

## Phased Implementation Plan

### Phase 1: Data Model Expansion
1. Add `ConstructionKitProjectModel` to `models.py` via polymorphic identity.
2. Add `ManifestModel` (belongs to project).
3. Add `ManifestRuleModel` (belongs to manifest, contains JSON rules for required tags, target counts).
4. Generate and run Alembic migrations.

### Phase 2: Core Manifest Evaluator
1. Create `src/core/manifest_evaluator.py`.
2. Implement logic to parse all `SampleModel` and `MidiFileModel` records for a project.
3. Implement matching logic to pair samples/MIDI with rules based on tags.

### Phase 3: Dynamic Rules Builder UI
1. Create frontend views/templates for creating and editing Manifest Rules.
2. Add a dynamic builder where users can specify parameters (e.g., "Add 3 Songs").

### Phase 4: Dashboard Visualization & Curation
1. Create a matrix view in the project dashboard showing rows (Instruments) and columns (Sections/Songs).
2. Display progress bars and missing elements based on the output of `ManifestEvaluator`.

### Phase 5: Amanuensis Integration & Export
1. Wire the loop generator (Amanuensis) to accept target rules from the Manifest.
2. Update the export engine to structure the final zip file logically: `Song_Name/Section_Name/Instrument_Take.wav`.