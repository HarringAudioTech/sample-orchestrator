# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status: Database Layer Recovery Needed

⚠️ **IMPORTANT**: This codebase is currently in a transitional state. The database layer was recently removed (commit `fe561e0`) due to mixed PostgreSQL/SQLite issues, but the application code still contains many references to the removed database infrastructure. The project needs SQLite persistence layer rebuilt.

## Project Overview

This is an **Audio Processing and Sample Management API** built with Flask that provides a modular, stage-based audio processing pipeline. The core audio processing architecture is solid and functional, but the data persistence layer needs to be rebuilt.

## Core Architecture (Functional)

### Audio Processing Pipeline
The core strength of this project is its well-designed audio processing system:

- **AudioProcessingStage** (`src/core/processing_stages.py`): Abstract base class defining the interface for all audio operations
- **Stage Runner** (`src/core/stage_runner.py`): Executes chains of processing stages with type validation
- **Workflows** (`src/core/workflows.py`): Pre-defined sequences like `ExampleSlicingWorkflow`, `DecentSamplerCreationWorkflow`
- **Stage Registry**: Global discovery system for audio processing stages

### Available Processing Stages (`src/core/stages/`)
- `slicing_stage.py`: Audio onset detection and slicing
- `noise_reduction_stage.py`: Audio noise reduction  
- `decent_sampler_export_stage.py`: Export to Decent Sampler (.dspreset) format
- `vocal_chop_perfection_stage.py`: Vocal processing optimization
- `onset_detection_stage.py`: Musical onset detection
- `segment_classification_stage.py`: Audio segment classification
- `slice_planning_stage.py`: Planning and optimization for audio slicing

### Data Flow (When Database is Restored)
1. Projects created via REST API
2. Audio files uploaded to projects
3. Processing initiated via named workflows or ad-hoc stage chains
4. Generated samples and metadata stored in database and filesystem

## Current Issues (Needs Immediate Attention)

### Broken Components
These files contain references to removed database infrastructure:

- `src/core/project.py`: References non-existent `ProjectModel`, `RecordingModel`
- `src/api/routes.py`: Contains database queries for removed models
- `src/ui/routes.py` & `src/ui/dashboard_routes.py`: Database session management code
- `src/core/midi_capture.py`: Database session references
- `src/core/dspreset_generator.py`: Imports from removed `src.database.models`

### Missing Dependencies
Need to add to `pyproject.toml`:
```toml
sqlalchemy = "^2.0.0"
alembic = "^1.13.0"  # for migrations
```

## Recovery Plan for Database Layer

### Step 1: Add SQLAlchemy Dependencies
```bash
poetry add sqlalchemy alembic
```

### Step 2: Create Database Models (`src/database/models.py`)
Rebuild with these core models:
- `Project`: id, name, description, project_type, created_at, metadata
- `Recording`: id, project_id, name, file_path, created_at, metadata  
- `Sample`: id, recording_id, file_path, start_time, end_time, pitch, metadata

### Step 3: Database Configuration (`src/database/utils.py`)
- SQLite connection setup
- Session management functions
- Database initialization

### Step 4: Update Core Classes
- Fix `src/core/project.py` to use new models
- Update API routes in `src/api/routes.py`
- Fix UI routes and dashboard

### Step 5: Application Integration
- Add database initialization to `src/app.py`
- Update configuration for SQLite database path

## Development Commands

### Basic Setup
```bash
poetry install
poetry shell
```

### Testing (Once Database is Fixed)
```bash
pytest
pytest tests/core/test_stage_runner.py  # This should work now
pytest tests/core/test_vocal_chop_evaluator.py  # This should work now
```

### Code Quality
```bash
pylint src/
black src/ tests/
```

### Audio Processing Pipeline Testing
The core audio processing can be tested independently:
```python
# Test stage execution without database
from src.core.stage_runner import execute_stage_chain, STAGE_REGISTRY
from src.core.workflows import WORKFLOW_REGISTRY
```

## File System Structure

### Current Data Storage
```
data/
├── projects/           # File-based project organization
│   ├── project_1/
│   │   ├── README.md   # Basic metadata
│   │   ├── samples/
│   │   │   ├── raw/
│   │   │   ├── processed/
│   │   │   └── mapped/
│   │   ├── exports/
│   │   └── presets/
└── uploads/           # Temporary upload storage
```

### Working Components
- `src/core/processing_stages.py` ✅
- `src/core/stage_runner.py` ✅  
- `src/core/workflows.py` ✅
- `src/core/stages/*.py` ✅ (individual processing stages)
- `src/app.py` ✅ (Flask app factory)

### Broken Components (Database-Dependent)
- `src/api/routes.py` ❌
- `src/core/project.py` ❌
- `src/ui/routes.py` ❌
- Most test files with `.bak_db_removed` extensions ❌

## Architecture Strengths to Preserve

The audio processing pipeline is well-designed with:
- **Clean abstractions**: Stage interface is well-defined
- **Type safety**: Data type validation between stages
- **Extensibility**: Easy to add new processing stages
- **Composability**: Workflows can combine stages flexibly
- **Registry pattern**: Dynamic stage discovery

## Recovery Priority

1. **High Priority**: Restore database models and core persistence
2. **Medium Priority**: Fix API routes and project management  
3. **Low Priority**: Restore UI components and complex workflows

The audio processing core is valuable and shouldn't be discarded - focus recovery efforts on rebuilding clean SQLite persistence around the existing pipeline architecture.