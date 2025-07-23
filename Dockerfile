# Use an official Python runtime as a parent image
FROM python:3.11

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl libasound2-dev ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory in the container
WORKDIR /app

# Install minimal dependencies required to run the Flask app
RUN pip install Flask==3.0.2 flask-cors==4.0.0 sqlalchemy==2.0.28 mido==1.3.2 requests==2.31.0 numpy==1.26.0 librosa==0.10.1

# Copy the application code
COPY src/ ./src/

# Create the data directory - this will be mounted as a volume
# Ensure the directory exists for the application to write to.
RUN mkdir -p /app/data

# Expose the port the app runs on
EXPOSE 5000

# Define the command to run the application
# Direct Python execution (no Poetry wrapper needed)
CMD ["python", "-m", "src.app"]
