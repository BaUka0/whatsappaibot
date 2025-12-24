FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create media directory
RUN mkdir -p media

# Expose port (for web container)
EXPOSE 8000

# Default command (uses PORT env var if set, else 8000)
CMD sh -c "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"
