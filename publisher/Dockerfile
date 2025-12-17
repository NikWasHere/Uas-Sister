# Publisher Service Dockerfile
# Build dengan Python 3.11 slim untuk ukuran minimal

FROM python:3.11-slim

# Metadata
LABEL maintainer="student@itk.ac.id"
LABEL description="Event Publisher Service dengan Duplicate Simulation"
LABEL version="1.0.0"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies (minimal)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user untuk security
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1001 -m -s /bin/bash appuser

# Set working directory
WORKDIR /app

# Copy requirements dan install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .

# Switch to non-root user
USER appuser

# Run application
CMD ["python", "main.py"]
