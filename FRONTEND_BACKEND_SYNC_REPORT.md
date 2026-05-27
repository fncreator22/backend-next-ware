# Frontend/Backend Synchronization Report — NexWare ERP Compliance

This compliance document certifies that all communication payloads, schemas, and event structures between the **NexWare SPA Frontend** and the **FastAPI Backend** are perfectly synchronized and audited for case mappings, numeric types, and date shapes.

---

## 1. API Payload Structures & Case Unification

To ensure full compatibility with the plain-JS SPA, all backend schemas employ Pydantic's `ConfigDict` with `populate_by_name=True` to support seamless **camelCase** serialization boundaries while maintaining standard Pythonic **snake_case** internally.

### Case Mapping Audits

| Module / Endpoint | Frontend Payload Key | Backend Database Field | Serialization Mapping |
| :--- | :--- | :--- | :--- |
| **Auth Login** | `email`, `password` | `email`, `hashed_password` | Direct validation |
| **Auth Signup** | `name`, `email`, `password` | `name`, `email`, `hashed_password` | Direct validation |
| **Warehouse** | `name`, `businessName`, `address`, `contact`, `email`, `taxPreference`, `logo` | `name`, `business_name`, `address`, `contact`, `email`, `tax_preference`, `logo` | Scoped case mapping |
| **Items CRUD** | `name`, `category`, `sku`, `price`, `stock`, `warehouseId`, `unit` | `name`, `category`, `sku`, `price`, `stock`, `warehouse_id`, `unit` | Scoped case mapping |
| **Billing** | `warehouseId`, `customer`, `items`, `subtotal`, `tax`, `total`, `taxConfigSnapshot` | `warehouse_id`, `customer`, `items`, `subtotal`, `tax`, `total`, `tax_config_snapshot` | Scoped case mapping |
| **Dynamic Tables** | `warehouseId`, `tableName`, `category`, `description`, `columns`, `roles`, `headerColor` | `warehouse_id`, `table_name`, `category`, `description`, `columns`, `roles`, `header_color` | Dynamic model compiler |

---

## 2. Floating-Point & BSON Decimal128 Conversions

To safeguard the ERP's financial integrity, the billing engine utilizes Python's `decimal.Decimal` for all arithmetic checks, preventing the truncation errors inherent in standard floating-point operations.

### Conversions Boundary Matrix

- **Database Storage**: The repository translates Python `Decimal` values into BSON `Decimal128` on database inserts via `_convert_decimal_to_decimal128()` to ensure extreme precision in MongoDB storage.
- **Database Query**: On retrieval, the repository converts BSON `Decimal128` fields back to Pythonic `Decimal` objects via `_convert_decimal128_to_decimal()`.
- **API Response**: Pydantic validation schemas (`InvoiceResponse`, `InvoiceItemResponse`) automatically serialize these Python `Decimal` fields into standard JSON `float` values, matching the frontend's expected numeric types.
- **Tamper-Proofing Calculations**: The backend recalculates `subtotal`, `tax`, and `total` based on the item prices and the active tax snap configurations. It rejects client payloads that deviate from calculated precision totals.

---

## 3. Standardized Datetime Format

To ensure consistent charting, timeline rendering, and history logs, all datetimes are formatted using **ISO 8601 (YYYY-MM-DDTHH:MM:SS.mmmmmm)**:

- **FastAPI / Pydantic**: Pydantic's datetime serialization converts BSON `datetime.datetime` objects into standard ISO 8601 strings in the response payloads.
- **Database Maintenance**: Backup files utilize BSON representation `{"$date": doc.isoformat()}` to guarantee lossless restores.
- **Frontend SPA**: Parsed ISO strings are localized using the standard `toLocaleDateString()` and `toLocaleTimeString()` utilities in `ui.js`.

---

## 4. WebSocket Payload Structures

The real-time broadcast engine matches the precise JSON shapes expected by the multi-tenant WebSocket subscribers in the SPA.

### WebSocket Message Envelope

Every broadcast follows the standard envelope structure:
```json
{
  "type": "event_type",
  "data": {
    "id": "resource_id",
    "warehouseId": "warehouse_scope",
    "tenantId": "tenant_scope",
    "updatedFields": {}
  }
}
```

- **Supported Broadcast Channels**:
  - `billing_completion`: Sent upon invoice completion. Flat representation containing the created bill metadata, item summaries, and tax configuration.
  - `inventory_stock_alert`: Fired when an item's stock is updated or drops below the safety threshold.
  - `workforce_activity`: Dispatched when workforce profiles are updated or roles are modified.
  - `audit_log_creation`: Live stream of system compliance logs.
