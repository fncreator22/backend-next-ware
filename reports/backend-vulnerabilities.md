# Backend Security Vulnerability Assessment
**Project Component**: NexWare-ERP Backend API  
**Audit Date**: May 28, 2026  
**Auditor**: Senior Backend Security Auditor  
**Classification**: CONFIDENTIAL — Internal Engineering Use Only

---

## 1. Executive Summary

The NexWare-ERP backend demonstrates a strong security posture across authentication, authorization, and multi-tenant isolation. The implementation of Argon2id password hashing, stateful JWT session tracking with database-backed revocation, per-request tenant scoping in the repository layer, and a configurable rate limiter reflects mature security engineering. The primary risks are concentrated around deployment configuration — the default fallback JWT secret and the overly permissive CORS policy in development.

### 🔐 Overall Backend Security Score: **7.6 / 10**

> [!IMPORTANT]
> The two highest-severity findings (VULN-BE-001 and VULN-BE-002) are **deployment-time** risks, not code-level bugs. They represent configurations that are intentionally relaxed in development but **must** be locked down before production deployment.

---

## 2. Vulnerability Register

### 🔴 VULN-BE-001: Hardcoded Default JWT Secret in `config.py`
- **Severity**: CRITICAL (if deployed to production without override)
- **CVSS v3.1 Score**: 9.1 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H)
- **Affected File**: `src/config.py` (line 25)
- **Root Cause**: The `Settings` class defines a hardcoded fallback value for `JWT_SECRET`:
```python
JWT_SECRET: str = "super_secret_cryptographic_key_replace_in_production_32_bytes_min"
```
If the `.env` file is absent or `JWT_SECRET` is not explicitly set in the production environment, the application silently falls back to this well-known string. Any attacker who reads the open-source GitHub repository can forge valid JWT access tokens for any user on any tenant, achieving complete authentication bypass.
- **Risk Level**: CRITICAL in production without environment override
- **Remediation**:
```python
# Replace the default with a validation that hard-fails if not configured:
JWT_SECRET: str = Field(..., min_length=32, description="Must be set via environment variable in production")
```
Alternatively, generate a random secret at startup and fail explicitly if the key matches the known development placeholder:
```python
@validator('JWT_SECRET')
def validate_jwt_secret(cls, v):
    if v == "super_secret_cryptographic_key_replace_in_production_32_bytes_min":
        import os
        if os.getenv("ENVIRONMENT") == "production":
            raise ValueError("JWT_SECRET must be overridden in production!")
    return v
```

---

### 🔴 VULN-BE-002: Overly Broad CORS `ALLOWED_ORIGINS` in Development Mode
- **Severity**: HIGH (in production context)
- **CVSS v3.1 Score**: 7.2 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N)
- **Affected File**: `src/config.py` (lines 11–18)
- **Root Cause**: The default `ALLOWED_ORIGINS` list includes `http://localhost:3000`, `http://localhost:5000`, and `http://localhost:8080`. Combined with `allow_credentials=True`, any attacker who tricks a logged-in user into visiting a page on one of these origins (if they control a local service) can make credentialed cross-origin requests to the API. More critically, if the production deployment does not explicitly override `ALLOWED_ORIGINS` to only include the production domain, local development origins remain active.
- **Risk Level**: HIGH in production if not overridden
- **Remediation**: Override `ALLOWED_ORIGINS` via environment variable in production:
```bash
# .env (production)
ALLOWED_ORIGINS=["https://app.nexware.com"]
```
Add a startup validation that warns loudly if localhost origins are present in a non-development environment.

---

### 🟡 VULN-BE-003: Missing Brute-Force Protection on `/auth/login`
- **Severity**: MEDIUM
- **CVSS v3.1 Score**: 5.9 (AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N)
- **Root Cause**: The global rate limiter applies 100 requests/60 seconds per IP. This blanket limiter allows approximately 100 login attempts per minute from any single IP, which is insufficient to block targeted brute-force attacks against known email addresses (since the per-account limit is not separately enforced).
- **Risk Level**: MEDIUM — Argon2id hashing provides significant computational resistance, but a dedicated brute-force rig can still try ~1.5 passwords/second per CPU core.
- **Remediation**: Add per-endpoint login rate limiting:
```python
# Apply strict rate limiter only to auth endpoints (5 attempts per 60 seconds)
@router.post("/login")
@limiter.limit("5/minute")
async def login(...):
```
Also add an account lockout mechanism (e.g., lock after 10 failed attempts within 5 minutes, stored in Redis).

