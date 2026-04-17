#!/usr/bin/env python3
"""
Test script for the SamplePackWorkflow.

This script demonstrates how to use the SamplePackWorkflow to process
an audio file and create a sample pack.
"""

import os
import sys
import logging
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from sqlmodel import SQLModel, create_engine, Session, select
from src.database.models import RecordingModel, ProjectModel
# pylint: disable=no-name-in-module
from src.core.workflows import create_sample_pack_workflow

logger = logging.getLogger(__name__)

def setup_database():
    """Set up the database for testing."""
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
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set up database
    session = setup_database()
    
    try:
        # Define test audio file
        audio_file = project_root / "test_audio" / "drum_loop.wav"
        
        if not audio_file.exists():
            logger.error(f"Test audio file not found at {audio_file}")
            return 1
            
        # Create test recording in DB
        logger.info(f"Creating test recording for {audio_file.name}")
        recording_id, project_id = create_test_recording(session, audio_file)
        
        # Create and run the workflow
        logger.info("Initializing SamplePackWorkflow")
        workflow = create_sample_pack_workflow(session)
        
        # Define processing parameters
        params = {
            "project_id": project_id,
            "recording_id": recording_id,
            "output_format": "wav",
            "bit_depth": 24,
            "noise_reduction_amount": 0.1,
            "min_confidence": 0.5
        }
        
        # Run the workflow
        logger.info(f"Running workflow for recording ID: {recording_id}")
        result = workflow.run(
            initial_data=str(audio_file),
            initial_data_type="file_path",
            context={"db_session": session, "project_id": project_id}
        )
        
        logger.info("Workflow execution completed")
        logger.info(f"Result: {result}")
        
        # Check if samples were created
        from src.database.models import SampleModel
        statement = select(SampleModel).where(SampleModel.recording_id == recording_id)
        samples = session.exec(statement).all()
        logger.info(f"Number of samples created: {len(samples)}")
        
        for i, sample in enumerate(samples):
            logger.info(f"Sample {i+1}: {sample.name} ({sample.file_path})")
            
        logger.info("Test completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Error running workflow: {str(e)}", exc_info=True)
        return 1
    finally:
        session.close()

if __name__ == "__main__":
    sys.exit(main())
