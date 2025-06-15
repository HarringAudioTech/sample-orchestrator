# Agent Instructions

This guide will help you interact with the audio processing and sample management API repository.

## Getting Started

- This project uses **Poetry** for dependency management. Install dependencies with `poetry install`.
- The main application is in `src/app.py` and can be run with `python -m src.app`.
- The recommended way to run the project is with Docker, using `docker-compose up --build`.

## Code Style and Conventions

- This project uses **Black** for code formatting and **Flake8** for linting.
- Before committing any code, run the pre-commit hooks to ensure your changes meet the style guidelines: `pre-commit run --all-files`.
- All new code should be fully type-hinted.

## Testing

- The test suite uses **pytest**.
- Run all tests with the `pytest` command in the root directory.
- When adding new features, please include corresponding tests in the `tests/` directory, mirroring the structure of the `src/` directory.

## Pull Requests

- Before submitting a pull request, ensure all tests are passing and the code has been linted.
- Your pull request description should clearly explain the changes you've made and why.