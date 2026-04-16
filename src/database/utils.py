"""
Database utilities for sample-orchestrator using SQLModel.

This module provides database connection and session management functions.
The get_db() function is a context manager that yields a SQLModel session.
"""

import contextlib
import logging
import os
from typing import Generator

from sqlmodel import SQLModel, create_engine, Session

# Configure logging
logger = logging.getLogger(__name__)

# Global variables for engine
engine = None

def get_engine():
    """Returns the SQLModel engine, initializing it if necessary."""
    global engine
    if engine is None:
        # Get database URL from environment variable or default
        DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/orchestrator.db")

        # Ensure the directory exists for SQLite
        if DATABASE_URL.startswith("sqlite:///"):
            db_path = DATABASE_URL.replace("sqlite:///", "").split("?")[0]
            if db_path != ":memory:":
                os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Create engine with connection pool settings
        engine = create_engine(
            DATABASE_URL,
            connect_args={"check_same_thread": False},  # Needed for SQLite
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",
        )
    return engine


@contextlib.contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager that yields a SQLModel session.
    
    This function should be used with a 'with' statement to ensure
    that the session is properly closed after use.
    
    Yields:
        Session: SQLModel session object
    """
    with Session(get_engine()) as session:
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database session error: {e}", exc_info=True)
            raise


def init_db() -> None:
    """
    Initialize the database by creating all tables.
    """
    # Import models here to register them with SQLModel metadata
    from src.database import models  # noqa: F401
    
    engine = get_engine()
    SQLModel.metadata.create_all(engine)
    logger.info("Database tables created or verified")
