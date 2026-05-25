# WareOps ERP — Asynchronous Enterprise Backend

This is the secure, modular, asynchronous enterprise SaaS backend for **WareOps ERP**, architected in **Python** using **FastAPI** and a **MongoDB-first** database strategy. It serves as a highly scalable Modular Monolith, designed with clean interfaces to allow individual modules to seamlessly split into microservices in the future.

---

## 🚀 Key Architectural Priorities

- **Modular Monolith**: Strict boundary isolation where modules have self-contained layers (routers, services, schemas, models, repositories) and are prohibited from querying other module collections directly.
- **Tenant & Warehouse Isolation**: Automatic tenant scoping applied globally via FastAPI dependency injection guards on database query filters.
- **MongoDB-First Database Strategy**: High-performance JSON-native document storage for core relational, dynamic tables, and audit trail events. Atomic operations across collections are handled via MongoDB Multi-Document ACID Transactions.
- **Dynamic Table Builder**: An Airtable-like runtime column validation system. Columns, headers, and validation schemas live in a `table_schemas` collection, with dynamic rows saved in `table_rows` and validated on write via runtime Pydantic configurations.
- **Enterprise-Grade Security**:
  - **Argon2id Hashing**: configured with optimal parameters ($m=65536, t=3, p=4$) for password protection.
  - **Token Rotation**: Short-lived HMAC-SHA256 JWT access tokens (15 mins) combined with httpOnly, secure, rotating refresh tokens (7 days) tracked in Redis/MongoDB.
  - **Role-Based Access Control (RBAC)**: Enforced privilege hierarchy: `employee` (1) < `staff` (2) < `manager` (3) < `admin` (4) < `super_admin` (5).
- **Double-Entry Financial Math**: All billing/invoice totals and calculations are executed via Python's `decimal.Decimal` module and stored in MongoDB's `Decimal128` format to eliminate floating-point math rounding issues.

---

## 📂 Project Organization

The repository strictly preserves a scalable, modular design. Each module is fully encapsulated:

```
src/
├── main.py                   # FastAPI Application Entry Point
├── config.py                 # Pydantic BaseSettings Configuration Loader
├── database.py               # Motor Asynchronous MongoDB Client & Session Registry
├── middleware/               # CORS, Security Headers, Custom Logging
└── modules/
    ├── auth/                 # Authentication, JWT handling, Argon2id
    ├── warehouses/           # Warehouse registries
    ├── items/                # Catalog item and SKU level management
    ├── billing/              # Invoice compilation & credit note double-entry balance
    ├── dynamic_tables/       # Custom Airtable-like table schemas & dynamic data rows
    ├── workforce/            # Staff roles & privilege hierarchies
    └── audit_logs/           # Secure, write-once user operation logging
```

Inside each module, boundaries are preserved across these layers:
* `router.py`: API endpoint pathways and FastAPI dependencies.
* `service.py`: Orchestration of business workflows.
* `schema.py`: Pydantic models for validation of incoming and outgoing payloads.
* `model.py`: Data type mapping representing MongoDB records.
* `repository.py`: Motor asynchronous query operations.
* `utils.py`: Specific module auxiliary helper tools.

---

## 🚦 Router Endpoint Tree

All endpoints reside under the `/api/v1` namespace and preserve the following routing:

