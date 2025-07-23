"""Initialize the database with required tables."""

from src.app import create_app
from src.database.utils import init_db as initialize_db
from sqlalchemy import create_engine

def init_database():
    """Initialize the database with required tables."""
    app = create_app()
    with app.app_context():
        # Configure the database URL (using SQLite in this case)
        db_url = app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///orchestrator.db')
        engine = create_engine(db_url)
        
        # Initialize the database (create tables)
        initialize_db(engine)
        print("Database tables created successfully!")

if __name__ == "__main__":
    init_database()
