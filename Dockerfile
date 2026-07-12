FROM python:3.10-slim AS development

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-install-project

COPY . .

RUN uv sync --frozen --no-dev

RUN mkdir -p downloads sessions

RUN useradd -m botuser && \
    chown -R botuser:botuser /app
USER botuser

CMD ["/app/.venv/bin/python", "-m", "src"]
