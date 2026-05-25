# NexWare ERP — Enterprise Multi-Tenant Monolith Monolith Backend

NexWare ERP is a high-performance, secure, and multi-tenant ERP platform backend designed as a modular monolith. It exposes a fully asynchronous FastAPI REST API integrated with MongoDB, WebSockets, rate limiting, centralized logs, heartbeat telemetry, and resilient standalone fallbacks.

---

## 🏗️ Architectural Folder Topology

The codebase is organized as a clean **Modular Monolith**, where each business domain is completely isolated under `src/modules/` with its own BSON database model, Pydantic schema mappings, Motor async repository layer, business service logic, and REST controllers:

```
src/
├── config.py              # Central BaseSettings configuration singleton
├── database.py            # MongoDB driver connections & index startup triggers
├── main.py                # Core FastAPI instance, lifecycles, and global middlewares
├── middleware/
│   ├── exceptions.py      # Unified domain exception-to-JSON handlers
│   ├── logging.py         # Centralized Request JSON Logger
│   └── rate_limiter.py    # Sliding window request protection
├── utils/
│   └── cache.py           # CacheManager with automatic local fallback
└── modules/
    ├── auth/              # JWT cookie sign-in & refresh rotation
    ├── warehouses/        # multi-tenant location isolation boundaries
    ├── workforce/         # RBAC member hierarchies
    ├── items/             # Decimal128 catalog & category aggregations
    ├── billing/           # Regional compliant invoicing & stock deductions
    ├── dynamic_tables/    # Airtable-style dynamic runtime compiler
    ├── audit_logs/        # Immutable compliance event trackers
    ├── analytics/         # Dynamic financial aggregate dashboards
    ├── realtime/          # Multi-tenant WebSocket registries
    └── health/            # Probes covering DB, Cache, and Host loads
```

---

## ⚡ Real-Time WebSockets & Fallback Loop Architecture

NexWare features a robust, multi-tenant scoped WebSocket gateway:

### 1. Multi-Tenant WebSocket Scoping
* **Route**: `WS /api/v1/realtime/ws?token=<access_token>`
* **Scoping Security**: Scopes client sockets inside a thread-locked connections registry:
  ```python
  active_connections[tenant_id][warehouse_id]: Set[WebSocket]
  ```
  JWT access tokens are decrypted during handshake query parameter validation. Sockets are separated strictly by `tenant_id`. Standard members only receive updates scoped to their designated `warehouse_id`, while Super Admins receive tenant-wide global event broadcasts.

### 2. Replica Set & Standalone Database Fallback
* **Replica Set Watch**: On database startup, background tasks attempt to spawn native MongoDB Change Streams (`watch()`) on core collections (`inventory_items`, `bills`, `audit_logs`, `users`).
* **Standalone Degraded Loop**: If MongoDB is running in standalone mode (no replica set configured), change streams fail gracefully, and the system transitions seamlessly to a **Manual Pub-Sub Broker**. Mutation service layers (Billing payments, catalog edits, workforce updates) automatically broadcast events via the `WebSocketManager` on successful writes, ensuring real-time client updates continue to function flawlessly.

---

## 🚀 Caching Abstraction Layer

The `CacheManager` class implements a transparent double-tier storage interface:
* **Tier 1 (Redis)**: Connects to a distributed Redis instance. Tests connection integrity using a fast async `ping()` on startup.
* **Tier 2 (In-Memory Fallback)**: If Redis is offline, not installed, or connection fails, the cache shifts automatically to thread-safe local dictionaries. Keys carry timestamp limits and are automatically purged during key lookups or writes to maintain constant memory boundaries.

---

## 🔒 Security, Rate Limiting & Observation Middlewares

### 1. Request Protection Rate Limiting
Intercepts all API requests and tracks request counts per client IP over sliding time windows (100 requests per minute by default).
* Uses Redis increment pipelines if available.
* Degrades gracefully to thread-safe local in-memory timestamp arrays.
* Excludes WebSocket connections and health checkheartbeats from limits.
* Returns `HTTP 429 Too Many Requests` on violation.

