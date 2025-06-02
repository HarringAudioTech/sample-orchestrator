from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLAlchemySession # Renamed to avoid conflict
from sqlalchemy.engine import Engine # For type hinting engine instances
from flask import current_app  # Ensure this is imported for get_engine
from .models import Base
from typing import Optional, Iterator

# Default DATABASE_URL for the main application
DATABASE_URL: str = "sqlite:///./database.db"
_engine: Optional[Engine] = None
# _SessionLocal = None # Removed global session factory cache


def get_engine(database_url: Optional[str] = None) -> Engine:
    """Retrieves or creates a SQLAlchemy engine.

    Prioritizes TEST_ENGINE_INSTANCE from app config if in TESTING mode.
    Then checks for an explicit database_url.
    Then checks for DATABASE_URL in Flask app config.
    Finally, falls back to a global default engine.

    Args:
        database_url: An optional database URL string.

    Returns:
        A SQLAlchemy Engine instance.
    """
    global _engine

    # Priority 1: Test engine instance if app is in TESTING mode
    if (
        current_app
        and current_app.config.get("TESTING")
        and current_app.config.get("TEST_ENGINE_INSTANCE")
    ):
        return current_app.config["TEST_ENGINE_INSTANCE"]

    # Priority 2: Explicit database_url argument
    if database_url:
        return create_engine(database_url)

    # Priority 3: DATABASE_URL from Flask app config (if not testing or test engine not set)
    if current_app and "DATABASE_URL" in current_app.config:
        return create_engine(current_app.config["DATABASE_URL"])

    # Priority 4: Global default engine (for scripts or non-app contexts)
    if _engine is None:
        _engine = create_engine(DATABASE_URL)
    return _engine


def get_session_local(engine_instance: Optional[Engine] = None) -> sessionmaker[SQLAlchemySession]:
    """Creates a SQLAlchemy sessionmaker (a factory for sessions).

    If `engine_instance` is provided, it's used directly.
    Otherwise, `get_engine()` is called to determine the appropriate engine
    (which will correctly pick up the test engine if in a testing context).

    Args:
        engine_instance: An existing SQLAlchemy engine.
            If None, `get_engine()` is used. Defaults to None.

    Returns:
        A new sessionmaker instance bound to the determined engine.
    """
    effective_engine: Engine = engine_instance or get_engine()

    # Always return a new sessionmaker bound to the determined engine for isolation
    return sessionmaker(autocommit=False, autoflush=False, bind=effective_engine)


def init_db(engine_instance: Optional[Engine] = None) -> None:
    """Initializes the database by creating all tables defined in `models.Base`.

    Args:
        engine_instance: An optional SQLAlchemy engine instance. If not provided,
                         `get_engine()` will be used to get or create one.
    """
    current_engine: Engine = engine_instance or get_engine()
    import logging # Keep import local to function if only used here

    logger = logging.getLogger(__name__)
    logger.info(f"init_db: Engine URL: {str(current_engine.url)}") # Ensure URL is string for logging
    logger.info(
        f"init_db: Tables known to Base.metadata before create_all: {list(Base.metadata.tables.keys())}"
    )
    Base.metadata.create_all(bind=current_engine)
    logger.info(
        f"Database initialized with engine: {str(current_engine.url)} and tables created (if they didn't exist)."
    )


def get_db(engine_instance: Optional[Engine] = None) -> Iterator[SQLAlchemySession]:
    """Provides a database session context that is managed for request handling or general use.

    This function is a generator that yields a SQLAlchemy `Session` object.
    It ensures that the session is closed after its use.

    Args:
        engine_instance: An existing SQLAlchemy engine
            to bind the session to. If None, the default engine resolution via
            `get_session_local` (and thus `get_engine`) is used. Defaults to None.

    Yields:
        A new database session.
    """
    # Create a factory using the potentially overridden engine
    current_session_local_factory: sessionmaker[SQLAlchemySession] = get_session_local(engine_instance)
    db: SQLAlchemySession = current_session_local_factory()
    try:
        yield db
    finally:
        db.close()


# SessionLocal = get_session_local() # Removed global SessionLocal instance

if __name__ == "__main__":
    # --------------------------------------------------------------------------
    # Script for Manual Database Initialization
    # --------------------------------------------------------------------------
    # This allows running this script directly (e.g., `python -m src.database.utils`)
    # to initialize the main application database.
    # Useful for initial setup, manual database recreation, or in environments
    # where the application itself doesn't handle DB creation.
    # --------------------------------------------------------------------------
    print("Initializing main database...")
    init_db()  # Uses default engine from get_engine()
    print("To verify, you can use a SQLite browser to open 'database.db' in the project root.")
