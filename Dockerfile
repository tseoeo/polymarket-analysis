# Multi-stage Dockerfile for Polymarket Analyzer
# Stage 1: Build React frontend (will be added in Phase 5)
# Stage 2: Python backend

# For now, just the backend until frontend is built
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./

# Create empty static directory (frontend will be added later)
RUN mkdir -p static

# Expose port
EXPOSE 8000

# Railway handles healthcheck via railway.toml, no need for Docker HEALTHCHECK

# Start command - use PORT env var provided by Railway (defaults to 8000)
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
