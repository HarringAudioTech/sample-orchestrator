# Tech Stack: Sample Orchestrator

## Core Technologies
- **Python:** The primary language for the backend, audio analysis, and DSP.
- **Flask:** The lightweight web framework for the API and UI.
- **Jinja2:** For server-side rendering of the web interface.
- **SQLAlchemy:** The ORM for managing the project's relational database.

## Audio & Music Libraries
- **Librosa:** Used for high-level audio analysis, onset detection, and BPM detection.
- **Soundfile:** For robust, low-level reading and writing of audio files (e.g., WAV).
- **Numpy:** For efficient array-based audio processing and mathematical operations.
- **Mido:** For handling MIDI device discovery and message capture.
- **PyAudio:** For real-time audio and MIDI environmental integration.

## Development & Testing
- **Pytest:** The primary testing framework for unit and integration tests.
- **Pylint & Flake8:** For maintaining code quality and adherence to style standards.
- **Black:** For automated code formatting.
- **Docker:** For consistent environment containerization and deployment.
- **GitHub Actions:** For automated CI/CD pipelines (testing and linting).
