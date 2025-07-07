from sqlalchemy import create_engine
from sqlalchemy.orm import (
    sessionmaker,
    Session as SQLAlchemySession,
)  # Renamed to avoid conflict
from sqlalchemy.engine import Engine  # For type hinting engine instances
from flask import current_app  # Ensure this is imported for get_engine
from .models import Base
from typing import Optional, Iterator

# Default DATABASE_URL for the main application
DATABASE_URL: str = "sqlite:///./data/database.db"
_engine: Optional[Engine] = None
# _SessionLocal = None # Removed global session factory cache


def get_engine(database_url: Optional[str] = None) -> Engine:
    """Retrieves or creates a SQLAlchemy engine based on a priority order.

    This function determines the appropriate SQLAlchemy engine to use by
    checking the following sources in order:
    1. If the Flask `current_app` is in "TESTING" mode and has a
       `TEST_ENGINE_INSTANCE` in its config, that engine instance is returned.
       This is primarily for testing scenarios where a pre-configured in-memory
       or test-specific database engine is used.
    2. If an explicit `database_url` argument is provided to this function,
       a new engine is created using this URL.
    3. If the Flask `current_app` is available and has a "DATABASE_URL"
       key in its config, a new engine is created using that URL. This allows
       the main application to define its database connection.
    4. If none of the above conditions are met (e.g., running in a non-Flask
       context or a script without app config), it falls back to a globally
       cached `_engine`. If this global `_engine` is not yet created, it's
       initialized using the module-level `DATABASE_URL` constant.

    Args:
        database_url (Optional[str]): An optional database URL string. If provided,
            it overrides other configurations except for a testing-specific engine.
            Defaults to None.

    Returns:
        Engine: A SQLAlchemy Engine instance configured according to the
                determined database URL or pre-existing test engine.
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


def get_session_local(
    engine_instance: Optional[Engine] = None,
) -> sessionmaker[SQLAlchemySession]:
    """Creates and returns a SQLAlchemy sessionmaker (a factory for sessions).

    This function is responsible for generating a `sessionmaker` instance,
    which is then used to create individual database `Session` objects.
    The `sessionmaker` is configured with `autocommit=False` and `autoflush=False`
    by default.

    The binding engine for the `sessionmaker` is determined as follows:
    - If an `engine_instance` is explicitly provided to this function, that
      engine is used.
    - If `engine_instance` is `None`, `get_engine()` is called. `get_engine()`
      has its own logic to determine the correct engine (e.g., using a test
      engine if in a testing context, or the application's configured engine).

    A new `sessionmaker` instance is created on each call to ensure that it is
    bound to the correct engine, especially in contexts where the engine might
    change (like testing).

    Args:
        engine_instance (Optional[Engine]): An existing SQLAlchemy engine to which
            the sessionmaker should be bound. If `None`, `get_engine()` will be
            used to resolve the engine. Defaults to None.

    Returns:
        sessionmaker[SQLAlchemySession]: A SQLAlchemy `sessionmaker` instance,
            configured and bound to the appropriate database engine. This
            factory can be called to produce new `SQLAlchemySession` objects.
    """
    effective_engine: Engine = engine_instance or get_engine()

    # Always return a new sessionmaker bound to the determined engine for isolation
    return sessionmaker(autocommit=False, autoflush=False, bind=effective_engine)


def init_db(engine_instance: Optional[Engine] = None) -> None:
    """Initializes the database by creating all defined tables.

    This function uses SQLAlchemy's metadata capabilities to issue "CREATE TABLE"
    statements to the database for all tables that are defined as subclasses of
    `src.database.models.Base` and do not already exist in the database.

    The database engine to which the tables are created is determined as follows:
    - If an `engine_instance` is explicitly provided, that engine is used.
    - If `engine_instance` is `None`, `get_engine()` is called to resolve the
      appropriate engine (which could be the application's default engine,
      a test engine, or an engine based on a specific DATABASE_URL).

    Logging is performed to indicate the engine URL being used and the tables
    known to `Base.metadata` before and after the creation process.

    Args:
        engine_instance (Optional[Engine]): An existing SQLAlchemy engine instance
            where the tables should be created. If `None`, `get_engine()` is used
            to determine the engine. Defaults to None.
    """
    current_engine: Engine = engine_instance or get_engine()
    import logging  # Keep import local to function if only used here

    logger = logging.getLogger(__name__)
    logger.info(
        f"init_db: Engine URL: {str(current_engine.url)}"
    )  # Ensure URL is string for logging
    logger.info(
        f"init_db: Tables known to Base.metadata before create_all: {list(Base.metadata.tables.keys())}"
    )
    Base.metadata.create_all(bind=current_engine)
    logger.info(
        f"Database initialized with engine: {str(current_engine.url)} and tables created (if they didn't exist)."
    )


class DBSessionContextManager:
    """Context manager and iterator for database sessions.
    
    This class supports both the context manager protocol (with statement) and
    the iterator protocol (for compatibility with existing tests that expect
    get_db() to return an iterator).
    """
    
    def __init__(self, engine_instance: Optional[Engine] = None):
        self.engine_instance = engine_instance
        self.db: Optional[SQLAlchemySession] = None
        self._iterated = False
    
    def __enter__(self) -> SQLAlchemySession:
        self.db = get_session_local(self.engine_instance)()
        return self.db
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db is not None:
            self.db.close()
    
    def __iter__(self):
        return self
    
    def __next__(self) -> SQLAlchemySession:
        if self._iterated:
            raise StopIteration
        
        if self.db is None:
            self.db = get_session_local(self.engine_instance)()
        
        self._iterated = True
        return self.db


def get_db(engine_instance: Optional[Engine] = None) -> DBSessionContextManager:
    """Provides a database session within a managed context, ensuring closure.

    This function returns a context manager that provides a SQLAlchemy `Session`
    object that can be used for database operations. The session is automatically
    closed when the context is exited, whether the operations within the context
    were successful or raised an exception.

    The session is created using a `sessionmaker` that is bound to an engine
    determined as follows:
    - If `engine_instance` is provided, the sessionmaker (and thus the session)
      is bound to this specific engine.
    - If `engine_instance` is `None`, `get_session_local()` is called without an
      explicit engine. `get_session_local()` will then use `get_engine()` to
      resolve the appropriate engine (e.g., application default, test engine).

    This pattern is essential for proper session management, preventing session
    leaks and ensuring that database connections are returned to the pool.

    Args:
        engine_instance (Optional[Engine]): An existing SQLAlchemy engine to which
            the session should be bound. If `None`, the engine is resolved via
            `get_session_local()` (ultimately by `get_engine()`). Defaults to None.

    Returns:
        DBSessionContextManager: A context manager that provides a database session.
    """
    return DBSessionContextManager(engine_instance)


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
