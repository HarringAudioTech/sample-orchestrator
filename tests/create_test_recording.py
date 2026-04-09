import os
import sys
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import src.database.utils as db_utils
from src.database.models import ProjectModel, RecordingModel
from src.app import create_app

def create_test_recording(project_id):
    """Create a test recording in the database."""
    app = create_app()
    with app.app_context():
        db_utils.init_db()
        session = db_utils.SessionLocal()
        try:
            # Create a test recording
            recording = RecordingModel(
                project_id=project_id,
                name="drum_loop.wav",
                file_path="test_audio/drum_loop.wav",
                duration=10.0,
                sample_rate=44100,
                created_at=datetime.utcnow()
            )
            
            session.add(recording)
            session.commit()
            
            print(f"Created test recording with ID: {recording.id} for project {project_id}")
            return recording.id
            
        except Exception as e:
            session.rollback()
            print(f"Error creating test recording: {e}")
            return None
        finally:
            session.close()

if __name__ == "__main__":
    create_test_recording(1)
