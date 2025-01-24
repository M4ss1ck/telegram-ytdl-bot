FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies and project
RUN pip install --no-cache-dir -e .

# Create downloads directory
RUN mkdir -p downloads

# Run as non-root user
RUN useradd -m botuser && \
    chown -R botuser:botuser /app
USER botuser

CMD ["python", "-m", "src"]
