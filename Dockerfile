# Slim base — keeps the image well under the 1GB hard limit, no GPU.
FROM python:3.12-slim

WORKDIR /app

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code.
COPY app ./app

# Document the port; deployment must bind 0.0.0.0.
EXPOSE 8000

# Secrets are passed via environment variables at runtime, never baked in.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
