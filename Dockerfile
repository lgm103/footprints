# Use a stable, slim Python base to keep the image size small
FROM python:3.11-slim

# 1. Environment variables
# PYTHONUNBUFFERED ensures logs are sent straight to the terminal (kubectl logs)
# PYTHONDONTWRITEBYTECODE prevents .pyc files from cluttering the container
# PYTHONPATH ensures Python can find your modules in the /app/src directory
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# 2. Install system dependencies
# We include gcc and python3-dev in case gevent needs to compile during install
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 3. Install Python dependencies
# Copy only the requirements first to leverage Docker's layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the application source code
# This copies your local 'src/' folder to '/app/src/' inside the container
# Path inside container: /app/src/webhook.py and /app/src/worker.py
COPY src/ /app/src/

# 5. Runtime Configuration
# Expose the port used by the Webhook (Flask)
EXPOSE 5000

# DEFAULT COMMAND: Webhook mode
# Note: In your Kubernetes 'worker.yaml', you will override this CMD
CMD ["gunicorn", "--worker-class", "gevent", "--workers", "4", "--bind", "0.0.0.0:5000", "webhook.webhook:app"]
