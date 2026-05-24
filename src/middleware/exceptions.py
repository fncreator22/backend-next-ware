import logging
from typing import Any, List, Optional
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("wareops_erp.middleware.exceptions")


class AppException(Exception):
    """Base class for all enterprise application exceptions."""
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Optional[List[Any]] = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []


class AuthException(AppException):
    """Raised when authentication credentials or token rotation fails."""
    def __init__(self, message: str = "Authentication credentials invalid or missing."):
        super().__init__(status_code=401, code="UNAUTHORIZED", message=message)


class PermissionException(AppException):
    """Raised when role-based privilege checks are violated."""
    def __init__(self, message: str = "Insufficient role permissions for this resource."):
        super().__init__(status_code=403, code="FORBIDDEN", message=message)


class NotFoundException(AppException):
    """Raised when a queried resource (e.g. warehouse, item) does not exist."""
    def __init__(self, message: str = "The requested resource was not found."):
        super().__init__(status_code=404, code="NOT_FOUND", message=message)


class ValidationException(AppException):
    """Raised for business logic validation errors."""
    def __init__(self, message: str, details: Optional[List[Any]] = None):
        super().__init__(status_code=422, code="VALIDATION_ERROR", message=message, details=details)


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Format custom application exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details
            }
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Serialize Pydantic validation errors into standard response format."""
    details = []
    for error in exc.errors():
        details.append({
            "field": ".".join([str(x) for x in error.get("loc", [])]),
            "issue": error.get("msg", ""),
            "type": error.get("type", "")
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request payload failed schema validation checks.",
                "details": details
            }
        }
    )


async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Serialize standard FastAPI/Starlette HTTP exceptions."""
    code_map = {
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
    }
    code = code_map.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": exc.detail,
                "details": []
            }
        }
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled 500 errors to maintain production resilience."""
    logger.error(f"Unhandled system exception occurred: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected system error occurred. Please try again later.",
                "details": []
            }
        }
    )


def register_exception_handlers(app: Any) -> None:
    """Register all standard exception handlers on the FastAPI app instance."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
