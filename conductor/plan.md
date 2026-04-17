# Implementation Plan: Modern Python Audio Stack Migration (2026)

## Objective
Perform a complete architectural rewrite of the Sample Orchestrator backend and audio engine. We are migrating from the legacy Flask/SQLAlchemy/PyAudio stack to a modern, high-performance "Power Trio" stack utilizing **FastAPI**, **SQLModel**, **SoundCard**, **Pedalboard**, and **PyTorch**. 

This is a **"Big Bang"** rewrite as requested, meaning the entire application will be transitioned in one major coordinated effort.

## Scope & Impact
- **Web Framework:** Replace Flask and Flask-CORS with FastAPI and Uvicorn.
- **ORM & Validation:** Replace SQLAlchemy with SQLModel for unified data modeling, eliminating redundant Pydantic models or manual serialization functions (e.g., `model_to_dict`).
- **Audio I/O:** Replace PyAudio with SoundCard for modern, cross-platform audio capture and playback without complex C-extensions.
- **Audio Processing:** Integrate Pedalboard and PyTorch for advanced DSP, neural audio, and significantly faster processing pipelines, deprecating manual Librosa/NumPy loops where applicable.
- **Impact:** The application will be temporarily non-functional during the rewrite phase. All API routes, UI templates, database schemas, and core audio logic must be updated to align with the new asynchronous, type-safe paradigms.

## Implementation Steps

### Phase 1: Environment & Dependencies
- [ ] Update `pyproject.toml` and `Dockerfile` to remove legacy dependencies (`Flask`, `pyaudio`, `sqlalchemy` direct usage).
- [ ] Add modern dependencies: `fastapi`, `uvicorn`, `sqlmodel`, `soundcard`, `torch`, `torchaudio`, and ensure `jinja2` and `python-multipart` are included for UI/Form support.
- [ ] Rebuild the Docker environment and synchronize lockfiles.

### Phase 2: Data Model Rewrite (SQLModel)
- [ ] Rewrite `src/database/models.py` to inherit from `sqlmodel.SQLModel`. 
- [ ] Convert SQLAlchemy relationships to SQLModel relationship attributes, ensuring proper type hinting (e.g., `List["RecordingModel"]`).
- [ ] Update `src/database/utils.py` to initialize the database using `sqlmodel.create_engine` and manage `sqlmodel.Session`.

### Phase 3: Core Audio Engine Rewrite
- [ ] Rewrite `src/core/audio_recorder.py` to replace `pyaudio` logic with `soundcard`. Implement async-friendly capture loops if possible.
- [ ] Update `src/core/loop_orchestrator.py` to handle the new `soundcard` interface and integrate `pedalboard` for any inline processing (e.g., applying effects during capture or playback).
- [ ] Prepare the `IntelligentSlicingStage` to eventually utilize PyTorch models for neural onset detection or source separation.

### Phase 4: API & UI Routing Rewrite (FastAPI)
- [ ] Rewrite `src/api/routes.py` using `fastapi.APIRouter`. 
  - [ ] Replace Flask request parsing (`request.get_json()`, `request.files`) with FastAPI dependency injection (`Body`, `UploadFile`, `Depends(get_db)`).
  - [ ] Utilize SQLModel classes directly as `response_model` schemas, completely removing the custom `model_to_dict` function.
- [ ] Rewrite `src/ui/routes.py` to use `fastapi.templating.Jinja2Templates`. Ensure the `request` object is passed to all template rendering calls as required by FastAPI.
- [ ] Rewrite `src/app.py` to initialize the `FastAPI` application, mount static files (`StaticFiles`), configure CORS middleware, and include the routers.

### Phase 5: Testing & Validation
- [ ] Update integration tests in `tests/` to use FastAPI's `TestClient` instead of the Flask test client.
- [ ] Perform manual end-to-end testing:
  - [ ] Verify the UI (Tailwind/DaisyUI) renders correctly via FastAPI templates.
  - [ ] Verify audio upload and processing via SoundCard/Pedalboard.
  - [ ] Verify database CRUD operations via SQLModel.

## Migration & Rollback
Given this is a "Big Bang" rewrite, rollback involves reverting the git repository to the state prior to Phase 1. Database schema changes may require a fresh `app.db` initialization in the development environment.