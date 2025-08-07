"""
Database utilities for sample-orchestrator.

This module provides database connection and session management functions.
The get_db() function is a context manager that yields a SQLAlchemy session.
"""

import contextlib
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from flask import current_app
import os

# Configure logging
logger = logging.getLogger(__name__)

# Define the SQLAlchemy base class for models
Base = declarative_base()

# Global variables for engine and session
engine = None
SessionLocal = None


@contextlib.contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager that yields a SQLAlchemy session.
    
    This function should be used with a 'with' statement to ensure
    that the session is properly closed after use.
    
    Example:
        with get_db() as db:
            # Use db session here
            project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    
    Yields:
        Session: SQLAlchemy session object
    
    Raises:
        Exception: Any exception that occurs during session use is logged and re-raised.
    """
    if SessionLocal is None:
        raise RuntimeError("Database has not been initialized. Call init_db() first.")

    db_session = SessionLocal()
    try:
        yield db_session
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        logger.error(f"Database session error: {e}", exc_info=True)
        raise
    finally:
        db_session.close()


def init_db() -> None:
    """
    Initialize the database by creating all tables.
    
    This function should be called manually or through a CLI command
    to set up the database schema. It's idempotent (safe to call multiple times).
    """
    global engine, SessionLocal

    # Get database URL from app config or environment variable
    DATABASE_URL = current_app.config.get("DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///./data/orchestrator.db"))

    # Ensure the directory exists for SQLite
    if DATABASE_URL.startswith("sqlite:///"):
        db_path = DATABASE_URL.replace("sqlite:///", "").split("?")[0]
        if db_path != ":memory:":
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Create engine with connection pool settings appropriate for Flask
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Needed for SQLite
        pool_pre_ping=True,
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",  # Enable SQL logging if SQL_ECHO=true
    )

    # Create a sessionmaker factory that will be used to create sessions
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Import models here to avoid circular imports
    from src.database.models import ProjectModel  # This will import all models due to imports in models.py
    
    # Drop all tables first to ensure a clean slate, then create them
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created or verified")