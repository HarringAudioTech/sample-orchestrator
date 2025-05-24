"""
Database utility functions for SQLAlchemy session management and initialization.

This module provides:
- Configuration for the default database URL.
- Engine and SessionLocal instances for database interaction.
- A function `init_db` to create database tables based on models.
- A dependency `get_db` for obtaining a database session, suitable for
  use in request contexts (e.g., in API routes).
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base

# Default DATABASE_URL for the main application
DATABASE_URL = "sqlite:///./database.db"

# Module-level Engine and SessionLocal instances, initialized once.
# These replace the global _engine and _SessionLocal variables and their getters.
ENGINE = create_engine(DATABASE_URL)
SESSION_LOCAL = sessionmaker(autocommit=False, autoflush=False, bind=ENGINE)


def init_db(engine_instance=None):
    """
    Initializes the database by creating all tables defined in `models.Base`.

    Uses the provided `engine_instance` or the module-level `ENGINE`.
    Typically called once at application startup.

    Args:
        engine_instance (sqlalchemy.engine.Engine, optional): An existing SQLAlchemy engine.
            If None, the module-level `ENGINE` is used. Defaults to None.
    """
    current_engine_to_use = engine_instance or ENGINE
    Base.metadata.create_all(bind=current_engine_to_use)
    # Consider using logger instead of print for application messages
    print(
        f"Database initialized with engine: {current_engine_to_use.url} "
        "and tables created (if they didn't exist)."
    )


def get_db(engine_instance=None) -> Session: # The return type hint is Session, but it's a generator.
                                         # Correct would be Generator[Session, None, None] or Iterator[Session]
                                         # from typing import Generator, Iterator. For now, keeping Session as per original.
    """
    Provides a database session context that is managed for request handling or general use.

    This function is a generator that yields a SQLAlchemy `Session` object.
    It ensures that the session is closed after its use, typically within a `try...finally` block.
    It can use a specific `engine_instance` for the session, or the default one.

    Args:
        engine_instance (sqlalchemy.engine.Engine, optional): An existing SQLAlchemy engine.
            If provided, a new session is created bound to this engine.
            If None, a session is created using the module-level `SESSION_LOCAL`.
            Defaults to None.

    Yields:
        sqlalchemy.orm.Session: A new database session.

    Example:
        ```python
        db_context_manager = get_db()
        db_session = next(db_context_manager)
        try:
            # Use db_session for database operations
            user = db_session.query(User).first()
        finally:
            # Ensure the generator is exhausted to close the session
            next(db_context_manager, None)
        ```
    """
    if engine_instance:
        # If a specific engine is provided, create a temporary sessionmaker for it.
        temp_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine_instance)
        db: Session = temp_session_local()
    else:
        # Use the module-level sessionmaker for the default engine.
        db: Session = SESSION_LOCAL()
    
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    # This allows running this script directly to initialize the main application database.
    print("Initializing main database using module-level ENGINE...")
    init_db() # Uses the module-level ENGINE by default
    print(
        "Database initialization complete. "
        "To verify, open 'database.db' (project root) with a SQLite browser."
    )
