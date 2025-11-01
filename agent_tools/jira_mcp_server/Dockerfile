# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# install OS deps if needed (git, build-essential, etc.); keep minimal
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
  && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Cloud Run sets $PORT for you. If your code listens only on a fixed port (8080),
# either set PORT env var at deploy time or change code to read os.getenv("PORT").
ENV PORT=8080

# Expose the configured port (optional for Cloud Run)
EXPOSE 8080

# Start your server file (your code calls server.run() when invoked).
CMD ["python", "server.py"]
