"""Script to list all projects in the database."""
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.database.utils import get_session_local
from src.database.models import Project

def list_projects():
    """List all projects in the database."""
    session_factory = get_session_local()
    session = session_factory()
    try:
        projects = session.query(Project).all()
        if not projects:
            print("No projects found in the database.")
            return
            
        print("\nProjects in the database:")
        print("-" * 50)
        for project in projects:
            print(f"ID: {project.id}")
            print(f"Name: {project.name}")
            print(f"Description: {project.description}")
            print(f"Created At: {project.created_at}")
            print(f"Updated At: {project.updated_at}")
            print("-" * 50)
    except Exception as e:
        print(f"Error listing projects: {e}")
    finally:
        session.close()  # Close the session

if __name__ == "__main__":
    list_projects()
