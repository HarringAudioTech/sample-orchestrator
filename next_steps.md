1. Install missing test dependencies (pytest-mock for the mocker fixture)
  2. Create new API test files to replace the removed ones:
    - tests/api/test_project_routes.py
    - tests/api/test_recording_routes.py
    - tests/api/test_sample_routes.py
  3. Set up test database fixtures with SQLite test database
  4. Write comprehensive tests covering:
    - Happy path scenarios for each endpoint
    - Error handling and validation
    - Database operations and relationships
    - File upload functionality
    - Audio processing integration