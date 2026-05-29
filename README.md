# NexWare ERP — Backend API Service

> ⚡ **FastAPI + MongoDB + WebSockets** — Enterprise-grade multi-tenant ERP backend with Argon2id auth, sliding-window rate limiting, real-time change streams, and a Redis/in-memory dual-tier cache.

---

## ⚡ Quick Start — Run on Any Device

> **Prerequisites:** [Python 3.11+](https://python.org/) · [MongoDB v6+](https://www.mongodb.com/try/download/community) · [Git](https://git-scm.com/)

### Step 1 — Clone the Backend Repository

```bash
git clone https://github.com/fncreator22/backend-next-ware.git
cd backend-next-ware
```

---

### Step 2 — Start MongoDB

The backend requires a running MongoDB instance before it will start.

**Windows (if installed as a service):**
```powershell
net start MongoDB
```

**Windows (manual start):**
```powershell
"C:\Program Files\MongoDB\Server\8.0\bin\mongod.exe" --dbpath "C:\data\db"
```

**Linux / macOS:**
```bash
sudo systemctl start mongod
# OR
mongod --dbpath /data/db
```

> 💡 **MongoDB Atlas (Cloud):** Set `MONGODB_URL` in your `.env` to your Atlas connection string and skip this step.

---

### Step 3 — Create Python Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate it
# Windows:
.venv\Scripts\activate

# Linux / macOS:
source .venv/bin/activate
```

---

### Step 4 — Install Dependencies

```bash
pip install -r requirements.txt
```

---

### Step 5 — Configure Environment Variables

```bash
# Windows:
copy .env.example .env

# Linux / macOS:
cp .env.example .env
```

Then open `.env` and edit the values:

```env
# Server
HOST=127.0.0.1
PORT=8000
RELOAD=True

# Database — Local MongoDB
MONGODB_URL=mongodb://localhost:27017
DB_NAME=wareops_erp_db

# OR — MongoDB Atlas
# MONGODB_URL=mongodb+srv://<user>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority

# Security — CHANGE THIS before any production deployment!
JWT_SECRET=your-cryptographically-random-64-char-secret-string-here
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=7

# Redis (Optional — falls back to in-memory cache automatically)
REDIS_URL=redis://localhost:6379/0

# SMTP Email (Optional — logs emails to console if not configured)
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM=noreply@nexware-erp.com
```

---

### Step 6 — Start the Backend Server

```bash
# Development (with hot-reload on file changes)
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload

# Production (no reload, all interfaces)
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

✅ **Backend is live at:** `http://127.0.0.1:8000`
📖 **Swagger API Docs:** `http://127.0.0.1:8000/docs`

---

## 🧰 All Available Commands

```bash
# Make sure your virtual environment is activated before running any command
.venv\Scripts\activate            # Windows
source .venv/bin/activate         # Linux / macOS

# ── Server ──────────────────────────────────────────────────────────────────
# Start development server (hot-reload)
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload

# Start production server (no reload)
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4

# ── Database Maintenance ─────────────────────────────────────────────────────
# Back up all database collections to JSON
python db_maintenance.py backup --file backups/my_backup.json

# Restore database from a backup file
python db_maintenance.py restore --file backups/my_backup.json

# Reset database to a clean vanilla state (deletes all data!)
python db_maintenance.py reset

# ── Health Verification ──────────────────────────────────────────────────────
# API health check
curl http://localhost:8000/health

# MongoDB connection status
curl http://localhost:8000/health/db

# System metrics (CPU, RAM, OS)
curl http://localhost:8000/health/system

# Cache status (Redis or in-memory fallback)
curl http://localhost:8000/health/cache
```

---

## 🏗️ Architecture & Folder Structure

```text
backend-next-ware/
├── .env                    # Local environment variables (not committed)
├── .env.example            # Template — copy this to .env
├── requirements.txt        # Pinned Python dependencies
├── db_maintenance.py       # Database backup / restore / reset CLI utility
├── src/
│   ├── config.py           # Pydantic BaseSettings singleton (reads .env)
│   ├── database.py         # Motor async MongoDB client + index initialization
│   ├── main.py             # FastAPI app factory, CORS, lifecycle hooks
│   ├── middleware/
│   │   ├── exceptions.py   # Domain exception → JSON error handlers
│   │   ├── logging.py      # Structured JSON request logger (stdout)
│   │   └── rate_limiter.py # Sliding window IP rate limiter (100 req/60s)
│   ├── utils/
│   │   ├── cache.py        # Redis → in-memory dual-tier cache manager
│   │   └── email.py        # SMTP email sender with console fallback
│   └── modules/
│       ├── auth/           # JWT sign-in, refresh rotation, Argon2id hashing
│       ├── warehouses/     # Multi-tenant warehouse management
│       ├── workforce/      # RBAC team hierarchy management
│       ├── items/          # Inventory catalog with Decimal128 pricing
│       ├── billing/        # Invoicing engine with tax snapshots
│       ├── dynamic_tables/ # Airtable-style runtime table compiler
│       ├── audit_logs/     # Immutable compliance event tracking
│       ├── analytics/      # Financial aggregate dashboards
│       ├── realtime/       # WebSocket manager + MongoDB change streams
│       └── health/         # Health probe endpoints (DB, cache, system)
```

---

## 🔌 API Endpoints Overview

| Category | Base Path | Key Endpoints |
|:---|:---|:---|
| **Auth** | `/api/v1/auth` | `POST /signup` · `POST /login` · `POST /refresh` · `POST /logout` |
| **Warehouses** | `/api/v1/warehouses` | `GET /` · `POST /` · `GET /{id}` · `PUT /{id}` · `DELETE /{id}` |
| **Workforce** | `/api/v1/workforce` | `GET /` · `POST /` · `PUT /{id}` · `DELETE /{id}` |
| **Items** | `/api/v1/items` | `GET /` · `POST /` · `PUT /{id}` · `DELETE /{id}` · `POST /bulk-import` |
| **Billing** | `/api/v1/billing` | `GET /` · `POST /` · `GET /{id}` · `PATCH /{id}/status` |
| **Tables** | `/api/v1/dynamic-tables` | `GET /` · `POST /` · `POST /{id}/rows` · `PUT /{id}/rows/{row_id}` |
| **Audit Logs** | `/api/v1/audit-logs` | `GET /` |
| **Analytics** | `/api/v1/analytics` | `GET /dashboard` · `GET /warehouse/{id}` |
| **Real-Time** | `/api/v1/realtime` | `WS /ws?token=<access_token>` |
| **Health** | `/health` | `GET /` · `GET /db` · `GET /cache` · `GET /system` |

📖 Full interactive docs: `http://localhost:8000/docs`

---

## ⚙️ Real-Time Architecture

```text
Client Browser
     │
     │  WebSocket Handshake  →  JWT token validated
     ▼
WS /api/v1/realtime/ws
     │
     ▼
WebSocketManager
     │  active_connections[tenant_id][warehouse_id]: Set[WebSocket]
     │
     ├─── Super Admin:  receives ALL tenant broadcasts
     └─── Staff/Admin:  receives only their warehouse_id events

Backend Services (Billing, Items, Workforce, Tables)
     │  on successful write mutation
     ▼
manager.broadcast(tenant_id, warehouse_id, event_payload)
     │
     ├─── MongoDB Replica Set → Change Streams (if available)
     └─── Standalone Mode    → Manual Pub-Sub event dispatch (fallback)
```

---

## 🔒 Security Overview

| Threat | Mitigation |
|:---|:---|
| Authentication bypass | JWT access + refresh tokens (15min / 7d) |
| Brute-force login | Sliding-window rate limiter — 429 on violation |
| Cross-tenant data leak | All DB queries scoped by `tenant_id` |
| Password storage | Argon2id hashing (OWASP recommended) |
| CSRF | SameSite cookie restrictions |
| CORS | Explicit origin allow-list in `config.py` |

> ⚠️ **Production Critical:** Set `JWT_SECRET` to a cryptographically random 64+ character string before any live deployment. Never use the default value.

---

## 🚀 Production Deployment

### Render / Railway (Cloud PaaS)

1. Connect your `backend-next-ware` GitHub repo to Render or Railway
2. Set **Build Command:** `pip install -r requirements.txt`
3. Set **Start Command:** `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables in the provider dashboard (copy from `.env.example`)

### Linux VPS (Systemd)

```bash
# Create systemd service file
sudo nano /etc/systemd/system/nexware-backend.service
```

```ini
[Unit]
Description=NexWare ERP FastAPI Backend
After=network.target mongod.service

[Service]
User=www-data
WorkingDirectory=/var/www/backend-next-ware
ExecStart=/var/www/backend-next-ware/.venv/bin/uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
EnvironmentFile=/var/www/backend-next-ware/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable nexware-backend
sudo systemctl start nexware-backend
```

---

## 🎯 Performance Targets

| Metric | Target |
|:---|:---|
| REST API Latency | `< 100ms` (sub-10ms for cached) |
| WebSocket Broadcast | `< 5ms` |
| Cache Read (Redis) | `< 1ms` |
| Cache Read (In-Memory) | `< 0.1ms` |
| Health Probe | `< 2ms` |

---

*NexWare ERP Backend — Enterprise Multi-Tenant Modular Monolith v2.0*
