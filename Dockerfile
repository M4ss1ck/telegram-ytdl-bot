FROM python:3.10-slim AS development

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies explicitly
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir instaloader>=4.10.0 && \
    pip install --no-cache-dir spotipy>=2.23.0

# Copy project files
COPY . .

# Install project in development mode
RUN pip install --no-cache-dir -e .

# Create downloads directory
RUN mkdir -p downloads

# Run as non-root user
RUN useradd -m botuser && \
    chown -R botuser:botuser /app
USER botuser

CMD ["python", "-m", "src"]