| Module Route Prefix | Method | Endpoint Path | Authentication | Description |
| :--- | :---: | :--- | :---: | :--- |
| **`/api/v1/auth`** | POST | `/signup` | Public | Registers a new Super Admin tenant |
| | POST | `/login` | Public | Authenticates and returns access & refresh tokens |
| | POST | `/refresh` | httpOnly Cookie | Rotates and issues a new access/refresh token pair |
| | POST | `/logout` | JWT | Invalidates the active session and tokens |
| **`/api/v1/warehouses`** | GET | `/` | JWT | Lists active warehouses (scopes based on roles) |
| | POST | `/` | JWT | Creates a new warehouse registry |
| | GET | `/{id}` | JWT | Fetches a specific warehouse's detailed registry |
| | PUT | `/{id}` | JWT | Modifies a warehouse profile |
| | DELETE | `/{id}` | JWT | Cascade deletes a warehouse and all associated data |
| **`/api/v1/items`** | GET | `/` | JWT | Fetches catalog items matching warehouse scope |
| | POST | `/` | JWT | Registers new item (evaluates SKU uniqueness) |
| | PUT | `/{id}` | JWT | Adjusts stock levels or specifications |
| | DELETE | `/{id}` | JWT | Removes item from catalog |
| **`/api/v1/billing`** | GET | `/` | JWT | Lists invoices under tenant (hierarchical view) |
| | POST | `/` | JWT | Generates bill (triggers atomic stock deduction) |
| | GET | `/{id}/print` | JWT | Streams invoice calculation PDF |
| **`/api/v1/dynamic-tables`**| GET | `/` | JWT | Retrieves custom schemas registered for warehouse |
| | POST | `/` | JWT | Creates a custom Airtable-like metadata schema |
| | GET | `/{tableId}/rows` | JWT | Fetches rows matching schema (dynamic schema validated) |
| | POST | `/{tableId}/rows`| JWT | Appends rows into document collection |
| **`/api/v1/workforce`** | GET | `/` | JWT | Lists staff members matching scope constraints |
| | POST | `/` | JWT | Creates new staff profile (cannot exceed caller privilege) |
| | PUT | `/{id}` | JWT | Updates role assignment or workforce status |
| **`/api/v1/audit-logs`** | GET | `/` | JWT | Pulls historical user action trail (write-once) |

---

## 🛠️ Developer Setup & Launch

1. **Virtual Environment Setup**:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   source .venv/bin/activate # Unix/macOS
   ```
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
3. **Environment Setup**:
   Copy `.env.example` to `.env` and adjust database variables.
4. **Run Application**:
   ```bash
   uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
   ```
   Open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) to access Swagger OpenAPI interactive documentation.

---

## 📦 Phase 5 — Scoped Item Catalog & Inventory Management

Phase 5 introduces a robust, enterprise-grade inventory system with warehouse-scoped partitioning, exact Decimal pricing math, and dashboard-optimized analytics pipelines.

### 1. Inventory Architecture

The inventory module utilizes a clean repository-service pattern inside [src/modules/items/](file:///c:/Users/sr2ma/OneDrive/Documents/GitHub/backend-warehouse/src/modules/items/). The backend is mathematically secure: prices and stock values are tracked utilizing Python's `decimal.Decimal` module and stored in MongoDB's native high-precision `Decimal128` format. This prevents floating-point issues during billing allocations.

### 2. Inventory Lifecycle Flow

```mermaid
stateDiagram-v2
    [*] --> Draft: SKU Assigned
    Draft --> Registered: create_item Validation
    Registered --> OutOfStock: stock == 0
    Registered --> LowStock: stock < 20
    Registered --> HealthyStock: stock >= 50
    LowStock --> HealthyStock: Restock Order
    OutOfStock --> HealthyStock: Restock Order
    HealthyStock --> LowStock: Sales Deductions
    Registered --> Retired: delete_item Action
    Retired --> [*]
```

### 3. Warehouse-Scoped Isolation

Tenant boundaries are enforced dynamically at the database repository query layer:
* **Super Admin**: Has global visibility across all registered warehouses.
* **Admin, Manager, Staff**: Query filters are strictly forced to their assigned `warehouse_id`. Staff have read-only access.
* **Employee**: Read-only catalog visibility.

SKU uniqueness is enforced per warehouse partition, allowing identical product SKUs to exist across different warehouses under the same tenant without catalog collision.

### 4. Optimized Aggregation & Dashboard Pipelines

The backend exposes four advanced analytics routes under `/api/v1/items/analytics/` specifically optimized for graphs, KPI cards, and smart AI restocking tables:

```
                  ┌──────────────────────────────┐
                  │   FastAPI Analytics Router   │
                  └──────────────┬───────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    /summary     │     │   /categories   │     │  /stock-status  │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ • Total Items   │     │ • Group by Cat  │     │ • Group by:     │
│ • Total Stock   │     │ • Item count    │     │   - in_stock    │
│ • Valuation     │     │ • Valuation     │     │   - low_stock   │
│ • Low Stock     │     │                 │     │   - out_of_stock│
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

