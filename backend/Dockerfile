# Backend Dockerfile for Render/Cloud Run
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies including Playwright requirements
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    ffmpeg \
    curl \
    # Playwright dependencies for Chromium
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies (includes spaCy model from requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only for efficiency)
RUN playwright install chromium
RUN playwright install-deps chromium

# Verify Playwright installation
RUN python -c "from playwright.sync_api import sync_playwright; print('Playwright import OK')"

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_ENV=production
ENV PORT=5003
# Tell Playwright to use installed browser
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

# Expose port
EXPOSE 5003

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5003/api/health || exit 1

# Run the application with gunicorn for production
# Using gevent for async support and higher timeout for webscraper
CMD gunicorn --bind 0.0.0.0:$PORT --workers 1 --worker-class gevent --timeout 600 --graceful-timeout 30 app_v2:app
