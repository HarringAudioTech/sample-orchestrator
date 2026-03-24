# Sample Orchestrator

A toolset for turning raw hardware synth and effects recording sessions into release-ready sample packs and virtual instruments. Record a 15–30 minute jam, import the audio, and let the pipeline detect transients, slice it into loops and one-shots, tag everything with musical metadata, and export bundles ready for sale.

---

## Current Feature Set & Development Status

### Core Architecture — *Implemented*

| Component | Status | Description |
|---|---|---|
| **Processing Stage Interface** | Done | Abstract `AudioProcessingStage` base class with typed inputs/outputs, default params, and a stage registry (`src/core/processing_stages.py`) |
| **Stage Runner** | Done | `execute_stage_chain` validates data-type compatibility between stages and runs them sequentially (`src/core/stage_runner.py`) |
| **Workflow System** | Done | `BaseWorkflow` base class + `WORKFLOW_REGISTRY` for named, reusable stage sequences (`src/core/workflows/`) |
| **Database Layer** | Done | SQLAlchemy models for Projects, Recordings, Samples, SamplePacks, VelocityGroups, SampleMappingItems, MIDI devices, and MIDI capture sessions (`src/database/models.py`) |
| **REST API** | Done | Flask blueprint with CRUD for projects, recordings, samples, plus processing trigger endpoints (`src/api/routes.py`) |
| **Web UI** | Done | Jinja2 templates — project list, dashboard, recording import/view, sample viewer, processing form, dspreset settings, velocity layer editing (`src/templates/ui/`) |
| **Docker Environment** | Done | `Dockerfile` + `docker-compose.yml` with volume-mounted data, port mapping, and auto DB init |

### Processing Stages

| Stage | Status | Notes |
|---|---|---|
| **Onset Detection** (`onset_detection`) | Done | Wraps `librosa.onset.onset_detect` with configurable FFT, hop length, frequency range, and energy threshold |
| **Slice Planning** (`slice_planning`) | Done | Converts onset times into slice-point dicts with start/end/type. Has drum-kit (one-shot) and melodic-loop planning modes. Loop detection is placeholder-level |
| **Segment Classification** (`segment_classification`) | Done | Duration-based heuristic classification into one-shot, loop, ambient, fill, transition. Confidence scoring present but audio-content analysis is not yet implemented |
| **Slicing** (`slicing`) | Done | Loads audio via librosa, extracts slices, saves as WAV (16/24/32-bit PCM), creates `SampleModel` DB records with full metadata, auto-creates sample packs |
| **Noise Reduction** (`noise_reduction`) | Stub | Placeholder — applies 2% attenuation. No spectral gating or noise profiling implemented |
| **Decent Sampler Export** (`decent_sampler_export`) | Done | Generates `.dspreset` XML + copies samples into instrument directory structure |
| **Vocal Chop Perfection Workflow** | Partial | Separate `ProcessingStage` hierarchy for vocal chops: denoising (stub), click/pop removal (stub), silence & stab adjustment (implemented with zero-crossing snapping), metadata update (implemented). Not yet integrated into the main stage registry |

### Audio Analysis — *Partial*

| Feature | Status | Notes |
|---|---|---|
| **BPM Detection** | Done | `librosa.beat.beat_track` with half/double-time correction |
| **Key Detection** | Done | Chromagram-based pitch-class analysis with simple major/minor heuristic |
| **Loop Point Detection** | Stub | Returns full-file bounds with 0.0 confidence. Self-similarity matrix code is scaffolded but not functional |
| **Loudness / Dynamic Range** | Done | RMS-based loudness, peak-to-noise-floor dynamic range |
| **Transient Detection** | Done | Via librosa onset detection |
| **Audio Normalization** | Basic | Simple peak normalization to target LUFS; not true LUFS metering |

### MIDI Capture — *Partial*

| Feature | Status | Notes |
|---|---|---|
| **Device Discovery** | Done | Enumerates `mido` MIDI inputs and syncs to DB |
| **Capture Sessions** | Done | DB models for sessions and per-channel MIDI file storage |
| **Live Recording** | Partial | Core capture logic exists; real-time hardware integration is environment-dependent and not fully battle-tested |

### Project Management

| Feature | Status | Notes |
|---|---|---|
| **Sample Pack Projects** | Done | Create, manage, upload recordings, trigger processing, view samples |
| **Virtual Instrument Projects** | Done | MIDI key mapping, velocity groups/layers, `.dspreset` export |
| **Recording Detail View** | Done | View recording metadata, waveform info, and generated samples |
| **Processing Progress** | Basic | Status field on recordings; no real-time progress or websocket updates |

### Testing & CI

| Component | Status |
|---|---|
| pytest suite | Present — covers stage runner, noise reduction, vocal chop stages, UI routes, API sessions, file uploads, soundfile utils |
| GitHub Actions CI | Configured — Python app tests, pylint, dependency review, Docker image publish |
| Pre-commit hooks | Black + Flake8 |

