FROM python:3.11-slim

# Environment variable to ensure log outputs are unbuffered and drop immediately to terminal
ENV PYTHONUNBUFFERED=1

# Working directory
WORKDIR /app

# Install system dependencies required for compilation and ARM compatibility
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install application dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ensure persistent state database directory exists
RUN mkdir -p /app/data

# Copy core application files
COPY app.py .

# Command to run the application
CMD ["python", "app.py"]
