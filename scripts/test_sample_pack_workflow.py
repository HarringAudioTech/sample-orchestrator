#!/usr/bin/env python3
"""
Test script for the SamplePackWorkflow.

This script demonstrates how to use the SamplePackWorkflow to process
an audio file and create a sample pack.
"""

import os
import sys
import logging
import argparse
from pathlib import Path

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add src directory to path
src_dir = os.path.join(project_root, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_database():
    """Set up the database for testing."""
    from sqlmodel import SQLModel, create_engine, Session
    from src.database.models import RecordingModel, ProjectModel
    
    # Use SQLite in-memory database for testing
    DATABASE_URL = "sqlite:///:memory:"
    
    # Create engine and session
    engine = create_engine(DATABASE_URL)
    
    # Create all tables
    SQLModel.metadata.create_all(engine)
    
    # Create session
    session = Session(engine)
    
    return session

def create_test_recording(session, audio_file_path):
    """Create a test recording in the database."""
    from sqlmodel import select
    from src.database.models import RecordingModel, ProjectModel
    
    # Create a test project if it doesn't exist
    statement = select(ProjectModel).where(ProjectModel.name == "Test Project")
    project = session.exec(statement).first()
    if not project:
        project = ProjectModel(
            name="Test Project",
            description="Test project for sample pack workflow",
            project_type="sample_pack"
        )
        session.add(project)
        session.commit()
        session.refresh(project)
    
    # Create a test recording
    recording = RecordingModel(
        name=os.path.basename(audio_file_path),
        file_path=str(audio_file_path),
        project_id=project.id,
        status="pending",
        duration=0.0,
        sample_rate=44100,
        channels=2,
        file_size_bytes=os.path.getsize(audio_file_path) if os.path.exists(audio_file_path) else 0
    )
    
    session.add(recording)
    session.commit()
    session.refresh(recording)
    
    return recording.id, project.id

def main():
    """Main function to test the sample pack workflow."""
    parser = argparse.ArgumentParser(description='Test the SamplePackWorkflow')
    parser.add_argument('audio_file', type=str, help='Path to the audio file to process')
    parser.add_argument('--output-dir', type=str, default='./output', 
                       help='Output directory for samples')
    args = parser.parse_args()
    
    # Validate input file
    audio_file = Path(args.audio_file)
    if not audio_file.is_file():
        logger.error(f"Audio file not found: {audio_file}")
        return 1
    
    # Set up output directory
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Set up database
    session = setup_database()
    
    try:
        # Create test recording in the database
        logger.info(f"Creating test recording for {audio_file.name}")
        recording_id, project_id = create_test_recording(session, audio_file)
        
        # Create and run the workflow
        from src.core.workflows.sample_pack_workflow import create_sample_pack_workflow
        
        logger.info("Initializing SamplePackWorkflow")
        workflow = create_sample_pack_workflow(session)
        
        # Define processing parameters
        params = {
            "onset_detection": {
                "hop_length": 512,
                "fmin": 50.0,
                "fmax": 5000.0,
                "delta": 0.2,
                "wait": 0.03
            },
            "slice_planning": {
                "min_slice_duration": 0.05,  # 50ms
                "max_slice_duration": 5.0,   # 5 seconds
                "project_type": "drum_kit"
            },
            "segment_classification": {
                "one_shot_max_duration": 2.0,  # 2 seconds
                "loop_min_duration": 0.5,      # 500ms
                "loop_max_duration": 8.0       # 8 seconds
            },
            "slicing": {
                "normalize_audio": True,
                "bit_depth": 24,
                "sample_rate": 44100,
                "default_category": "Drums"
            }
        }
        
        # Run the workflow
        logger.info(f"Starting workflow for recording {recording_id}")
        result = workflow.process_recording(
            recording_id=recording_id,
            project_id=project_id,
            output_dir=str(output_dir),
            params=params
        )
        
        logger.info(f"Workflow completed successfully: {result}")
        return 0
        
    except Exception as e:
        logger.error(f"Error running workflow: {str(e)}", exc_info=True)
        return 1
    finally:
        session.close()

if __name__ == "__main__":
    sys.exit(main())
