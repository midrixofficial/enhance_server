# FastAPI RunPod Gateway (Direct VPS Deployment)

A production-ready FastAPI backend that acts as an intermediary between a Flutter app and a RunPod Serverless endpoint, designed to run natively on an Ubuntu VPS without Docker or Redis.

## Features

- **No Docker / No Redis**: Native execution using Python venv, SQLite, and Systemd.
- **Hides RunPod API Keys**: Credentials never touch the frontend.
- **Duplicate Job Prevention**: Validates active jobs via SQLite.
- **Image Caching**: Calculates SHA256 hashes and serves previous results from disk.
- **Authentication Ready**: Pre-configured with an `X-User-ID` header ready for Firebase JWT substitution.

## Tech Stack
- Python 3.12+
- FastAPI + Uvicorn
- SQLite + SQLAlchemy
- httpx (Async RunPod client)
- Nginx (Reverse Proxy)
- systemd (Process manager)

## Deployment Guide (Ubuntu)

### 1. Initial Setup
SSH into your VPS and install dependencies:
```bash
sudo apt update
sudo apt install python3.12 python3.12-venv nginx certbot python3-certbot-nginx sqlite3 -y
```

### 2. Project Setup
Clone or copy the project into `/var/www/photo_enhancer`:
```bash
sudo mkdir -p /var/www/photo_enhancer
sudo chown -R $USER:$USER /var/www/photo_enhancer
# Copy files into /var/www/photo_enhancer
```

### 3. Virtual Environment
```bash
cd /var/www/photo_enhancer
python3.12 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

### 4. Configuration
Create your `.env` file:
```bash
cp backend/.env.example .env
nano .env
```
Fill out `RUNPOD_API_KEY` and `RUNPOD_ENDPOINT_ID`.

### 5. Systemd Setup
Copy the service file to systemd:
```bash
sudo cp backend/deployment/enhance-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start enhance-api
sudo systemctl enable enhance-api
```

Check status: `sudo systemctl status enhance-api`

### 6. Nginx Setup
Copy the Nginx configuration:
```bash
sudo cp backend/deployment/nginx.conf /etc/nginx/sites-available/enhance-api
sudo ln -s /etc/nginx/sites-available/enhance-api /etc/nginx/sites-enabled/
```
Edit `/etc/nginx/sites-available/enhance-api` and change `server_name` to your domain.

Test and restart Nginx:
```bash
sudo nginx -t
sudo systemctl restart nginx
```

### 7. HTTPS / SSL (Certbot)
Run Certbot to automatically configure SSL:
```bash
sudo certbot --nginx -d api.yourdomain.com
```

## API Documentation

- **`POST /enhance`**
  - **Headers**: `X-User-ID`
  - **Body (Multipart)**: `image` (file), optional kwargs.
- **`GET /status/{job_id}`**
  - **Headers**: `X-User-ID`
  - **Returns**: Status and optionally base64 image data.
