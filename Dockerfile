# Use official Python runtime as base image
FROM python:3.11-slim

ARG CYGNET_VERSION=1.0.1
LABEL org.opencontainers.image.version=$CYGNET_VERSION
ENV CYGNET_VERSION=$CYGNET_VERSION

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency manifest
COPY pyproject.toml ./

# Install Poetry v1 (compatible with current lock format)
RUN pip install --no-cache-dir "poetry<2.0.0"

# Configure Poetry to not create virtual environments (we're in a container)
RUN poetry config virtualenvs.create false

# Install Python dependencies
RUN poetry install --only main --no-interaction --no-ansi

# Copy application code
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Default command (can be overridden by docker-compose service commands)
CMD ["streamlit", "run", "main_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
