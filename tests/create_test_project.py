"""Script to create a test project in the database."""
import sys
import os
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database.utils import get_session_local
from src.database.models import Project

def create_test_project():
    """Create a test project in the database."""
    session_factory = get_session_local()
    session = session_factory()
    try:
        # Create a test project
        test_project = Project(
            name="Test Project",
            description="A test project for dashboard testing",
            project_type="virtual_instrument",
            base_note=60,  # Middle C
            velocity_layers=3,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        session.add(test_project)
        session.commit()
        
        print(f"Created test project with ID: {test_project.id}")
        return test_project.id
        
    except Exception as e:
        session.rollback()
        print(f"Error creating test project: {e}")
        return None
    finally:
        session.close()

if __name__ == "__main__":
    project_id = create_test_project()
    if project_id:
        print(f"\nYou can now access the dashboard at: http://localhost:5001/ui/dashboard/{project_id}")