---

## Roadmap: From Current State to Feature-Complete Sample Pack Toolset

The goal is a reliable end-to-end pipeline: **record → import → analyze → slice → tag → review → export → sell**. The phases below are ordered by dependency and impact.

### Phase 1 — Robust Audio Ingestion & Session Management

> *Make it trivially easy to go from a 30-minute hardware jam to organized raw material.*

- [ ] **Long-session audio import** — stream-read large files (>500 MB / 30 min @ 48 kHz/24-bit stereo) instead of loading entirely into memory. Use `soundfile` block reads or memory-mapped I/O
- [ ] **Multi-take session grouping** — allow a single "session" entity that groups multiple recordings captured in the same sitting (e.g., multiple passes through a patch)
- [ ] **Source hardware tagging** — capture and store synth/effect chain metadata at import time (manual entry + optional MIDI device auto-association)
- [ ] **Automatic silence trimming on import** — detect and strip leading/trailing silence from raw takes before any processing
- [ ] **Sample rate & bit depth standardization** — configurable project-level target format (e.g., 48 kHz / 24-bit) with automatic SRC on import using high-quality resampling (e.g., `soxr`)

### Phase 2 — Intelligent Slicing & Loop Creation

> *Go beyond simple onset detection to produce musically meaningful slices.*

- [ ] **Real noise reduction** — replace the placeholder with spectral gating (e.g., `noisereduce` library) using a noise profile captured from silent sections of the recording
- [ ] **Beat-grid–aware slicing** — snap slice points to the nearest beat/bar boundary using detected BPM, producing bar-aligned loops (1-bar, 2-bar, 4-bar, 8-bar)
- [ ] **Tempo-synced loop trimming** — auto-calculate exact sample-accurate loop lengths from detected BPM so loops are seamlessly repeatable
- [ ] **Crossfade loop points** — apply short crossfades at loop boundaries to eliminate clicks on seamless playback
- [ ] **One-shot tail handling** — detect natural decay envelopes on one-shots; option to truncate or fade-out to a consistent tail length
- [ ] **Transient-preserving fade-in/out** — apply zero-crossing–snapped micro-fades to every slice to prevent start/end clicks
- [ ] **Improved loop point detection** — implement actual self-similarity matrix analysis to find true loop regions within longer recordings
- [ ] **Manual slice editing UI** — waveform display with draggable slice markers, audition buttons, and the ability to merge/split slices in the browser

### Phase 3 — Comprehensive Metadata & Tagging

> *Every sample needs rich, accurate metadata for discoverability and DAW integration.*

- [ ] **Automatic BPM embedding** — write detected BPM into WAV metadata (BWF `bext` chunk, `ACID` chunk for loop info, and `iXML` for DAW compatibility)
- [ ] **Automatic key/scale tagging** — improve key detection accuracy (use `key-finder` or Essentia) and write results into file metadata and DB
- [ ] **Musical category auto-classification** — ML or rule-based classification of slices into categories: kick, snare, hi-hat, bass, pad, lead, FX, texture, riser, etc., using spectral features
- [ ] **WAV chunk metadata writing** — write `ACID`, `bext`, `iXML`, `smpl` (loop points + root note), and `inst` chunks for full DAW compatibility (Ableton, FL Studio, Logic, Maschine, etc.)
- [ ] **User-editable tags UI** — bulk tag editor in the web UI for manual review and correction of auto-detected metadata
- [ ] **Naming convention engine** — configurable sample naming templates (e.g., `{pack_name}_{category}_{key}_{bpm}_{index}.wav`) applied at export time

### Phase 4 — Sample Review & Quality Control

> *Ensure every sample in the pack meets release quality standards.*

- [ ] **Waveform + spectrogram preview** — render visual previews for each sample in the web UI (server-side with matplotlib or client-side with Web Audio API)
- [ ] **In-browser audio playback** — play/audition any sample directly from the UI using Web Audio API
- [ ] **Batch loudness normalization** — true integrated LUFS normalization (e.g., `pyloudnorm`) across all samples in a pack for consistent perceived volume
- [ ] **DC offset removal** — automatic DC offset correction on all exported samples
- [ ] **Clipping detection & reporting** — flag samples that contain digital clipping; optionally apply soft-clip or limiter
- [ ] **Silence/noise-only detection** — flag and auto-exclude slices that contain only noise or silence below a threshold
- [ ] **Duplicate detection** — identify near-duplicate samples within a pack using audio fingerprinting and offer merge/removal
- [ ] **Quality score** — compute a per-sample quality score based on signal-to-noise ratio, dynamic range, spectral balance, and clip-free status

### Phase 5 — Sample Pack Bundling & Export

> *Package everything for sale on Splice, Loopmasters, Bandcamp, etc.*

