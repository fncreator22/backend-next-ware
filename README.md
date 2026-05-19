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
