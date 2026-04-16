# Stage 1: Build stage
FROM python:3.14 AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl libasound2-dev libsndfile1-dev portaudio19-dev git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /build

# Install dependencies into a temporary directory
# This allows us to copy only the site-packages to the final image
RUN --mount=type=secret,id=GH_PAT \
    export TOKEN=$(grep '^GH_PAT=' /run/secrets/GH_PAT | sed 's/^GH_PAT=//') && \
    pip install --prefix=/install \
    fastapi==0.115.0 \
    "uvicorn[standard]==0.34.0" \
    sqlmodel==0.0.16 \
    soundcard==0.4.3 \
    torch==2.11.0 \
    torchaudio==2.11.0 \
    jinja2==3.1.3 \
    python-multipart==0.0.9 \
    mido==1.3.3 \
    requests==2.32.3 \
    numpy>=2.4.4 \
    librosa>=0.11.0 \
    pedalboard>=0.9.22 \
    "amanuensis @ git+https://${TOKEN}@github.com/HarringAudioTech/amanuensis.git@v0.3" \
    "patchlab @ git+https://${TOKEN}@github.com/HarringAudioTech/patchlab.git@v0.1#subdirectory=patchlab-python"

# Stage 2: Runtime stage
FROM python:3.14-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/usr/local/lib/python3.14/site-packages

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libasound2 libportaudio2 ffmpeg libsndfile1 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy installed dependencies from the builder stage
COPY --from=builder /install /usr/local

# Set the working directory
WORKDIR /app

# Copy the application code
COPY src/ ./src/

# Create the data directory
RUN mkdir -p /app/data

# Expose the port the app runs on
EXPOSE 5001

# Define the command to run the application
CMD ["python", "-m", "src.app"]
