# Sample Orchestrator

A modern audio orchestration and sample management platform. Transform raw hardware synth and effects recording sessions into release-ready sample packs, virtual instruments, and construction kits.

Sample Orchestrator automates the tedious parts of sample creation: transient detection, musically-aware slicing, intelligent tagging, and format-ready exports.

---

## Core Features

### 🚀 Modern Audio Stack
- **Python 3.14 Support**: Leverages the latest Python features and performance improvements.
- **FastAPI Core**: High-performance asynchronous API for responsive processing and UI.
- **SQLModel Persistence**: Unified Pydantic and SQLAlchemy models for robust data integrity and developer productivity.
- **Amanuensis & Patchlab Integration**: Deep integration with specialized libraries for deterministic musical intermediate representation and advanced audio analysis.

### 🎧 Intelligent Slicing & Processing
- **Automated Onset Detection**: Precise transient detection via `librosa`.
- **Intelligent Classification**: Duration and heuristic-based segment classification into one-shots, loops, and textures.
- **Spectral Noise Reduction**: Professional-grade denoising using spectral gating.
- **Vocal Chop Perfection**: Specialized workflows for cleaning and snapping vocal fragments to zero-crossings.

### 🎹 Virtual Instrument Creation
- **Decent Sampler Export**: Generate `.dspreset` XML files ready for use in Decent Sampler.
- **MIDI Integration**: Real-time MIDI device discovery and capture sessions via `mido`.
- **Velocity Mapping**: Organize samples into velocity groups and layers for expressive instruments.

### 🏗️ Construction Kit Workflows
- **Manifest Builder**: Define target rules for your kit (e.g., "3 Bass loops in C minor").
- **Asset Fulfillment**: Automatically match generated samples against manifest requirements.
- **Dynamic Tagging**: Rich metadata support for BPM, key, and musical category.

### 🎨 Modern Web Interface
- **Tailwind CSS & DaisyUI**: A sleek, responsive design system with theme support.
- **Interactive Dashboards**: Real-time project status, recording details, and sample previews.
- **Manifest Status UI**: Visual tracking of construction kit fulfillment progress.

---

## Tech Stack

- **Backend:** Python 3.14, FastAPI, SQLModel
- **Database:** SQLite (SQLAlchemy engine)
- **Frontend:** Jinja2 Templates, Tailwind CSS, DaisyUI
- **Audio Logic:** Librosa, NumPy, Pedalboard, SoundCard, Amanuensis, Patchlab
- **Containerization:** Docker (Python 3.14-slim base)
- **Environment:** Poetry

---

## Project Structure

```
├── data/                    # Local storage (recordings, exports, SQLite DB)
├── src/
│   ├── api/                 # FastAPI REST API routes
│   ├── ui/                  # UI routes (Dashboard, Manifest, Data views)
│   ├── core/
│   │   ├── stages/          # Processing Stage implementations (Slicing, Noise Reduction)
│   │   ├── workflows/       # Stage chain definitions (Sample Pack, Audio Ingestion)
│   │   ├── amanuensis/      # Musical IR logic
│   │   └── loop_orchestrator.py
│   ├── database/            # SQLModel models & utilities
│   ├── templates/           # Modern UI templates (Tailwind + DaisyUI)
│   └── app.py               # FastAPI application entry point
├── tests/                   # Comprehensive test suite (migrated to TestClient)
├── Dockerfile               # Multi-stage Python 3.14 build
├── docker-compose.yml       # Dev/Prod orchestration
└── pyproject.toml           # Modern Python dependency management
```

---

## Quick Start

### Docker (Recommended)

Requires a `.env` file with `GH_PAT=your_github_token` for private repository access.

```bash
docker-compose up --build
```

The application will be available at `http://localhost:5001`.

### Native Installation

Requires system packages: `gcc g++ curl libasound2-dev libsndfile1-dev portaudio19-dev ffmpeg` (Debian/Ubuntu).

```bash
# Set Python 3.14
pyenv local 3.14.2

# Install dependencies
poetry install

# Run the app
poetry run python -m src.app
```

---

## Development & Testing

We use `pytest` for verification. The test suite has been fully migrated to use FastAPI's `TestClient`.

```bash
# Run all tests
poetry run pytest tests/

# Run specific integration tests
poetry run pytest tests/test_amanuensis_integration.py
```

---

## License

MIT — see [LICENSE](LICENSE) for details.
