"""
Configuration file for pytest.
This file ensures that the src directory is in the Python path when running tests.
"""
import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent.resolve()
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))

# Mock patchlab before any imports that might use it
import unittest.mock
sys.modules['patchlab'] = unittest.mock.MagicMock()

@pytest.fixture(name="engine")
def engine_fixture():
    """Provides a shared in-memory SQLite engine for tests."""
    import src.database.utils as db_utils
    # Use a shared in-memory database to allow multiple connections to see the same data
    engine = create_engine(
        "sqlite:///file:testdb?mode=memory&cache=shared",
        connect_args={"check_same_thread": False}
    )
    # Keep one connection open to keep the database alive
    connection = engine.connect()
    
    # Override the global engine in utils
    db_utils.engine = engine
    
    SQLModel.metadata.create_all(engine)
    yield engine
    
    db_utils.engine = None
    connection.close()

@pytest.fixture(name="session")
def session_fixture(engine):
    """Provides a SQLModel session for tests."""
    with Session(engine, expire_on_commit=False) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session):
    """Provides a TestClient for the FastAPI app with a database session override."""
    from src.app import app
    from src.database.utils import get_db

    def get_db_override():
        yield session

    app.dependency_overrides[get_db] = get_db_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

