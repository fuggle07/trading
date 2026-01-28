# Use the official lightweight Python image.
FROM python:3.12-slim

# Allow statements and log messages to immediately appear in the logs
ENV PYTHONUNBUFFERED True

# Set the working directory
WORKDIR /app

# Install system dependencies (needed for some bigquery/pandas operations)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy local code to the container image.
COPY requirements.txt .

# Upgrade pip
RUN pip install --root-user-action --no-cache-dir --upgrade pip
# Install dependencies
RUN pip install --root-user-action --no-cache-dir -r requirements.txt
# Install uvicorn/gunicorn for async production handling
RUN pip install --root-user-action --no-cache-dir gunicorn uvicorn

# Copy the rest of the application code
COPY . .

# Run the web service on container startup.
# We use 1 worker with the uvicorn worker class for async compatibility
CMD exec gunicorn --bind :$PORT --workers 1 --worker-class uvicorn.workers.UvicornWorker --threads 8 main:app

