import os
import sys
import time
import ctypes
import logging
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from src.database import db_conn
from src.utils.cache import cache_manager

logger = logging.getLogger("wareops_erp.modules.health")

router = APIRouter(tags=["Health Check"])


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def get_windows_memory():
    """Query accurate Windows memory load statistics using ctypes."""
    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(stat)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        return {
            "memory_load_percent": stat.dwMemoryLoad,
            "total_physical_gb": round(stat.ullTotalPhys / (1024 ** 3), 2),
            "available_physical_gb": round(stat.ullAvailPhys / (1024 ** 3), 2),
            "used_physical_gb": round((stat.ullTotalPhys - stat.ullAvailPhys) / (1024 ** 3), 2)
        }
    except Exception:
        return None


@router.get("/health")
async def health():
    """Verify general application heartbeat."""
    return {
        "success": True,
        "status": "healthy",
        "service": "WareOps ERP Enterprise API",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }


@router.get("/health/db")
async def health_db():
    """Verify MongoDB database connection ping state."""
    if db_conn.db is None:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "status": "unhealthy",
                "database": "disconnected",
                "error": "MongoDB driver not initialized"
            }
        )
    try:
        await db_conn.db.command("ping")
        return {
            "success": True,
            "status": "healthy",
            "database": "connected"
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "status": "unhealthy",
                "database": "disconnected",
                "error": str(e)
            }
        )


@router.get("/health/cache")
async def health_cache():
    """Verify caching status (Redis vs safe In-Memory fallback)."""
    if cache_manager.use_redis:
        return {
            "success": True,
            "status": "healthy",
            "cache_layer": "Redis",
            "redis": "connected"
        }
    else:
        return {
            "success": True,
            "status": "healthy (degraded)",
            "cache_layer": "In-Memory Fallback Active",
            "redis": "disconnected"
        }


@router.get("/health/system")
async def health_system():
    """Verify hardware load metrics (Memory and CPU statistics)."""
    sys_metrics = {
        "os": sys.platform,
        "cpu_count": os.cpu_count(),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    }

    if sys.platform == "win32":
        mem = get_windows_memory()
        if mem:
            sys_metrics["memory"] = mem

    if "memory" not in sys_metrics:
        sys_metrics["memory"] = {
            "memory_load_percent": "N/A",
            "total_physical_gb": "N/A",
            "available_physical_gb": "N/A",
            "used_physical_gb": "N/A"
        }

    return {
        "success": True,
        "status": "healthy",
        "system": sys_metrics
    }
