# Use a high-performance, slim Python base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for ib_async
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Set entry point for GCP Cloud Functions
CMD ["python", "main.py"]

