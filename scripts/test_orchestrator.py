import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.database.models import Base, ProjectModel
from src.core.loop_orchestrator import LoopOrchestrator

@patch("src.core.audio_recorder.pyaudio.PyAudio")
@patch("src.core.loop_orchestrator.mido.open_output")
@patch("src.core.loop_orchestrator.mido.MidiFile")
def test_orchestration(mock_midi_file, mock_mido_open, mock_pyaudio):
    # Setup mocks
    mock_midi_file.return_value.play.return_value = [MagicMock()]
    mock_pyaudio.return_value.get_host_api_info_by_index.return_value = {'deviceCount': 0}
    
    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)
    
    # Use a temporary SQLite DB for testing
    engine = create_engine("sqlite:///data/test_orchestrator.db")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        # 1. Create a dummy project
        project = ProjectModel(name="Orchestrator Test", project_type="sample_pack")
        db.add(project)
        db.commit()
        print(f"Created test project with ID: {project.id}")

        # 2. Initialize LoopOrchestrator
        orchestrator = LoopOrchestrator(db)
        
        # Mock the recorder to avoid real hardware access and file saving issues
        orchestrator.recorder.start_recording = MagicMock()
        def mock_stop(path):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).touch()
            return Path(path)
        orchestrator.recorder.stop_recording = MagicMock(side_effect=mock_stop)

        # 3. Capture a loop
        print("Capturing loop via orchestrator...")
        result = orchestrator.capture_single_loop(
            project_id=project.id,
            label="orch_test_loop",
            engine_id="bass",
            midi_port="Mock Port",
            bars=1,
            seed=505,
            max_tweak_passes=0,
            min_loop_fitness=0.1
        )
        print(f"Orchestration result: {result}")

        # 4. Verify
        if Path(result["audio_file"]).exists():
            print(f"SUCCESS: Mock audio file created at {result['audio_file']}")
        else:
            print(f"FAILURE: Mock audio file NOT found at {result['audio_file']}")

    finally:
        db.close()

if __name__ == "__main__":
    test_orchestration()
