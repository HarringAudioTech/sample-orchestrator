# Sample Orchestrator - Repository Analysis

## Overview
A Python-based audio processing application designed for managing, analyzing, and processing audio recordings and MIDI data. The application provides a web interface for project management and audio sample manipulation.

## Technical Stack

### Core Technologies
- **Language**: Python 3.12+
- **Database**: SQLite (development), PostgreSQL (production-ready)
- **Frontend**: HTML/CSS/JavaScript (basic), potential for modern frontend framework

### Main Dependencies
- **Web Framework**: Flask (>3.0.0)
- **Audio Processing**: 
  - librosa (0.10.1)
  - pydub (0.25.1)
  - numpy (>2.0.0)
  - scipy (1.11.4)
  - SoundFile (0.12.1)
  - madmom (0.17.0, optional for advanced tempo detection)
- **API**: FastAPI (0.104.1) with Pydantic (2.5.2)
- **Database**: SQLAlchemy (2.0.23) with Alembic for migrations
- **Containerization**: Docker with docker-compose

### Development Tools
- **Package Management**: Poetry
- **Linting/Formatting**: 
  - ruff (for linting and formatting)
  - black (25.1.0)
  - isort (for import sorting)
  - mypy (for type checking)
- **Testing**: 
  - pytest (8.3.5)
  - pytest-mock
  - hypothesis (for property-based testing)

## Project Structure

### Core Components
```
src/
├── api/                  # API endpoints and routes
│   └── routes.py         # API route definitions
├── core/                 # Core business logic
│   ├── audio_analyzer.py # Audio feature extraction
│   ├── audio_processor.py # Audio processing pipelines
│   ├── dspreset_generator.py # DSP preset generation
│   ├── midi_capture.py   # MIDI input handling
│   ├── project.py        # Project management
│   └── stages/           # Processing stages
├── database/             # Database models and utilities
│   └── models.py         # SQLAlchemy models
├── models/               # Data models
├── ui/                   # Web interface components
└── app.py                # Application entry point
```

### Key Data Models
- **Project**: Top-level container for recordings and samples
- **Recording**: Represents an audio file with metadata
- **Sample**: Individual audio samples extracted from recordings
- **SampleMapping**: Maps samples to MIDI notes and velocity ranges
- **MidiCaptureSession**: Tracks MIDI input sessions

## Build & Development

### Setup
```bash
# Install dependencies
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt

# Run development server
uvicorn src.app:app --reload

# Run tests
pytest
```

### Containerized Development
```bash
# Build and start containers
docker-compose up --build

# Run tests in container
docker-compose exec web pytest
```

## Features

### Audio Processing
- Audio file analysis (tempo, key, loudness)
- Sample slicing and mapping
- MIDI capture and processing
- Noise reduction and audio effects
- Support for various audio formats (WAV, MP3, etc.)

### Web Interface
- Project management
- Recording and sample browser
- Real-time audio visualization
- MIDI device configuration

## Deployment

### Containerization
- Dockerfile for building application container
- docker-compose.yml for local development
- Volume mounts for persistent data storage
- Environment-based configuration

### Configuration
- Environment variable based configuration
- Separate settings for development/production
- Audio device configuration support

## Testing Strategy
- Unit tests for core functionality
- Integration tests for API endpoints
- Mocked audio processing for CI
- Property-based testing for critical components

## Documentation
- Inline docstrings following Google style
- API documentation via docstrings
- Basic README with setup instructions
- Architecture decision records (ADRs)

## CI/CD
- GitHub Actions for automated testing
- Linting and type checking in CI
- Automated dependency updates
- Container image building and publishing

## Known Limitations
- Some audio processing features limited on ARM64 (M1/M2 Macs)
- Real-time processing performance may vary based on hardware
- Web interface currently in development
- Limited automated browser testing

## Future Development Areas
1. **Enhanced Web UI**
   - Modern frontend framework (React/Vue)
   - Real-time audio visualization
   - Drag-and-drop sample management

2. **Advanced Audio Processing**
   - More DSP effects
   - Machine learning-based audio analysis
   - Real-time audio processing

3. **Workflow Engine**
   - Custom processing pipelines
   - Batch processing capabilities
   - Visual workflow editor

4. **Sample Librarian**
   - ML-based similarity matching
   - Auto-tagging of samples
   - Advanced search capabilities

5. **Personal Style Modeling**
   - Fine-tuned models for audio description
   - Personal audio processing presets
   - Style transfer for audio samples
