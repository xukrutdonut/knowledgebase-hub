FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget gcc git libpq-dev \
    libbz2-dev liblzma-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencias principales (sin variant_alert — diff implementado nativamente)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/clinvar /app/logs

EXPOSE 8000

CMD ["uvicorn", "tracker.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
