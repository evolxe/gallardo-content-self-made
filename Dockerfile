# Use Python 3.11 slim as base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for video processing
RUN apt-get update && apt-get install -y nodejs npm \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Set PATH with standard binary directories
ENV PATH="/usr/bin:/usr/local/bin:/bin:${PATH}"

# Install deno (JavaScript runtime) for yt-dlp YouTube extraction
# YouTube now requires a JS runtime for proper extraction
RUN curl -fsSL https://deno.land/install.sh | sh \
    && mv /root/.deno/bin/deno /usr/local/bin/deno \
    && chmod +x /usr/local/bin/deno

# Install yt-dlp as a system binary (following Python backend pattern - subprocess calls)
RUN curl -L https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp -o /usr/local/bin/yt-dlp \
    && chmod a+rx /usr/local/bin/yt-dlp

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
# Note: opencv-python needs to be installed separately with --no-deps to avoid numpy conflicts
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir opencv-python --no-deps

# Copy application code
COPY api/ ./api/
COPY run_api.py .

# Create directories for video processing
RUN mkdir -p temp_videos/uploads \
    temp_videos/output/audio_removal \
    temp_videos/output/scene_detection \
    temp_videos/output/color_grading \
    temp_videos/output/crop_zoom \
    temp_videos/output/reencode \
    temp_videos/output/merge_audio_video \
    temp_videos/output/comprehensive \
    temp_videos/output/ytdlp_downloads

# Expose the API port
EXPOSE 8000

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PATH="/usr/bin:/usr/local/bin:/bin:${PATH}"

# Health check (using curl instead of requests to avoid extra dependency)
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1

# Run the application
CMD ["python", "run_api.py", "--host", "0.0.0.0", "--port", "8000"]

