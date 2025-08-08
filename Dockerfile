# Base Image
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    poppler-utils \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK punkt tokenizer data
RUN python -m nltk.downloader punkt

# Expose ports (Handled by docker-compose)
EXPOSE 8016
EXPOSE 8017

# Entry point defined by docker-compose commands (CMD not needed)
