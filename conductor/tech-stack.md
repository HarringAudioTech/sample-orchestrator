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

## External Local Libraries
- **Amanuensis:** (`../amanuensis`) Python package used for generative MIDI phrases and variations.
- **Patchlab:** (`../patchlab`) Python package bindings for synthesizer manipulation via the Patchlab Rust core.
**Development Boundary:** Both Amanuensis and Patchlab are standalone projects. Any modifications, feature requests, or bug fixes required in these libraries MUST be addressed by opening an issue on their respective GitHub issue trackers. Development within Sample Orchestrator must use them as external dependencies.

## Development & Testing
- **Pytest:** The primary testing framework for unit and integration tests.
- **Pylint & Flake8:** For maintaining code quality and adherence to style standards.
- **Black:** For automated code formatting.
- **Docker:** For consistent environment containerization and deployment.
- **GitHub Actions:** For automated CI/CD pipelines (testing and linting).
