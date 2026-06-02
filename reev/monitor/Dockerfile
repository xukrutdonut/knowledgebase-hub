FROM python:3.12-slim

WORKDIR /app

# SSH client needed to trigger NAS update script
RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code
COPY app.py .
COPY static/ ./static/

EXPOSE 8300

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8300"]
