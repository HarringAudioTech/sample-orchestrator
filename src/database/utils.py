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
    if database_url:
        return create_engine(database_url)
    if _engine is None:
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
    if engine_instance:
        return sessionmaker(autocommit=False, autoflush=False, bind=engine_instance)
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
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
    Base.metadata.create_all(bind=current_engine)
    print(f"Database initialized with engine: {current_engine.url} and tables created (if they didn't exist).")

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

if __name__ == "__main__":
    # This allows running this script directly to initialize the main application database.
    # Useful for initial setup or manual database recreation.
    print("Initializing main database...")
    init_db() # Uses default engine from get_engine()
    print("To verify, you can use a SQLite browser to open 'database.db' in the project root.")
