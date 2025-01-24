FROM python:3.10-slim as builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

FROM python:3.10-slim

WORKDIR /app

# Copy only necessary files from builder
COPY --from=builder /root/.local /root/.local
COPY src/ ./src/
COPY setup.py .

# Install system dependencies required by yt-dlp
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Ensure Python can find the installed packages
ENV PATH=/root/.local/bin:$PATH

# Create downloads directory
RUN mkdir -p downloads

# Run as non-root user
RUN useradd -m botuser && \
    chown -R botuser:botuser /app
USER botuser

CMD ["python", "-m", "src"]
