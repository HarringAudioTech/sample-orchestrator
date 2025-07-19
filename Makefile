# Makefile for sample-orchestrator

.PHONY: all help install run test lint format clean docker-build docker-test-build scripts-generate-test-audio scripts-test-audio-slicing scripts-test-sample-pack-workflow

# Default target
all: help

# Help message
help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  help                               Show this help message."
	@echo "  install                            Install Python dependencies using Poetry."
	@echo "  run                                Run the Flask application using Docker Compose (development mode)."
	@echo "  run-local                          Run the Flask application locally using Poetry."
	@echo "  test                               Run tests using Docker Compose (test database included)."
	@echo "  test-local                         Run tests locally using Poetry."
	@echo "  lint                               Run linting checks (pylint, flake8)."
	@echo "  format                             Format code using black and autopep8."
	@echo "  clean                              Clean up build artifacts and caches."
	@echo "  docker-build                       Build the main application Docker image."
	@echo "  docker-test-build                  Build the test runner Docker image."
	@echo "  scripts-generate-test-audio        Run the generate_test_audio.py script."
	@echo "  scripts-test-audio-slicing         Run the test_audio_slicing.py.bak_db_removed script."
	@echo "  scripts-test-sample-pack-workflow  Run the test_sample_pack_workflow.py script."

# Variables
POETRY := poetry
DOCKER_COMPOSE := docker-compose
DOCKER_COMPOSE_TEST := docker-compose -f docker-compose.test.yml

# Install Python dependencies
install:
	@echo "Installing Python dependencies..."
	$(POETRY) install

# Run the Flask application using Docker Compose
run: docker-build
	@echo "Running Flask application with Docker Compose..."
	$(DOCKER_COMPOSE) up --build

# Run the Flask application locally
run-local: install
	@echo "Running Flask application locally..."
	$(POETRY) run flask run

# Run tests using Docker Compose
test: docker-test-build
	@echo "Running tests with Docker Compose..."
	$(DOCKER_COMPOSE_TEST) up --build --abort-on-container-exit

# Run tests locally
test-local: install
	@echo "Running tests locally..."
	$(POETRY) run pytest tests/ -v

# Run linting checks
lint: install
	@echo "Running linting checks..."
	$(POETRY) run pylint src/
	$(POETRY) run flake8 src/

# Format code
format: install
	@echo "Formatting code..."
	$(POETRY) run black src/
	$(POETRY) run autopep8 --in-place --recursive src/

# Clean up build artifacts and caches
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -rf .venv .venv_test
	rm -f .poetry/config.toml
	$(DOCKER_COMPOSE) down --volumes --remove-orphans
	$(DOCKER_COMPOSE_TEST) down --volumes --remove-orphans

# Build the main application Docker image
docker-build:
	@echo "Building main application Docker image..."
	$(DOCKER_COMPOSE) build

# Build the test runner Docker image
docker-test-build:
	@echo "Building test runner Docker image..."
	$(DOCKER_COMPOSE_TEST) build

# Run scripts
scripts-generate-test-audio: install
	@echo "Running generate_test_audio.py..."
	$(POETRY) run python scripts/generate_test_audio.py

scripts-test-audio-slicing: install
	@echo "Running test_audio_slicing.py.bak_db_removed..."
	$(POETRY) run python scripts/test_audio_slicing.py.bak_db_removed

scripts-test-sample-pack-workflow: install
	@echo "Running test_sample_pack_workflow.py..."
	$(POETRY) run python scripts/test_sample_pack_workflow.py
