"""
Database utilities and session management for the Audio Processing API.

CRITICAL WARNING: This application ONLY supports SQLite as the database backend.
Previous attempts to support PostgreSQL, MySQL, or other databases resulted in
significant complexity and maintenance issues. The entire codebase has been
designed around SQLite-specific features and limitations.

SQLITE ONLY - DO NOT ADD SUPPORT FOR OTHER DATABASE ENGINES

This module provides:
- SQLite database connection and session management
- Database initialization and schema creation
- Context managers for safe database operations
- Utility functions for common database tasks
"""

import os
import logging
from contextlib import contextmanager
from typing import Optional, Generator
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from src.database.models import Base

# Configure logging
logger = logging.getLogger(__name__)

# SQLITE ONLY: Global engine and session factory
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None

# SQLITE ONLY: Default database configuration
DEFAULT_DATABASE_PATH = "data/database.db"
SQLITE_CONNECT_ARGS = {
    "check_same_thread": False,  # Allow SQLite to be used in multi-threaded Flask app
    "timeout": 30,               # Connection timeout in seconds
}


def get_database_url(database_path: Optional[str] = None) -> str:
    """
    Get the SQLite database URL.
    
    SQLITE ONLY: This function only generates SQLite URLs. Do not modify
    to support other database engines.
    
    Args:
        database_path: Path to SQLite database file. If None, uses default.
        
    Returns:
        SQLite database URL string
    """
    if database_path is None:
        database_path = DEFAULT_DATABASE_PATH
    
    # Ensure the directory exists
    db_dir = os.path.dirname(database_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
        logger.info(f"Created database directory: {db_dir}")
    
    # SQLITE ONLY: Return SQLite URL format
    return f"sqlite:///{database_path}"


def init_database(database_path: Optional[str] = None, force_recreate: bool = False) -> None:
    """
    Initialize the SQLite database and create all tables.
    
    SQLITE ONLY: This function is designed specifically for SQLite initialization.
    Do not modify to support other database engines.
    
    Args:
        database_path: Path to SQLite database file. If None, uses default.
        force_recreate: If True, drop and recreate all tables
        
    Raises:
        SQLAlchemyError: If database initialization fails
    """
    global _engine, _SessionLocal
    
    try:
        database_url = get_database_url(database_path)
        logger.info(f"Initializing SQLite database at: {database_url}")
        
        # SQLITE ONLY: Create engine with SQLite-specific configuration
        _engine = create_engine(
            database_url,
            connect_args=SQLITE_CONNECT_ARGS,
            echo=False  # Set to True for SQL query logging
        )
        
        # Create session factory
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        
        # Create all tables
        if force_recreate:
            logger.warning("Force recreating all database tables")
            Base.metadata.drop_all(bind=_engine)
        
        Base.metadata.create_all(bind=_engine)
        logger.info("Database initialization completed successfully")
        
    except SQLAlchemyError as e:
        logger.error(f"Failed to initialize SQLite database: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {e}")
        raise


def get_session_factory() -> sessionmaker:
    """
    Get the SQLite session factory.
    
    SQLITE ONLY: Returns a sessionmaker configured for SQLite.
    
    Returns:
        SQLAlchemy sessionmaker for SQLite
        
    Raises:
        RuntimeError: If database has not been initialized
    """
    if _SessionLocal is None:
        raise RuntimeError(
            "Database not initialized. Call init_database() first."
        )
    return _SessionLocal


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Context manager for SQLite database sessions.
    
    SQLITE ONLY: Provides safe session management for SQLite operations.
    Use this context manager for all database operations to ensure
    proper session cleanup and error handling.
    
    Usage:
        with get_db() as db:
            project = db.query(Project).filter(Project.id == 1).first()
            # Session is automatically committed and closed
    
    Yields:
        SQLAlchemy Session for SQLite operations
        
    Raises:
        RuntimeError: If database has not been initialized
        SQLAlchemyError: If database operation fails
    """
    SessionLocal = get_session_factory()
    db = SessionLocal()
    
    try:
        yield db
        db.commit()
        logger.debug("Database session committed successfully")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error, rolled back transaction: {e}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error, rolled back transaction: {e}")
        raise
    finally:
        db.close()
        logger.debug("Database session closed")


def get_engine() -> Engine:
    """
    Get the SQLite database engine.
    
    SQLITE ONLY: Returns the SQLite engine instance.
    
    Returns:
        SQLAlchemy Engine for SQLite
        
    Raises:
        RuntimeError: If database has not been initialized
    """
    if _engine is None:
        raise RuntimeError(
            "Database not initialized. Call init_database() first."
        )
    return _engine


def check_database_health() -> bool:
    """
    Check if the SQLite database is accessible and healthy.
    
    SQLITE ONLY: Performs basic SQLite connectivity test.
    
    Returns:
        True if database is accessible, False otherwise
    """
    try:
        with get_db() as db:
            # Simple query to test connectivity - SQLAlchemy 2.0 syntax
            db.execute(text("SELECT 1"))
            logger.info("Database health check passed")
            return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False


def reset_database(database_path: Optional[str] = None) -> None:
    """
    Reset the SQLite database by dropping and recreating all tables.
    
    SQLITE ONLY: Designed for SQLite database reset operations.
    WARNING: This will delete all data in the database.
    
    Args:
        database_path: Path to SQLite database file. If None, uses default.
    """
    logger.warning("Resetting database - ALL DATA WILL BE LOST")
    init_database(database_path=database_path, force_recreate=True)
    logger.info("Database reset completed")


# SQLITE ONLY: Module-level initialization check
def ensure_database_initialized() -> None:
    """
    Ensure the SQLite database has been initialized.
    
    SQLITE ONLY: Initializes database if not already done.
    This function is safe to call multiple times.
    """
    if _engine is None or _SessionLocal is None:
        logger.info("Database not initialized, initializing now...")
        init_database()


if __name__ == "__main__":
    """
    Command-line interface for database management.
    
    SQLITE ONLY: Provides basic SQLite database operations via CLI.
    Usage: python -m src.database.utils
    """
    import sys
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "init":
            print("Initializing SQLite database...")
            init_database()
            print("Database initialization completed.")
            
        elif command == "reset":
            print("WARNING: This will delete all data!")
            response = input("Are you sure? (yes/no): ")
            if response.lower() == "yes":
                reset_database()
                print("Database reset completed.")
            else:
                print("Reset cancelled.")
                
        elif command == "health":
            print("Checking database health...")
            if check_database_health():
                print("Database is healthy.")
            else:
                print("Database health check failed.")
                sys.exit(1)
                
        else:
            print(f"Unknown command: {command}")
            print("Available commands: init, reset, health")
            sys.exit(1)
    else:
        print("SQLite Database Utilities")
        print("Usage: python -m src.database.utils <command>")
        print("Commands:")
        print("  init   - Initialize database and create tables")
        print("  reset  - Reset database (WARNING: deletes all data)")
        print("  health - Check database connectivity")
        print()
        print("REMINDER: This application ONLY supports SQLite.")
        print("Do not attempt to use other database engines.")