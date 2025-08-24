# Dockerfile (RAQM-enabled)
FROM python:3.12-slim

# Build tools + image libs + RAQM deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential pkg-config \
    libjpeg62-turbo libjpeg62-turbo-dev zlib1g zlib1g-dev \
    libfreetype6 libfreetype6-dev \
    libharfbuzz-dev libfribidi-dev libraqm-dev \
  && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY . .

# Upgrade pip and install from source so Pillow links to RAQM
RUN python -m pip install --upgrade pip \
 && pip install --no-cache-dir Flask==3.0.2 \
 && pip install --no-cache-dir --no-binary :all: Pillow==10.2.0 \
 && pip install --no-cache-dir arabic-reshaper python-bidi

EXPOSE 5123
CMD ["python", "main.py"]