FROM python:3.10-slim

# Install system dependencies for compiling pysam
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    zlib1g-dev \
    libbz2-dev \
    liblzma-dev \
    libcurl4-gnutls-dev \
    libssl-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000

ENV IN_SILICO_DATA_DIR=/data/download/in-silico

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
