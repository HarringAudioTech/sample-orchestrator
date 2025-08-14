# Sample Orchestrator

## Overview

Sample Orchestrator is a comprehensive tool designed to streamline the process of converting raw audio recordings into polished virtual instruments and sample packs. It provides a suite of tools for automating repetitive processing tasks and offers lightweight project management features tailored to these specific creative workflows.

Whether you're a sound designer crafting the next iconic virtual instrument or a musician building a custom sample pack, this project helps you manage the entire lifecycle: from importing raw takes to processing, slicing, and exporting in a ready-to-use format.

The core of the processing engine is built around:
*   **Audio Processing Stages (`AudioProcessingStage`):** Individual, reusable components that perform a specific audio operation (e.g., noise reduction, slicing, format conversion).
*   **Stage Runner (`stage_runner`):** Executes a chain of these stages, passing data from one to the next.
*   **Workflows (`BaseWorkflow`):** Pre-defined sequences of stages that can be invoked by name.

## Features

*   **Project-Based Workflows:** Manage your work in two distinct project types:
    *   **Virtual Instruments:** Group recordings, process them, and map samples to MIDI notes for instrument creation.
    *   **Sample Packs:** Collect, process, and organize audio files into cohesive libraries.
*   **Web-Based UI:** A user-friendly interface for managing projects, uploading audio, triggering processing workflows, and viewing results.
*   **Extensible Audio Processing Pipeline:**
    *   Chain together processing "stages" to create custom workflows.
    *   Out-of-the-box stages for slicing, noise reduction, and more.
    *   Easily create new stages in Python to add custom logic.
