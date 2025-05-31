from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from .models import Base

# Default DATABASE_URL for the main application
DATABASE_URL = "sqlite:///./database.db"
_engine = None
_SessionLocal = None


def get_engine(database_url: str = None):
    """
    Retrieves or creates a SQLAlchemy engine.

    If `database_url` is provided, a new engine is created with this URL.
    Otherwise, a global engine instance is created and reused for the default `DATABASE_URL`.
    This allows for using a different database URL for testing or specific configurations.

    Args:
        database_url (str, optional): The database URL string.
            If None, uses the global `DATABASE_URL`. Defaults to None.

    Returns:
        sqlalchemy.engine.Engine: The SQLAlchemy engine instance.
    """
    global _engine
    from flask import current_app

    # If a specific test engine instance is configured on the app, use it.
    # This ensures that during testing, the app uses the exact same engine
    # instance as the test setup code (e.g., for creating tables, clearing data).
    if current_app and current_app.config.get("TEST_ENGINE_INSTANCE"):
        return current_app.config["TEST_ENGINE_INSTANCE"]

    if database_url:
        # If a specific URL is provided, use it directly.
        return create_engine(database_url)

    if current_app and "DATABASE_URL" in current_app.config:
        # If running within a Flask app context and DATABASE_URL is configured
        # (and TEST_ENGINE_INSTANCE was not set), use DATABASE_URL from app config.
        return create_engine(current_app.config["DATABASE_URL"])

    if _engine is None:
        # Fallback to the global default engine if no specific URL or app config is found
        _engine = create_engine(DATABASE_URL)
    return _engine


def get_session_local(engine_instance=None) -> sessionmaker:
    """
    Retrieves or creates a SQLAlchemy sessionmaker.

    If `engine_instance` is provided, a new sessionmaker is created and bound to this engine.
    Otherwise, a global sessionmaker instance is created and reused, bound to the
    default engine obtained from `get_engine()`.

    Args:
        engine_instance (sqlalchemy.engine.Engine, optional): An existing SQLAlchemy engine.
            If None, the default engine is used. Defaults to None.

    Returns:
        sqlalchemy.orm.sessionmaker: The SQLAlchemy sessionmaker instance.
    """
    global _SessionLocal
    from flask import current_app

    effective_engine = engine_instance
    if not effective_engine:
        # If no specific engine instance is provided, determine the engine to use.
        # This will leverage the logic in get_engine(), including Flask app config.
        effective_engine = get_engine()

    if engine_instance:
        # If a specific engine_instance was provided, always create a new sessionmaker for it.
        # This is useful for tests or scenarios needing isolated sessions with a specific DB.
        return sessionmaker(autocommit=False, autoflush=False, bind=effective_engine)

    # For the global/default SessionLocal, reuse if already created with the same engine.
    # However, if the effective_engine is different from what _SessionLocal is bound to,
    # a new _SessionLocal needs to be created.
    # This handles the case where get_engine() might return a different engine
    # (e.g., from app.config) than the one used for the initial global _SessionLocal.
    if _SessionLocal is None or _SessionLocal.kw["bind"] != effective_engine:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=effective_engine)
    return _SessionLocal


def init_db(engine_instance=None):
    """
    Initializes the database by creating all tables defined in `models.Base`.

    This function uses the provided `engine_instance` or the default engine
    obtained from `get_engine()`. It's typically called once at application startup
    or before running tests that require a database schema.

    Args:
        engine_instance (sqlalchemy.engine.Engine, optional): An existing SQLAlchemy engine.
            If None, the default engine is used. Defaults to None.
    """
    current_engine = engine_instance or get_engine()
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"init_db: Engine URL: {current_engine.url}")
    logger.info(f"init_db: Tables known to Base.metadata before create_all: {list(Base.metadata.tables.keys())}")
    Base.metadata.create_all(bind=current_engine)
    logger.info(
        f"Database initialized with engine: {
            current_engine.url} and tables created (if they didn't exist)."
    )


def get_db(engine_instance=None) -> Session:
    """
    Provides a database session context that is managed for request handling or general use.

    This function is a generator that yields a SQLAlchemy `Session` object.
    It ensures that the session is closed after its use, typically within a `try...finally` block.
    It can use a specific `engine_instance` for the session, or the default one.

    Args:
        engine_instance (sqlalchemy.engine.Engine, optional): An existing SQLAlchemy engine
            to bind the session to. If None, the default engine is used. Defaults to None.

    Yields:
        sqlalchemy.orm.Session: A new database session.

    Example:
        ```python
        db_gen = get_db()
        db = next(db_gen)
        try:
            # Use db session
            user = db.query(User).first()
        finally:
            next(db_gen, None) # Close session
        ```
        Or, more commonly in web frameworks as a dependency:
        ```python
        # In a Flask route for example (simplified):
        # db = next(get_db())
        # try:
        #    ...
        # finally:
        #    db.close() # Or framework handles this with teardown context
        ```
    """
    current_session_local = get_session_local(engine_instance)
    db: Session = current_session_local()
    try:
        yield db
    finally:
        db.close()


# Create the global SessionLocal instance that other modules expect to import.
# This should be the session *factory* (the result of sessionmaker()).
# Initialize SessionLocal using the default engine resolution logic.
SessionLocal = get_session_local()

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
