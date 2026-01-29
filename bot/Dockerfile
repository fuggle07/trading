# Use a slim, versioned base to avoid unrecoverable environmental errors
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies for ib_async and networking
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy pinned requirements first to leverage Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Pass Python logs directly to Cloud Logging stdout without buffering
ENV PYTHONUNBUFFERED=1

# Production-grade Gunicorn entrypoint
# - threads: Supports concurrent asyncio tasks
# - timeout: Set to 0 to let Cloud Run manage request lifetimes
CMD ["gunicorn", "--bind", ":8080", "--workers", "1", "--threads", "8", "--timeout", "0", "main:app"]