*   **Virtual Instrument Export:** Automatically generate `.dspreset` files for the popular [Decent Sampler](https://www.decentsamples.com/) format, turning your samples into a playable instrument.
*   **REST API:** A comprehensive backend API for programmatic control over all features.
*   **Database Backend:** Uses SQLAlchemy with SQLite for robust data persistence.
*   **Dockerized Environment:** Comes with `docker-compose` for a one-command setup and consistent development environment.

## Web UI Overview

The application includes a web-based user interface for managing your projects and workflows without needing to use the API directly.

Key UI components include:
*   **Project Dashboard:** A central view for each project, showing its recordings and providing access to key actions.
*   **Project & Recording Management:** Create new projects, upload recordings, and view generated samples.
*   **Processing Interface:** A form-based UI to trigger processing on your recordings, select workflows, and provide parameters.
*   **Virtual Instrument Settings:** For `virtual_instrument` projects, a dedicated page to configure MIDI mapping and metadata for `.dspreset` export.

## Project Structure

```
├── data/                    # Data storage for uploads and generated samples (created automatically by app or volume mount)
│   ├── database.db          # SQLite database file (if using default Docker setup, this lives in ./data on host)
│   ├── projects/
│   └── uploads/
├── src/                     # Source code
│   ├── api/                 # Flask API routes (Blueprints)
│   ├── core/                # Core business logic
│   │   ├── stages/          # Implementations of AudioProcessingStage
│   │   ├── processing_stages.py # Defines AudioProcessingStage interface & data types
│   │   ├── stage_runner.py  # Executes chains of stages
│   │   └── workflows.py     # Defines BaseWorkflow and preset workflows
│   ├── database/            # Database models and utility functions
│   └── app.py               # Flask application factory and entry point
├── tests/                   # Unit and integration tests
│   ├── api/
│   ├── core/
│   │   └── stages/
│   ├── database/
│   └── fixtures/            # Test fixtures, e.g., dummy audio files
├── .gitignore
├── Dockerfile               # For building the Docker image
├── docker-compose.yml       # For running the application with Docker Compose
├── LICENSE
├── poetry.lock              # Poetry lock file for deterministic builds
├── pyproject.toml           # Project metadata and dependencies for Poetry
└── README.md
```

## Running with Docker (Recommended)

Docker is the recommended way to run this project for both development and production. It simplifies dependency management and ensures a consistent environment.

**Prerequisites:**
*   [Docker](https://docs.docker.com/get-docker/) installed.
*   [Docker Compose](https://docs.docker.com/compose/install/) installed (usually included with Docker Desktop).

### Getting Started with Docker

1.  **Build and start the services:**
    ```bash
    docker-compose up --build
    ```
    This single command will:
    *   Build the Docker image from the `Dockerfile`.
    *   Start the application container.
    *   Initialize the database using the `flask init-db` command.
    *   Run the Flask development server.
    *   Map port `8000` on your host to port `5001` in the container.
    *   Mount the project source code into the container for live reloading.
    *   Mount the `./data` directory to persist the database and all generated files.

2.  **Access the application:**
    Once the container is running, the web UI and API are accessible at:
    `http://localhost:8000`

### Database and Data Persistence

The application uses an SQLite database, which is stored at `./data/orchestrator.db` on your host machine. All other user-generated data (uploads, samples, instrument files) is also stored within the `./data` directory, ensuring that your work is safe even if the container is stopped or removed.

### USB MIDI and Audio Device Access

Accessing host hardware like audio interfaces and MIDI devices from within a Docker container can be complex and platform-dependent.

*   **General Linux:**
    *   **Audio:** To give the container access to your host's audio system (ALSA), you can map the sound device:
        ```bash
        # In docker run command:
        docker run --device=/dev/snd ... your-app-name

        # In docker-compose.yml:
        # services:
        #   app:
        #     devices:
        #       - "/dev/snd:/dev/snd"
        ```
    *   **USB MIDI:** For USB MIDI devices, you might need to map the specific USB device or the entire USB bus. This often requires `udev` rules on the host for correct permissions and persistent device identification.
        1.  Identify your device using `lsusb`. Example output: `Bus 001 Device 005: ID 1234:5678 Some MIDI Device`.
        2.  Map the specific device path (e.g., `/dev/bus/usb/001/005`):
            ```bash
            # In docker run command:
            docker run --device=/dev/bus/usb/001/005 ... your-app-name

            # In docker-compose.yml:
            # services:
            #   app:
            #     devices:
            #       - "/dev/bus/usb/001/005:/dev/bus/usb/001/005" # Adjust path
            ```
        Mapping the entire USB bus (`--device=/dev/bus/usb`) is possible but grants broad access and might be a security concern.

*   **macOS and Loopback:**
    *   Direct hardware access for audio/MIDI devices from Docker containers on macOS is limited by Docker Desktop's architecture.
    *   **Audio INPUT into the container:** Use an application like [Loopback by Rogue Amoeba](https://rogueamoeba.com/loopback/) on your Mac to create a virtual audio device. You can route audio from microphones or other applications into this virtual device. Then, if the application running *inside the Docker container* supports selecting its audio input device, you would configure it to use the audio input that corresponds to the virtual device fed by Loopback (this often appears as a standard system input).
    *   **Audio OUTPUT from the container:** If the application in Docker plays audio, it will typically play through Docker Desktop's audio output, which then uses your Mac's standard audio output. Loopback can be used on the host to capture this audio if needed.
    *   **MIDI on macOS:** macOS's built-in 'Audio MIDI Setup' utility allows creating virtual MIDI ports. An application inside the Docker container might be able to connect to these if it supports network MIDI (e.g., via `rtpmidi`) or if a tool on the Mac can bridge these virtual ports to a network MIDI service that Docker can access. Direct USB MIDI device pass-through is generally not straightforward.

*   **Windows:**
    *   Similar to macOS, direct hardware access can be complex. The WSL2 backend for Docker Desktop might offer some pass-through capabilities for USB devices, but setup can be involved. For audio, software solutions on the host are typically used to manage audio routing.

## Setup and Installation (Manual / Native)

**Note:** While manual setup is possible, using Docker (see 'Running with Docker' section above) is the recommended method for both development and deployment as it handles all dependencies and configurations.

This project uses [Poetry](https://python-poetry.org/) for dependency management and packaging.

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <repository-name>
    ```

2.  **Install Python dependencies using Poetry:**
    Ensure you have Poetry installed. Then run:
    ```bash
    poetry install
    ```
    This will create a virtual environment and install all necessary packages.

3.  **System Dependencies (for native audio processing):**
    If running natively and using Python libraries that interface with system audio (like `sounddevice` or `pyaudio` which might be used by stages not yet implemented), you may need to install development libraries for PortAudio and potentially others.
    For example, on Debian/Ubuntu:
    ```bash
    sudo apt-get update
    sudo apt-get install portaudio19-dev libasound2-dev libsndfile1 ffmpeg
    ```
    The `Dockerfile` installs these for the containerized environment. Always refer to the documentation of the specific Python library causing issues for accurate system dependency information if you encounter them in a native setup.

4.  **Database Initialization (Native Setup):**
    When running natively, the SQLite database (`./data/database.db`) and its tables are initialized by the application when it first starts. The `src.app` module ensures the `data` directory (and subdirectories like `uploads`, `projects`) are created if they don't exist.

    You can also initialize the database manually (e.g., for scripting or before running the app for the first time without Docker):
    ```bash
    poetry shell
    python -m src.database.utils
    ```
    This script will create `database.db` in the project root if it's not configured to be in `./data` by the environment. **Note:** The application is now configured to use `./data/database.db`. Ensure your manual initialization aligns with this or that the application correctly creates it in `./data` on first run. When using Docker with the volume mount, the database will be at `./data/database.db` on your host.

## Running the Application Natively (Alternative to Docker)

If you prefer to run the application directly on your host machine without Docker:

1.  **Ensure you have completed the manual setup steps.**
2.  **Activate the Poetry virtual environment:**
    ```bash
    poetry shell
    ```
3.  **Run the application:**
    ```bash
    python -m src.app
    ```
    The server will typically start on `http://0.0.0.0:5000/`. The application will create and use `./data/database.db` and store other data in `./data/uploads` and `./data/projects`.

## Audio Processing Pipeline

The application features a flexible audio processing pipeline built on three main concepts:

1.  **`AudioProcessingStage` Interface (`src/core/processing_stages.py`):**
    This is an abstract base class that defines the contract for any individual processing step. Each stage takes specific input data (e.g., a file path, an audio buffer), performs an operation, and produces output data. Stages define their expected input/output types and default parameters.

2.  **`stage_runner.py` (`src/core/stage_runner.py`):**
    This module contains the `STAGE_REGISTRY` where all available `AudioProcessingStage` classes are registered. The core function `execute_stage_chain` takes a list of stage definitions (name and parameters), instantiates them, validates data type compatibility between stages, and executes them sequentially.

3.  **`BaseWorkflow` (`src/core/workflows.py`):**
    This abstract base class allows for defining preset sequences of stages as a named workflow. Each workflow specifies its name, description, and a list of stage definitions with their parameters. Workflows are registered in the `WORKFLOW_REGISTRY` and can be invoked by name via the API.

This architecture allows for modular and extensible audio processing. New operations can be added as new stages, and these stages can then be combined into new or existing workflows, or used in ad-hoc chains.

### Creating Custom Stages

To add a new audio processing capability:

1.  **Create a new Python file** (e.g., `src/core/stages/my_custom_stage.py`).
2.  **Define a class** that inherits from `AudioProcessingStage` (from `src.core.processing_stages`).
3.  **Implement the required abstract properties:**
    *   `name` (str): A unique name for your stage (e.g., `"my_effect"`).
    *   `description` (str): What your stage does.
    *   `input_type` (str): Expected input data type (e.g., `DATA_TYPE_AUDIO_BUFFER_MONO`). Use constants from `src.core.processing_stages`.
    *   `output_type` (str): Produced output data type.
    *   `default_params` (dict): Default parameters for your stage.
4.  **Implement the `process` method:**
    This is where your stage's logic goes. It receives the input data, parameters, and an optional context dictionary.

**Pseudo-code Example:**
```python
# src/core/stages/my_custom_stage.py
from src.core.processing_stages import (
    AudioProcessingStage, DATA_TYPE_AUDIO_BUFFER_MONO, # ... other types
)
from src.core.stage_runner import register_stage
import numpy as np # If processing audio buffers

class MyEffectStage(AudioProcessingStage):
    @property
    def name(self) -> str: return "my_effect"
    @property
    def description(self) -> str: return "Applies a custom audio effect."
    @property
    def input_type(self) -> str: return DATA_TYPE_AUDIO_BUFFER_MONO
    @property
    def output_type(self) -> str: return DATA_TYPE_AUDIO_BUFFER_MONO
    @property
    def default_params(self) -> dict: return {"intensity": 0.5}

    def process(self, data: np.ndarray, params: dict, context: dict = None):
        intensity = params.get("intensity", self.default_params["intensity"])
        # ... your processing logic using 'data' and 'intensity' ...
        processed_data = data * intensity # Example
        return processed_data

# Register the stage so the runner can find it
register_stage(MyEffectStage)
```

5.  **Register the Stage:**
    At the end of your stage's file, call `register_stage(YourStageClass)` from `src.core.stage_runner`. This makes it available to the `execute_stage_chain` function and workflows. Ensure your stage module is imported by the application (e.g., by importing it in `src/core/stages/__init__.py` or directly in `src/api/routes.py` where processing is initiated if you want to ensure registration).

### Creating Custom Workflows

To define a reusable, named sequence of stages:

1.  **Create a new Python file** or add to `src/core/workflows.py`.
2.  **Define a class** that inherits from `BaseWorkflow` (from `src.core.workflows`).
3.  **Implement the required abstract properties:**
    *   `name` (str): A unique, human-readable name for your workflow (e.g., `"basic_vocal_cleanup"`).
    *   `description` (str): What this workflow achieves.
    *   `stages_definition` (List[Dict[str, Any]]): A list defining the sequence of stages and their parameters. Each item in the list is a dictionary:
        ```json
        {
          "stage_name": "name_of_registered_stage",
          "params": {"param1": "value1", ...} // Optional, overrides stage defaults
        }
        ```

**Pseudo-code Example:**
```python
# src/core/workflows.py (or a new file in src/core/workflows/)
from src.core.workflows import BaseWorkflow, register_workflow
from typing import List, Dict, Any

class MyCustomWorkflow(BaseWorkflow):
    @property
    def name(self) -> str: return "my_custom_pipeline"
    @property
    def description(self) -> str: return "Applies my custom effect after noise reduction."
    @property
    def stages_definition(self) -> List[Dict[str, Any]]:
        return [
            {"stage_name": "noise_reduction", "params": {"amount": 0.7}},
            {"stage_name": "my_effect", "params": {"intensity": 0.65}},
            # ... other stages ...
        ]

# Register the workflow
register_workflow(MyCustomWorkflow)
```

4.  **Register the Workflow:**
    At the end of your workflow's file (or where it's defined), call `register_workflow(YourWorkflowClass)` from `src.core.workflows`. This makes it available to be called by name via the API. Ensure your workflow module is imported by the application.

## API Usage

The REST API is the backbone of the Sample Orchestrator, allowing for programmatic control over all its features.

### Endpoints

**Projects**
*   `POST /projects`: Create a new project. Requires `name` and `project_type` ('virtual_instrument' or 'sample_pack').
*   `GET /projects`: List all projects. Can be filtered by `project_type`.
*   `GET /projects/<project_id>`: Get details for a specific project.
*   `POST /projects/<project_id>/recordings`: Upload an audio file to a project.
*   `GET /projects/<project_id>/recordings`: List all recordings within a project.

**Recordings & Processing**
*   `GET /recordings/<recording_id>`: Get details for a specific recording.
*   `POST /recordings/<recording_id>/process`: The core processing endpoint. Trigger a workflow or an ad-hoc chain of stages on a recording.
*   `GET /recordings/<recording_id>/samples`: List all samples generated from a recording.

**Samples**
*   `GET /samples/<sample_id>`: Get details for a specific sample.

### Example: Creating a Virtual Instrument

Here is a typical workflow for creating a `.dspreset` file from a recording, using `curl`.

**(Assumes the application is running and accessible at `http://localhost:8000`)**

1.  **Create a Virtual Instrument Project:**
    ```bash
    curl -X POST -H "Content-Type: application/json" \
         -d '{
               "name": "My New Piano",
               "description": "A beautifully sampled piano.",
               "project_type": "virtual_instrument"
             }' \
         http://localhost:8000/projects
    ```
    *(This will return a project object, including its new ID. Let's assume the ID is `1`)*

2.  **Upload a Recording:**
    ```bash
    curl -X POST -F "name=Piano C4" \
         -F "file=@/path/to/your/piano_c4.wav" \
         http://localhost:8000/projects/1/recordings
    ```
    *(This returns a recording object. Let's assume its ID is `1`)*

3.  **Process the Recording to Create an Instrument:**
    This step uses an ad-hoc chain to first slice the audio and then export it as a Decent Sampler instrument.
    ```bash
    curl -X POST -H "Content-Type: application/json" \
         -d '{
               "stages_chain": [
                 {
                   "stage_name": "slicing",
                   "params": { "threshold_db": -40 }
                 },
                 {
                   "stage_name": "decent_sampler_export",
                   "params": {
                     "instrument_name": "My New Piano",
                     "instrument_author": "Your Name"
                   }
                 }
               ],
               "output_dir_suffix": "piano_v1_export"
             }' \
         http://localhost:8000/recordings/1/process
    ```
    After this command completes, you will find a `.dspreset` file and its associated samples inside the project's data directory (e.g., `./data/projects/project_1/recording_1/piano_v1_export/`).

## Running Tests

The project is tested with `pytest`.

### Running Tests in Docker (Recommended)

To run the tests in the same consistent environment as the application, use Docker Compose:
```bash
docker-compose exec app poetry run pytest
```

### Running Tests Natively

1.  **Activate the virtual environment:**
    ```bash
    poetry shell
    ```
2.  **Run pytest:**
    ```bash
    pytest
    ```

## Pre-commit Hooks

This project uses pre-commit hooks to ensure code quality and consistency. The hooks automatically format the code using Black and lint it using Flake8 before each commit.

### Installation

1. Install the pre-commit framework:
   ```bash
   pip install pre-commit
   ```
   Or, if you are using Poetry:
   ```bash
   poetry add -D pre-commit
   ```
   (If you followed the project setup instructions, `pre-commit` should already be installed as a dev dependency.)

2. Install the pre-commit hooks:
   ```bash
   pre-commit install
   ```

### Usage

Once installed, the pre-commit hooks will run automatically before each commit. If Black reformats any files, you will need to stage the changes again. If Flake8 finds any errors that it cannot fix, the commit will be blocked. You will need to fix the errors manually before you can commit.

## Contributing
(Placeholder for contribution guidelines if this were an open project)

## License
This project is licensed under the MIT License - see the LICENSE file for details.
```
