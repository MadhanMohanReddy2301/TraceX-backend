# Dockerfile
FROM python:3.11-slim

# Avoid buffering stdout/stderr (helps logs/streaming)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . .

# expose default port (informational; Cloud Run uses $PORT env var)
EXPOSE 8080

# Set environment variable for the port (Cloud Run by default sets PORT)
ENV PORT=8080

# Use Uvicorn to run FastAPI, binding to all interfaces and using the PORT
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]

