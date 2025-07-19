# Use an official Python runtime as a parent image
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VENV_CREATE=false \
    PATH="$POETRY_HOME/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libasound2-dev \
    libportaudio2 \
    libportaudiocpp0 \
    portaudio19-dev \
    gcc \
    g++ \
    make \
    curl \
    ffmpeg \
    libsndfile1 \
    pkg-config \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
ENV POETRY_HOME="/opt/poetry"
ENV PATH="${POETRY_HOME}/bin:${PATH}"
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && poetry --version \
    && poetry config virtualenvs.create false

# Set the working directory in the container
WORKDIR /app

# Set working directory
WORKDIR /app

# Copy only the dependency files first to leverage Docker cache
COPY pyproject.toml poetry.lock ./

# Install project dependencies directly with pip to ensure they're in the system Python path
RUN pip install flask flask-cors sqlalchemy alembic librosa mido pyaudio numpy requests

# Copy the rest of the application code
COPY src/ ./src/

# Create the data directory
RUN mkdir -p /app/data

# Set the working directory to the app directory
WORKDIR /app

# Add the app directory to PYTHONPATH
ENV PYTHONPATH="/app:${PYTHONPATH}"

# Expose the port the app runs on
EXPOSE 5001

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/health || exit 1

# Define the command to run the application
CMD ["python", "-m", "src.app"]