### 2. Centralized Structured Logging
Interceptors write a clean, single-line JSON request record straight to standard output (`stdout`), ready to be ingested by fluentd, vector, or other centralized log collectors:
```json
{"timestamp": "2026-05-25T18:01:17Z", "client_ip": "127.0.0.1", "method": "POST", "path": "/api/v1/items/", "status_code": 201, "latency_ms": 14.83, "tenant_id": "tenant_a"}
```

---

## 📊 Unified Heartbeat Telemetry Probes

Diagnostic probes are mounted directly under the root namespace to allow external service status monitors (UptimeRobot, Datadog) to verify nodes without JWT headers:
* `GET /health` — Simple health heartbeat status.
* `GET /health/db` — MongoDB driver connection verification.
* `GET /health/cache` — Caching connection state.
* `GET /health/system` — Windows physical memory and CPU diagnostics utilizing `ctypes` on Windows hosts.

---

## 🏛️ Compliant Regional Billing & Transactions

* **Compliance Snapshotting**: Snapshots tax categories (`luxury` vs `normal`) per warehouse, preserving historical invoice records against future tax rate updates.
* **ACID Deductions**: Inventory stock is decremented atomically inside an ACID transaction session context (`start_session()`).
* **Standalone Manual Rollback Fallback**: On standalone MongoDB nodes, the system runs sequential item deductions. If a stock violation occurs mid-loop, a manual rollback loop is instantly executed to restore the exact original stock state, preventing inventory mismatch.

---

## 💾 Enterprise Backup & Maintenance Utility

A secure, standalone administration utility is available at the repository root to perform database maintenance without container shells:

```powershell
# 1. Back up database collections directly to backups/ folder
.venv\Scripts\python.exe db_maintenance.py --action backup

# 2. Restore database from the latest JSON backup inside backups/
.venv\Scripts\python.exe db_maintenance.py --action restore

# 3. Clean and reset all collections to a fresh seed state
.venv\Scripts\python.exe db_maintenance.py --action reset
```

---

## 🚀 Bare-Metal VPS, Render, & Railway Production Deployment Guide

This guide details deploying the modular monolith backend in a non-containerized environment:

### Prerequisites
* Python 3.12+ installed on host machine.
* Active MongoDB Community Server (v8.0+) or MongoDB Atlas connection string.
* (Optional) Local or Cloud Redis instance.

### Step 1: Environment Configuration
Create a production `.env` file in the repository root matching the target configurations:
```env
HOST="0.0.0.0"
PORT=8000
RELOAD=false
MONGODB_URL="mongodb+srv://<user>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority"
DB_NAME="wareops_erp_production"
JWT_SECRET="YOUR_HIGH_ENTROPY_CRYPTOGRAPHIC_JWT_SECRET_32_BYTES_MIN"
REDIS_URL="redis://:<password>@redis-cloud-server:6379/0"
```

### Step 2: Virtual Environment Setup & Dependency Installation
```bash
# 1. Clone backend repository to target server
git clone <your-repo-url> backend-warehouse
cd backend-warehouse

# 2. Setup Python virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# 3. Install production dependencies
pip install -r requirements.txt
```

### Step 3: Running via Production Process Manager (PM2 / Systemd)

#### Option A: Deploying via Systemd (Bare-metal Linux VPS)
Create a new service file `/etc/systemd/system/nexware-backend.service`:
```ini
[Unit]
Description=NexWare ERP FastAPI Monolith Service
After=network.target

[Service]
User=www-data
WorkingDirectory=/var/www/backend-warehouse
ExecStart=/var/www/backend-warehouse/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
EnvironmentFile=/var/www/backend-warehouse/.env

[Install]
WantedBy=multi-user.target
```
Start and enable the service:
```bash
sudo systemctl daemon-reload
sudo systemctl start nexware-backend
sudo systemctl enable nexware-backend
```

#### Option B: Deploying on Render or Railway
To host the backend on Git-integrated cloud providers without containers:
1. **Build Command**: `pip install -r requirements.txt`
2. **Start Command**: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
3. Configure target `.env` parameters inside the provider's Environmental variables dashboard.

---

## 🎯 Target Performance Metrics

* **REST Endpoint Latency**: `< 100ms` (Sub-10ms for cached responses).
* **WS Event Broadcast Latency**: `< 5ms`.
* **Cache Read Latency**: `< 1ms` (Sub-0.1ms for InMemory fallback).
* **Telemetry heartbeats**: `< 2ms`.
