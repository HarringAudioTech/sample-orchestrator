"""Initialize the database with required tables using SQLModel."""

from src.database.utils import init_db

def init_database():
    """Initialize the database with required tables."""
    init_db()
    print("Database tables created successfully!")

if __name__ == "__main__":
    init_database()