* **`GET /api/v1/items/analytics/summary`**: Aggregates catalog totals, physical stock units, total dollar valuation, and low stock metrics.
* **`GET /api/v1/items/analytics/categories`**: Groups inventory count and total valuation per category segment.
* **`GET /api/v1/items/analytics/stock-status`**: Distributes stock counts into health buckets (`in_stock`, `low_stock`, `out_of_stock`).
* **`GET /api/v1/items/analytics/trends`**: Aggregates monthly inventory creation volume.

### 5. MongoDB Indexing & Performance Optimizations

To achieve sub-100ms local query executions, we register compound database indexes on startup:

1. **Compound Index `[("warehouse_id", 1), ("sku", 1)]`**: Enforces strict SKU uniqueness within a single warehouse partition while speeding up transactional lookup speeds.
2. **Compound Index `[("tenant_id", 1), ("warehouse_id", 1)]`**: Optimizes listings query speeds and scopes filtering limits instantly.

---

## 💰 Phase 6 — Billing Transactions & Atomic Stock Deductions

Phase 6 implements a secure billing engine that guarantees database consistency during inventory transactions, snapping regional taxes at the exact millisecond of purchase.

### 1. Invoicing & Stock Deduction Workflow

```mermaid
flowchart TD
    A[Checkout Request] --> B{Replica Set Active?}
    B -->|Yes| C[Open Multi-Document ACID Session]
    B -->|No| D[Execute Sequential Fallback Block]
    C --> E[Verify Cash Totals & Snapshot Regional Taxes]
    D --> E
    E --> F[Check Stock Sufficiency]
    F -->|Insufficient| G[Abort ACID Session / Sequential Rollback]
    F -->|Sufficient| H[Decrement Stock counts & Insert Invoice document]
    H --> I[Commit ACID Transaction / Confirm Standalone Update]
    I --> J[Paid Invoice Issued & Printed]
```

### 2. Standalone Fallback & ACID Transactions

* **Staged ACID Transactions**: When running on production replica sets or MongoDB Atlas, the system utilizes MongoDB's native multi-document ACID transaction sessions (`start_session` and `start_transaction`).
* **Manual Sequential Rollback Fallback**: On local standalone developer instances, the system automatically detects the lack of a replica set configuration and switches to sequential operations. If any stock overdraft or exception occurs mid-deduction, it sequentially restores the original catalog stock levels from local backups, avoiding database crashes.

### 3. Financial Integrity & Double-Entry Math

* **Pricings & Totals**: Evaluated entirely using Python's `decimal.Decimal` module on the backend to safeguard against client-side pricing manipulations.
* **Storage Precision**: Financial fields (`subtotal`, `tax`, `total`, item snapshot `price`) are stored utilizing BSON `Decimal128` format.
* **Immutable Records**: Once generated, invoice documents (`bills` collection) are historically immutable. Corrections are managed by issuing negative value Credit Notes referencing the original `bill_no`.

### 4. Advanced Revenue Analytics

Dashboard widgets are powered by high-performance aggregation pipelines under `/api/v1/billing/analytics/`:
* **`GET /api/v1/billing/analytics/revenue`**: Computes gross revenue, tax collected, net revenue, and average invoice size.
* **`GET /api/v1/billing/analytics/trends`**: Groups invoice volumes monthly for line charts.
* **`GET /api/v1/billing/analytics/top-items`**: Aggregates bestselling inventory items.
* **`GET /api/v1/billing/analytics/warehouse-performance`**: Scopes sales summaries grouped per warehouse name.

---

## 📋 Phase 7 — Dynamic Tables & Analytics Intelligence

Phase 7 delivers a highly customizable, Airtable-style dynamic metadata schema builder, an enterprise-grade analytics engine, and a secure, role-scoped immutable audit logging system.

### 1. Runtime Schema Validation Flow

```mermaid
flowchart TD
    A[Post /api/v1/dynamic-tables/:id/rows] --> B[Fetch Custom Schema Metadata]
    B --> C[Extract Column Types & Required Settings]
    C --> D[Compile Dynamic Pydantic Model at Runtime]
    D --> E[Validate Payload via Compiled Model]
    E -->|Validation Failure| F[Reject with detailed 400 Validation Error]
    E -->|Structure Passes| G[Execute Custom Option Range Checks]
    G -->|Dropdown/Status Mismatch| F
    G -->|All Checks Pass| H[Flatten Object & Persist in MongoDB]
```

