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

@pytest.fixture(name="engine")
def engine_fixture():
    """Provides an in-memory SQLite engine for tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)

@pytest.fixture(name="session")
def session_fixture(engine):
    """Provides a SQLModel session for tests."""
    with Session(engine) as session:
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

