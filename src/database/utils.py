from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session  # Ensure these are imported
from flask import current_app  # Ensure this is imported for get_engine
from .models import Base

# Default DATABASE_URL for the main application
DATABASE_URL = "sqlite:///./database.db"
_engine = None
# _SessionLocal = None # Removed global session factory cache


def get_engine(database_url: str = None):
    """
    Retrieves or creates a SQLAlchemy engine.
    Prioritizes TEST_ENGINE_INSTANCE from app config if in TESTING mode.
    Then checks for an explicit database_url.
    Then checks for DATABASE_URL in Flask app config.
    Finally, falls back to a global default engine.
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


def get_session_local(engine_instance=None) -> sessionmaker:
    """
    Creates a SQLAlchemy sessionmaker (a factory for sessions).

    If `engine_instance` is provided, it's used directly.
    Otherwise, `get_engine()` is called to determine the appropriate engine
    (which will correctly pick up the test engine if in a testing context).

    Args:
        engine_instance (sqlalchemy.engine.Engine, optional): An existing SQLAlchemy engine.
            If None, `get_engine()` is used. Defaults to None.

    Returns:
        sqlalchemy.orm.sessionmaker: A new sessionmaker instance bound to the determined engine.
    """
    effective_engine = engine_instance
    if not effective_engine:
        effective_engine = get_engine()

    # Always return a new sessionmaker bound to the determined engine for isolation
    return sessionmaker(autocommit=False, autoflush=False, bind=effective_engine)


def init_db(engine_instance=None):
    """
    Initializes the database by creating all tables defined in `models.Base`.
    """
    current_engine = engine_instance or get_engine()
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"init_db: Engine URL: {current_engine.url}")
    logger.info(
        f"init_db: Tables known to Base.metadata before create_all: {list(Base.metadata.tables.keys())}"
    )
    Base.metadata.create_all(bind=current_engine)
    logger.info(
        f"Database initialized with engine: {
            current_engine.url} and tables created (if they didn't exist)."
    )


def get_db(engine_instance=None) -> Session:
    """
    Provides a database session context that is managed for request handling or general use.

    This function is a generator that yields a SQLAlchemy `Session` object.
    It ensures that the session is closed after its use.

    Args:
        engine_instance (sqlalchemy.engine.Engine, optional): An existing SQLAlchemy engine
            to bind the session to. If None, the default engine resolution via
            `get_session_local` (and thus `get_engine`) is used. Defaults to None.

    Yields:
        sqlalchemy.orm.Session: A new database session.
    """
    # Create a factory using the potentially overridden engine
    current_session_local_factory = get_session_local(engine_instance)
    db: Session = current_session_local_factory()
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
