# --- STAGE 1: Builder ---
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off

WORKDIR /build

# Install compilers needed for some python packages (like pandas/numpy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies into a virtual env
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Use --no-compile to save space as we don't need bytecode in the image
RUN pip install --upgrade pip && \
    pip install --no-compile -r requirements.txt


# --- STAGE 2: Runner ---
FROM python:3.12-slim AS runner

# Standard Python env vars
# PYTHONDONTWRITEBYTECODE=1 prevents .pyc creation at runtime (kept from builder)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Create a non-privileged user
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Copy ONLY the virtual env from the builder
COPY --from=builder /opt/venv /opt/venv

# Copy app code (keeping the bot/ package structure)
COPY --chown=botuser:botuser bot/ bot/

# Ensure we don't have tests in the production image if .dockerignore was missed
RUN rm -rf bot/tests/ bot/__pycache__/

# Switch to non-root user
USER botuser

# Gunicorn for production
# We run from /app, and the module is bot.main:app
CMD ["gunicorn", "--bind", ":8080", "--workers", "1", "--threads", "8", "--timeout", "0", "bot.main:app"]

