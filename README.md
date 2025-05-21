# sample-orchestrator
Utility to manage sampling midi instruments and processing the resulting audio

## Project Overview

This application automates the planning, recording, post-processing, and packaging into a DecentSampler preset of the sounds contained in a MIDI controllable device. It also provides more limited functionality for recording via microphone.

## Prerequisites

Before you begin, ensure you have the following installed:

*   **Python** (version 3.12 or higher, as configured in `pyproject.toml`)
*   **Poetry**: For managing project dependencies and virtual environments. You can find installation instructions [here](https://python-poetry.org/docs/#installation).
*   **System Libraries**:
    *   `Aubio` may require `libaubio-dev` (or similar, e.g., `aubio` on macOS via Homebrew).
    *   `PyAudio` may require `portaudio19-dev` (or similar, e.g., `portaudio` on macOS via Homebrew).
    The `poetry install` command will attempt to guide you if these are missing, but pre-installing them can be smoother.

## Setup and Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd sample-orchestrator
    ```

2.  **Install dependencies using Poetry:**
    This will create a virtual environment and install all necessary packages.
    ```bash
    poetry install
    ```

## Running Tests

This project uses Pytest for running automated tests. To execute the test suite:

```bash
poetry run pytest
```

## Directory Structure

*   `src/`: Contains the main source code for the project.
*   `tests/`: Contains all the automated tests.
*   `pyproject.toml`: Defines project dependencies and metadata for Poetry.
*   `poetry.lock`: Records the exact versions of all installed dependencies.

## Contributing

Contributions are welcome! If you'd like to contribute, please:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes.
4.  Ensure tests pass (and add new ones if applicable).
5.  Submit a pull request.
