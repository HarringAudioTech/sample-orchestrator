"""
Test script for audio slicing functionality.

This script demonstrates how to use the SlicingStage to process an audio file,
extract samples, and organize them into a sample pack.
"""

import os
import sys
import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.database.models import Base, Project, Recording, Sample, SamplePack, SampleCategory, SampleType
from src.database.utils import get_engine, get_session_local, init_db
from src.core.stages.slicing_stage import SlicingStage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_database():
    """Set up the database and create tables."""
    # Create data directory if it doesn't exist
    data_dir = Path("./data")
    data_dir.mkdir(exist_ok=True)
    
    # Initialize database
    engine = get_engine()
    init_db(engine)
    
    # Create a session
    Session = get_session_local(engine)
    return Session()

def create_test_project(session, name="Test Project"):
    """Create a test project in the database."""
    project = Project(
        name=name,
        project_type="sample_pack",
        description="Test project for audio slicing"
    )
    session.add(project)
    session.commit()
    return project

def create_test_recording(session, project_id, audio_path):
    """Create a test recording in the database, removing any previous one with the same file_path."""
    file_path = os.path.abspath(audio_path)
    # Remove any previous recording with this file_path
    existing = session.query(Recording).filter_by(file_path=file_path).first()
    if existing:
        session.delete(existing)
        session.commit()
    recording = Recording(
        name=os.path.basename(audio_path),
        file_path=file_path,
        status="pending",
        project_id=project_id
    )
    session.add(recording)
    session.commit()
    return recording

def test_audio_slicing(audio_path, output_dir, min_length_ms=50, max_length_ms=10000):
    """Test the audio slicing functionality.
    
    Args:
        audio_path: Path to the audio file to process
        output_dir: Directory to save extracted samples
        min_length_ms: Minimum sample length in milliseconds
        max_length_ms: Maximum sample length in milliseconds
    """
    # Set up database session
    session = setup_database()
    
    try:
        # Create test project
        project = create_test_project(session, "Audio Slicing Test")
        
        # Create test recording
        recording = create_test_recording(session, project.id, audio_path)
        logger.info(f"Created test recording with ID: {recording.id}")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize slicing stage
        slicer = SlicingStage()
        
        # Set up processing context
        context = {
            "db_session": session,
            "recording_id": recording.id,
            "project_id": project.id,
            "output_sample_dir": output_dir,
            "sample_pack_name": f"Test Pack - {os.path.basename(audio_path)}"
        }
        
        # Configure slicing parameters
        params = {
            "output_format": "wav",
            "bit_depth": 24,
            "normalize": True,
            "normalize_lufs": -14.0,
            "detect_bpm": True,
            "detect_key": True,
            "default_category": "Test Category",
            "min_sample_length_ms": min_length_ms,
            "max_sample_length_ms": max_length_ms,
            "create_loops": True
        }
        
        # Process the audio file
        logger.info(f"Starting audio slicing for {audio_path}")
        samples = slicer.process(audio_path, params, context)
        
        # Log results
        logger.info(f"Created {len(samples)} samples:")
        for i, sample in enumerate(samples, 1):
            logger.info(
                f"{i}. {sample['name']} | "
                f"Type: {sample.get('sample_type', 'N/A')} | "
                f"BPM: {sample.get('bpm', 'N/A')} | "
                f"Key: {sample.get('key', 'N/A')} | "
                f"Duration: {sample.get('duration', 0):.2f}s"
            )
        
        return samples
        
    except Exception as e:
        logger.error(f"Error during audio slicing test: {str(e)}", exc_info=True)
        raise
    finally:
        session.close()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test audio slicing functionality')
    parser.add_argument('audio_file', help='Path to the audio file to process')
    parser.add_argument('--output-dir', default='./output_samples', 
                       help='Directory to save extracted samples')
    parser.add_argument('--min-length', type=int, default=50,
                      help='Minimum sample length in milliseconds (default: 50)')
    parser.add_argument('--max-length', type=int, default=10000,
                      help='Maximum sample length in milliseconds (default: 10000)')
    
    args = parser.parse_args()
    
    # Convert to absolute paths
    audio_path = os.path.abspath(args.audio_file)
    output_dir = os.path.abspath(args.output_dir)
    
    # Run the test with the specified parameters
    test_audio_slicing(audio_path, output_dir, args.min_length, args.max_length)
