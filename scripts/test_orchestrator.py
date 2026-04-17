import sys
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add src to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlmodel import SQLModel, create_engine, Session
from src.database.models import ProjectModel
from src.core.loop_orchestrator import LoopOrchestrator

def test_orchestration():
    """Test the LoopOrchestrator integration."""
    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)
    
    # Use a temporary SQLite DB for testing
    engine = create_engine("sqlite:///data/test_orchestrator.db")
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    
    with Session(engine) as db:
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

            # 3. Capture a loop with mocks for MIDI
            print("Capturing loop via orchestrator...")
            with patch("src.core.loop_orchestrator.mido.open_output"), \
                 patch("src.core.loop_orchestrator.mido.MidiFile") as mock_midi_file:
                
                mock_midi_file.return_value.play.return_value = [MagicMock()]
                
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

        except Exception as e:
            print(f"ERROR during orchestration test: {e}")
            raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_orchestration()