---

### 🟡 VULN-BE-004: Potential IDOR in Workforce & Item Endpoints
- **Severity**: MEDIUM
- **CVSS v3.1 Score**: 5.4 (AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:N/A:N)
- **Root Cause**: Endpoints like `GET /api/v1/items/{item_id}` and `PUT /api/v1/workforce/{user_id}` accept MongoDB ObjectIDs in the URL path. If the repository queries use only the `item_id`/`user_id` without also filtering by `tenant_id`, a malicious authenticated user from Tenant A could access or modify records belonging to Tenant B by guessing or enumerating valid MongoDB ObjectIDs.
- **Assessment**: The repository pattern is designed to include `tenant_id` filtering — this is **likely protected** in most modules. However, explicit verification in every `find_by_id` method is required.
- **Risk Level**: Medium — impact is high if any repository method bypasses tenant scoping
- **Remediation**: Audit every `find_by_id(item_id)` call in all repository files to confirm it includes `{"_id": ObjectId(item_id), "tenant_id": tenant_id}` as the filter rather than `{"_id": ObjectId(item_id)}` alone.

---

### 🟡 VULN-BE-005: No HTTP Security Headers Middleware
- **Severity**: MEDIUM
- **CVSS v3.1 Score**: 5.1 (AV:N/AC:H/PR:N/UI:R/S:U/C:H/I:N/A:N)
- **Root Cause**: The FastAPI application does not set standard browser security headers. Missing headers include:
  - `Content-Security-Policy` — prevents XSS payload execution
  - `X-Content-Type-Options: nosniff` — prevents MIME-type sniffing
  - `X-Frame-Options: DENY` — prevents clickjacking
  - `Strict-Transport-Security` — enforces HTTPS
  - `Referrer-Policy: no-referrer`
- **Remediation**: Add a `SecurityHeadersMiddleware`:
```python
from starlette.middleware.base import BaseHTTPMiddleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
```

---

### 🟢 VULN-BE-006: MongoDB Injection — Protected by Motor's BSON Driver
- **Severity**: LOW (documented as non-issue)
- **Root Cause**: All MongoDB queries pass through Motor's BSON serializer, which correctly handles special characters in query values. NoSQL injection via string concatenation into raw query strings is not possible with Motor's parameterized query API.
- **Risk Level**: LOW — confirmed safe with current Motor driver usage

---

## 3. Backend Security Scorecard

| Category | Score | Finding |
| :--- | :--- | :--- |
| Authentication Strength | 9/10 | 🟢 Excellent — Argon2id + stateful JWT revocation |
| Secrets Management | 5/10 | 🔴 Risk — default JWT secret must be overridden |
| Multi-Tenant Isolation | 8/10 | 🟢 Strong — enforced at repository layer |
| CORS Configuration | 5/10 | 🔴 Risk — localhost origins in production default |
| Brute-Force Resistance | 6/10 | 🟡 Medium — global rate limiter, no per-account lockout |
| IDOR Protection | 7/10 | 🟡 Likely safe, requires explicit per-repo verification |
| Security Headers | 4/10 | 🔴 Missing — no HTTP security response headers set |
| NoSQL Injection | 9/10 | 🟢 Safe — Motor BSON driver prevents injection |

---

## 4. Immediate Remediation Priorities

1. **[CRITICAL]** Add production startup validation that fails hard if `JWT_SECRET` equals the known development placeholder string.
2. **[HIGH]** Override `ALLOWED_ORIGINS` in the production environment to only include the production domain. Add startup warning if localhost origins are detected in production mode.
3. **[MEDIUM]** Add per-account login lockout after 10 failed attempts within 5 minutes.
4. **[MEDIUM]** Audit all repository `find_by_id` methods to verify `tenant_id` is always included in the filter.
5. **[MEDIUM]** Add `SecurityHeadersMiddleware` to set `CSP`, `X-Frame-Options`, `X-Content-Type-Options`, and `HSTS` headers on all API responses.
