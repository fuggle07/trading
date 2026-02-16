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

# Install dependencies into a wheels directory or venv
COPY requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --upgrade pip && pip install -r requirements.txt


# --- STAGE 2: Runner ---
FROM python:3.12-slim AS runner

# Standard Python env vars
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Create a non-privileged user
RUN groupadd -r botuser && useradd -r -g botuser botuser

# Copy ONLY the virtual env from the builder
COPY --from=builder /opt/venv /opt/venv

# Copy app code with ownership set during the copy
COPY --chown=botuser:botuser . .

# Switch to non-root user
USER botuser

# Gunicorn for production
CMD ["gunicorn", "--bind", ":8080", "--workers", "1", "--threads", "8", "--timeout", "0", "main:app"]