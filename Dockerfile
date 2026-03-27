FROM python:3.12-slim-bookworm

LABEL maintainer="eriklysoe"
LABEL org.opencontainers.image.title="Converter"
LABEL org.opencontainers.image.description="File format converter supporting images, PDFs, and documents"
LABEL org.opencontainers.image.url="https://github.com/eriklysoe/converter"

# Environment defaults
ENV PUID=1000 \
    PGID=1000 \
    TZ=Europe/Oslo \
    MAX_FILE_SIZE=52428800 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app/app.py

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    inkscape \
    ghostscript \
    ffmpeg \
    dcraw \
    pandoc \
    weasyprint \
    pdftk-java \
    libreoffice \
    libreoffice-writer \
    libgl1 \
    libglib2.0-0 \
    tzdata \
    gosu \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-nor \
    poppler-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app/ ./app/

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create config and temp directories
RUN mkdir -p /config/temp

EXPOSE 7391

ENTRYPOINT ["/entrypoint.sh"]
