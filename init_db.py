"""Initialize the database with required tables."""

from src.app import create_app
from src.database.utils import init_db as initialize_db
from sqlalchemy import create_engine

def init_database():
    """Initialize the database with required tables."""
    app = create_app()
    with app.app_context():
        # Initialize the database (create tables)
        initialize_db()
        print("Database tables created successfully!")

if __name__ == "__main__":
    init_database()
