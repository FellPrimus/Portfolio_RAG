# RAGTest Application Docker Image
# Base: Python 3.11 slim (better package compatibility)
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build tools
    build-essential \
    gcc \
    g++ \
    # For playwright
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libcairo2 \
    # For konlpy (Korean NLP)
    default-jdk \
    # Utilities
    curl \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME for konlpy
ENV JAVA_HOME=/usr/lib/jvm/default-java

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Install Playwright browsers and dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation \
    fonts-dejavu-core \
    xfonts-base \
    && rm -rf /var/lib/apt/lists/* \
    && playwright install chromium

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/data/faiss_web \
    /app/data/feedback \
    /app/uploads \
    /app/html

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:5000/api/status || exit 1

# Run the application
CMD ["python", "-Bu", "app.py"]