- [ ] **Configurable folder structure export** — generate the final pack directory tree organized by category, key, or BPM (e.g., `Loops/Bass/120bpm/`, `One-Shots/Drums/Kick/`)
- [ ] **Format conversion on export** — export as WAV (16/24/32-bit), AIFF, or FLAC with configurable sample rate
- [ ] **Pack manifest / metadata file** — generate a JSON or CSV manifest listing every sample with its full metadata (for marketplace upload or internal tracking)
- [ ] **Artwork & README bundling** — include cover art, license text, and a README in the exported pack
- [ ] **ZIP packaging** — compress the final pack into a distributable `.zip` archive
- [ ] **Marketplace-specific presets** — export templates matching the submission requirements of common marketplaces (Splice, Loopmasters, ADSR, etc.)
- [ ] **Decent Sampler instrument bundling** — extend existing `.dspreset` export to handle multi-velocity, round-robin, and loop sample mappings in a single instrument file

### Phase 6 — Performance, UX & Workflow Polish

> *Make it fast and pleasant enough for daily use.*

- [ ] **Background processing with progress** — move all audio processing to a task queue (Celery or RQ) with websocket-based real-time progress updates in the UI
- [ ] **Batch processing** — process all recordings in a session/project with a single click
- [ ] **Undo/redo for slice edits** — maintain edit history for non-destructive workflow
- [ ] **Project templates** — save and reuse processing configurations (stage chains + parameters) as named templates
- [ ] **Keyboard shortcuts** — add hotkeys for common actions in the sample review UI (next/prev sample, approve/reject, play/stop)
- [ ] **CLI interface** — headless command-line mode for scripted/automated pack creation without the web UI
- [ ] **Multi-user support** — optional user accounts and project isolation for shared studio environments

### Phase 7 — Advanced & Nice-to-Have

> *Stretch goals that would differentiate the tool.*

- [ ] **AI-assisted slicing** — use a trained model to identify musical phrases and suggest semantically meaningful slice points
- [ ] **Automatic gain staging** — analyze and normalize input recordings to optimal levels before processing
- [ ] **Reference pack comparison** — compare your pack's tonal balance, loudness distribution, and category mix against a reference commercial pack
- [ ] **Plugin format export** — beyond Decent Sampler, export to SFZ, Kontakt NKI, or Ableton Drum Rack presets
- [ ] **Hardware integration** — direct audio capture from an interface (via JACK or CoreAudio) for a true record-to-pack workflow without leaving the app
- [ ] **Stem separation** — integrate a source-separation model (e.g., Demucs) to isolate drums/bass/melody from mixed recordings before slicing

---

## Project Structure

```
├── data/                    # Data storage (uploads, generated samples, SQLite DB)
│   ├── orchestrator.db      # SQLite database
│   ├── projects/            # Per-project output directories
│   └── uploads/             # Raw uploaded recordings
├── src/
│   ├── api/                 # Flask REST API routes
│   ├── core/
│   │   ├── stages/          # AudioProcessingStage implementations
│   │   │   ├── onset_detection_stage.py
│   │   │   ├── slice_planning_stage.py
│   │   │   ├── segment_classification_stage.py
│   │   │   ├── slicing_stage.py
│   │   │   ├── noise_reduction_stage.py
│   │   │   ├── decent_sampler_export_stage.py
│   │   │   └── vocal_chop_perfection_stage.py
│   │   ├── workflows/       # Named workflow definitions
│   │   ├── audio_analysis.py       # BPM, key, loudness, loop detection
│   │   ├── audio_processor.py      # Vocal chop processor entry point
│   │   ├── dspreset_generator.py   # Decent Sampler XML generator
│   │   ├── midi_capture.py         # MIDI device discovery & capture
│   │   ├── processing_stages.py    # Stage ABC & data type constants
│   │   ├── stage_runner.py         # Stage chain executor & registry
│   │   └── vocal_chop_evaluator.py # Vocal chop quality analysis
│   ├── database/            # SQLAlchemy models & utilities
│   ├── ui/                  # UI route blueprints
│   ├── templates/           # Jinja2 HTML templates
│   └── app.py               # Flask application factory
├── tests/                   # pytest test suite
├── scripts/                 # Utility & test scripts
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml           # Poetry dependencies (Python 3.11+)
└── README.md
```

## Tech Stack

- **Language:** Python 3.11+
- **Web Framework:** Flask + Jinja2
- **Database:** SQLAlchemy + SQLite
- **Audio Processing:** librosa, soundfile, NumPy
- **MIDI:** mido
- **Packaging:** Poetry
- **Containerization:** Docker + Docker Compose
- **CI:** GitHub Actions (pytest, pylint, Docker publish)

## Quick Start

### Docker (Recommended)

```bash
docker-compose up --build
```

The app will be available at `http://localhost:8000`.

### Native

```bash
poetry install
poetry run python -m src.app
```

Requires system packages: `portaudio19-dev libasound2-dev libsndfile1 ffmpeg` (Debian/Ubuntu).

## Running Tests

```bash
# Docker
docker-compose exec app poetry run pytest

# Native
poetry run pytest
```

## License

MIT — see [LICENSE](LICENSE) for details.