### 2. Multi-Tenant Analytics & Scoping Boundaries

All custom table schemas and dynamically appended rows are strictly isolated under tenant partitions using compound query selectors. 
* **Role-Based Schema Visibility**: Table schemas can declare restricted access `roles`. If not empty, only users with those roles (or system `admins` / `super_admins`) can fetch or append rows.
* **Cascading Purge Safety**: Deleting a custom schema automatically executes a cascading delete, removing all associated row documents to prevent orphaned records.

### 3. High-Performance Analytics & Aggregations

The analytics engine uses MongoDB aggregation pipelines to compile real-time dashboard cards, KPI widgets, and trend visualizations:
* **`GET /api/v1/analytics/dashboard`**: A unified, high-performance API compiling total revenues, total tax collected, physical stock units, active users count, low stock alarms, recent activity, recent invoices, and smart restock recommendations in a single round-trip database query.
* **`GET /api/v1/analytics/revenue`**: Aggregates total billing, tax collections, average invoice values, and net margins.
* **`GET /api/v1/analytics/inventory`**: Groups catalog total stocks and valuation per category segment.
* **`GET /api/v1/analytics/workforce`**: Resolves active user allocations per role distributions.
* **`GET /api/v1/analytics/trends`**: Evaluates month-by-month financial progress metrics over a rolling 12-month period.

### 4. Immutable Audit Logs & Role Scopes

The `audit_logs` collection provides a read-only, tamper-proof record of system events. 
* **Dynamic Role Scoping (Upward Reflection)**: Managers can see operational logs of staff members, and admins can see logs of managers. However, lower role levels are blocked from accessing logs of their superiors, safeguarding internal operations.

---

## 💾 Database Maintenance & Safe Backup/Restore Utility

To prevent accidental data loss and enforce platform integrity, we provide a structured, safe command-line database utility `db_maintenance.py` in the backend root folder:

### 1. Generate Structured JSON Backup
Safely exports all collections (`users`, `warehouses`, `sessions`, `audit_logs`, `inventory_items`, `bills`, `table_schemas`, `table_rows`) with correct BSON typing, ObjectId representations, Decimal128 values, and UTC datetime snapshots:
```bash
.venv\Scripts\python.exe db_maintenance.py backup --file backups/manual_backup.json
```

### 2. Restore Database from JSON Snapshot
Safely drops and restores all operational collections to matching BSON structures:
```bash
.venv\Scripts\python.exe db_maintenance.py restore --file backups/manual_backup.json
```

### 3. Safe Database Reset
Automatically generates a timestamped auto-backup first in the `backups/` directory before purging all collection data:
```bash
.venv\Scripts\python.exe db_maintenance.py reset
```

---

## 🚦 Full Local Integration & Startup Guide

To run the complete full-stack **NexWare ERP** locally with a live connection, execute the following steps in sequence:

### Terminal 1: Asynchronous FastAPI Backend
1. Navigate to the backend directory:
   ```bash
   cd C:\Users\sr2ma\OneDrive\Documents\GitHub\backend-warehouse
   ```
2. Activate virtual environment and launch Uvicorn:
   ```bash
   .venv\Scripts\activate
   uvicorn src.main:app --reload --host 127.0.0.1 --port 8000
   ```
   * *Backend starts up live at [http://127.0.0.1:8000](http://127.0.0.1:8000) with swagger docs at `/docs`.*

### Terminal 2: Static Modern SPA Frontend
1. Navigate to the frontend directory:
   ```bash
   cd "C:\Users\sr2ma\OneDrive\Documents\New folder\warehouse-erp"
   ```
2. Launch dev bundling compiler watch and serve standard web files:
   ```bash
   npm run dev
   ```
   * *Frontend launches live at [http://localhost:3000](http://localhost:3000) (using serve default).*

### Terminal 3: MongoDB Verification
1. To inspect loopback connectivity and ping replica set status:
   ```bash
   mongosh --eval "db.adminCommand('ping')"
   ```



