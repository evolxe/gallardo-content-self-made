# Docker Deployment Guide

This guide explains how to deploy the Video Processing API using Docker.

## Prerequisites

- Docker installed on your system ([Install Docker](https://docs.docker.com/get-docker/))
- Docker Compose (usually included with Docker Desktop)

## Quick Start

### Option 1: Using Docker Compose (Recommended)

1. **Build and start the container:**
   ```bash
   docker-compose up -d
   ```

2. **View logs:**
   ```bash
   docker-compose logs -f
   ```

3. **Stop the container:**
   ```bash
   docker-compose down
   ```

### Option 2: Using Docker directly

1. **Build the Docker image:**
   ```bash
   docker build -t video-processing-api .
   ```

2. **Run the container:**
   ```bash
   docker run -d \
     --name video-processing-api \
     -p 8000:8000 \
     -v $(pwd)/temp_videos:/app/temp_videos \
     video-processing-api
   ```

3. **View logs:**
   ```bash
   docker logs -f video-processing-api
   ```

4. **Stop the container:**
   ```bash
   docker stop video-processing-api
   docker rm video-processing-api
   ```

## Accessing the API

Once the container is running, the API will be available at:

- **API Base URL:** `http://localhost:8000`
- **API Documentation:** `http://localhost:8000/docs`
- **Health Check:** `http://localhost:8000/api/v1/health`

### From Another Machine

If you want to access the API from another machine on your network:

1. **Find your machine's IP address:**
   - Windows: `ipconfig`
   - Linux/Mac: `ifconfig` or `ip addr`

2. **Update docker-compose.yml** to bind to your IP:
   ```yaml
   ports:
     - "YOUR_IP:8000:8000"  # e.g., "192.168.1.100:8000:8000"
   ```

   Or use `0.0.0.0:8000:8000` to bind to all interfaces.

3. **Access from another machine:**
   - Replace `localhost` with your machine's IP address
   - Example: `http://192.168.1.100:8000/docs`

## Production Deployment

### Using Docker Compose

1. **Update docker-compose.yml for production:**
   ```yaml
   version: '3.8'
   
   services:
     video-api:
       build:
         context: .
         dockerfile: Dockerfile
       container_name: video-processing-api
       ports:
         - "8000:8000"
       volumes:
         - ./temp_videos:/app/temp_videos
       environment:
         - PYTHONUNBUFFERED=1
       restart: always  # Changed from unless-stopped
       healthcheck:
         test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')"]
         interval: 30s
         timeout: 10s
         retries: 3
         start_period: 10s
   ```

2. **Run in detached mode:**
   ```bash
   docker-compose up -d
   ```

### Deploying to a Remote Server

1. **Copy files to server:**
   ```bash
   scp -r api/ run_api.py requirements.txt Dockerfile docker-compose.yml .dockerignore user@server:/path/to/app/
   ```

2. **SSH into server:**
   ```bash
   ssh user@server
   ```

3. **Navigate to app directory and start:**
   ```bash
   cd /path/to/app
   docker-compose up -d
   ```

4. **Set up reverse proxy (optional but recommended):**
   - Use Nginx or Traefik to handle SSL/TLS
   - Point to `localhost:8000` as the backend

## Volume Management

The `temp_videos` directory is mounted as a volume to persist processed videos. To clean up old files:

```bash
# Clean up old uploads (older than 7 days)
find temp_videos/uploads -type f -mtime +7 -delete

# Clean up old outputs (older than 30 days)
find temp_videos/output -type f -mtime +30 -delete
```

## Monitoring

### View Container Status
```bash
docker-compose ps
```

### View Logs
```bash
docker-compose logs -f video-api
```

### View Resource Usage
```bash
docker stats video-processing-api
```

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```

## Troubleshooting

### Container won't start
1. Check logs: `docker-compose logs video-api`
2. Verify port 8000 is not in use: `netstat -an | grep 8000`
3. Check Docker is running: `docker ps`

### Video processing fails
1. Check FFmpeg is installed: `docker exec video-processing-api ffmpeg -version`
2. Check available disk space: `docker exec video-processing-api df -h`
3. View detailed error logs: `docker-compose logs -f video-api`

### Permission issues
If you encounter permission issues with the temp_videos directory:
```bash
sudo chown -R $USER:$USER temp_videos
chmod -R 755 temp_videos
```

## Updating the API

1. **Pull latest code changes**
2. **Rebuild the image:**
   ```bash
   docker-compose build
   ```
3. **Restart the container:**
   ```bash
   docker-compose up -d
   ```

## Building for Different Platforms

### Build for ARM64 (Apple Silicon, Raspberry Pi)
```bash
docker buildx build --platform linux/arm64 -t video-processing-api:arm64 .
```

### Build for AMD64 (Intel/AMD)
```bash
docker buildx build --platform linux/amd64 -t video-processing-api:amd64 .
```

## Security Considerations

1. **Don't expose port 8000 directly to the internet** - Use a reverse proxy with SSL
2. **Set up firewall rules** to restrict access
3. **Regularly update dependencies** in requirements.txt
4. **Monitor disk usage** - Video processing can use significant storage
5. **Set resource limits** in docker-compose.yml:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '2'
         memory: 4G
   ```

## Next Steps

- Import the Postman collection (`Video_Processing_API.postman_collection.json`) to test the API
- Set up monitoring and logging (e.g., Prometheus, Grafana)
- Configure automated backups for processed videos
- Set up CI/CD pipeline for automated deployments

