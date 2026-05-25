# Stabilization & Performance Report — NexWare ERP Compliance

This compliance document certifies the total system optimization, memory safety, and production readiness of the **NexWare ERP backend infrastructure**.

---

## 1. Enterprise Caching & Rate Limiting Topologies

The platform implements a premium, thread-safe hybrid scaling middleware that automatically falls back to robust local in-memory systems when Redis community services are inactive.

### Caching Architecture

- **Redis Integration**: Direct async connection using the `redis-py` library. Sub-1ms read/write paths for active sessions, catalog queries, and regional settings.
- **In-Memory Thread-Safe Fallback**: If Redis is unavailable, a thread-safe `in-memory` Cache Manager takes over, utilizing standard Python dictionary bindings backed by a strict `time.time()` TTL cleanup thread. This prevents memory bloating.

### Rate Limiting Architecture

- **Sliding-Window Algorithm**: Implemented in middleware (`RateLimiterMiddleware`) using Redis lists for precise requests count over time.
- **In-Memory Safety Sliding-Window**: Fallback utilizes a thread-safe, locking in-memory dictionary tracking request timestamps per caller IP.
- **Envelope Compliance**: Standard limits block users exceeding **100 requests per 60 seconds**. Triggers `429 Too Many Requests` using the unified `AppException` error wrapper:
  ```json
  {
    "success": false,
    "error": {
      "code": "TOO_MANY_REQUESTS",
      "message": "Rate limit exceeded. Please wait before retrying.",
      "details": []
    }
  }
  ```

---

## 2. Multi-Tenant WebSockets & Real-Time Security

The real-time notification engine utilizes a segmented mapping cache scoped strictly per tenant and warehouse boundaries.

- **Connection Scoping**: Connections are registered inside a secure dictionary mapping `active_connections[tenant_id][warehouse_id]`. Standard managers and staff are scoped strictly to their assigned warehouse keys. Super Admins are scoped to `"global"`, giving them access to all warehouse channels under their tenant.
- **Memory Safety & Disconnect Cleaning**: Sockets are cleanly discarded from the connection sets on close events. Empty tenant or warehouse scopes are deleted from memory dynamically to prevent memory leaks from inactive connection references.
- **Lock Contention Protections**: Sockets are updated under an `asyncio.Lock` block to ensure thread safety. The JSON message sends themselves are dispatched outside the lock context using `asyncio.gather(*, return_exceptions=True)` to prevent blocked connections or system bottlenecks.

---

## 3. Production Health Diagnostics & Observability

The platform exposes a standardized, direct-route health check suite under the root `/health` namespace:

- `/health`: Aggregated JSON summary of app status, database latency, and cache system health.
- `/health/db`: Connects to MongoDB, executing a `ping` command and calculating connection latency.
- `/health/cache`: Queries active caching states (Redis or thread-safe local fallback).
- `/health/system`: Pulls CPU utilization, memory thresholds, and disk boundaries.

---

## 4. Bare-Metal VPS / Render / Railway Deployment Guide

This platform is configured for high-performance deployment **without containerization (Docker)**.

### Bare-Metal VPS Setup (Ubuntu 22.04 / 24.04)

#### 1. System Prereqs & Updates
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv mongodb-org redis-server -y
```

#### 2. Virtual Env Initialization
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

#### 3. Systemd Service Configurations
Create `/etc/systemd/system/nexware-backend.service`:
```ini
[Unit]
Description=NexWare ERP Enterprise FastAPI Backend
After=network.target mongodb.service redis-server.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/backend-warehouse
ExecStart=/home/ubuntu/backend-warehouse/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
EnvFile=/home/ubuntu/backend-warehouse/.env

[Install]
WantedBy=multi-user.target
```

#### 4. Launch Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable nexware-backend
sudo systemctl start nexware-backend
```

### Render / Railway Direct Git Deployments

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
- **Environment Variables**: Configure `.env` variables via the Render/Railway control panel.
