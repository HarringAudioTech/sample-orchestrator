# Stage 1: Build stage
FROM python:3.14 AS builder

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl libasound2-dev libsndfile1-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /build

# Install dependencies into a temporary directory
# This allows us to copy only the site-packages to the final image
RUN pip install --prefix=/install \
    Flask==3.0.2 \
    flask-cors==4.0.0 \
    sqlalchemy==2.0.28 \
    mido==1.3.2 \
    requests==2.32.3 \
    numpy>=2.0.0 \
    librosa>=0.10.1 \
    pedalboard>=0.9.22

# Stage 2: Runtime stage
FROM python:3.14-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/usr/local/lib/python3.14/site-packages

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libasound2 ffmpeg libsndfile1 \
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
EXPOSE 5000

# Define the command to run the application
CMD ["python", "-m", "src.app"]
