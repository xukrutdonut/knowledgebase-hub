# Multi-stage build
FROM node:16-slim as frontend

WORKDIR /frontend

# Clone repository and build frontend
RUN apt-get update && apt-get install -y git && \
    git clone https://github.com/genomics-geek/exome_slicer.git /tmp/repo && \
    cp -r /tmp/repo/frontend/* /frontend/ && \
    yarn install && \
    yarn build

# Python stage
FROM python:3.7-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    git \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Clone repository
RUN git clone https://github.com/genomics-geek/exome_slicer.git /app

# Copy built frontend from first stage
COPY --from=frontend /frontend/build /app/frontend/build

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements/local.txt && \
    pip install gunicorn==19.9.0

# Move built files to Django templates/static
RUN mkdir -p /app/exome_slicer/templates && \
    cp /app/frontend/build/index.html /app/exome_slicer/templates/ && \
    mkdir -p /app/staticfiles && \
    cp -r /app/frontend/build/static/* /app/staticfiles/ 2>/dev/null || true

# Collect static files
RUN python manage.py collectstatic --noinput || true

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Wait for postgres\n\
echo "Waiting for postgres..."\n\
while ! nc -z $POSTGRES_HOST 5432; do\n\
  sleep 0.1\n\
done\n\
echo "PostgreSQL started"\n\
\n\
# Run migrations\n\
python manage.py migrate --noinput\n\
\n\
# Create superuser if it does not exist\n\
python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username=\"admin\").exists() or User.objects.create_superuser(\"admin\", \"admin@localhost\", \"${DJANGO_ADMIN_PASSWORD:-admin}\")" || true\n\
\n\
# Start server\n\
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
