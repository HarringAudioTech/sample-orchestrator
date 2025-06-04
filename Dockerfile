# Use an official Python runtime as a parent image
FROM python:3.13

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV POETRY_VERSION=1.8.3
ENV POETRY_HOME="/opt/poetry"
ENV POETRY_VENV_CREATE=false
# POETRY_VENV_CREATE=false means poetry will use the system python.
# This is generally fine for containers.
ENV PATH="$POETRY_HOME/bin:$PATH"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends libportaudio2 libportaudiocpp0 portaudio19-dev gcc curl libasound2-dev ffmpeg libsndfile1 && apt-get clean     && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Set the working directory in the container
WORKDIR /app

# Copy only files necessary for dependency installation first to leverage Docker cache
COPY pyproject.toml poetry.lock ./

# Install project dependencies (without installing the project itself yet)
# --no-root is important here so it doesn't try to build/install the local project yet
# --no-dev is also good for production images
RUN poetry install  --no-root --no-dev

# Copy the rest of the application code
COPY src/ ./src/
#COPY tests/ ./src/tests/
# Install the application itself (now that the code is present)
# This will install the 'src' package as defined in pyproject.toml
RUN poetry install

# Create the data directory - this will be mounted as a volume
# Ensure the directory exists for the application to write to.
RUN mkdir -p /app/data

# Expose the port the app runs on
EXPOSE 5000

# Define the command to run the application
# Using poetry run ensures it uses the correct environment and dependencies
CMD ["poetry", "run", "python", "-m", "src.app"]
