import logging
from fastapi import APIRouter, Depends, Response, Cookie, status, Request
from src.modules.auth.schema import UserSignup, UserLogin, UserResponse, ChangePassword, ForgotPassword, ResetPassword
from src.modules.auth.service import AuthService
from src.modules.auth.dependencies import get_current_user
from src.middleware.exceptions import AuthException

logger = logging.getLogger("wareops_erp.modules.auth.router")

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(payload: UserSignup, service: AuthService = Depends()):
    """Register a new Super Admin tenant and profile."""
    user = await service.register_tenant(payload)
    return {
        "success": True,
        "data": user,
        "message": "Super Admin registration completed successfully."
    }


@router.post("/login")
async def login(payload: UserLogin, response: Response, service: AuthService = Depends()):
    """Verify credentials and set secure, httpOnly refresh token cookie while returning access token."""
    session = await service.authenticate_user(payload)
    tokens = await service.create_session_tokens(session)
    
    # Configure long-lived secure refresh cookie (7 days)
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="strict",
        path="/api/v1/auth/refresh",
        max_age=7 * 24 * 3600
    )
    
    return {
        "success": True,
        "data": {
            "access_token": tokens["access_token"],
            "token_type": "bearer",
            "user": tokens["user"]
        },
        "message": "User logged in successfully."
    }


@router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    service: AuthService = Depends()
):
    """Rotate expired JWT access token using stateful httpOnly cookie."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise AuthException("Refresh session token is missing.")
        
    tokens = await service.rotate_session_tokens(refresh_token)
    
    # Update cookie with new rotated refresh token
    response.set_cookie(
        key="refresh_token",
        value=tokens["refresh_token"],
        httponly=True,
        secure=True,
        samesite="strict",
        path="/api/v1/auth/refresh",
        max_age=7 * 24 * 3600
    )
    
    return {
        "success": True,
        "data": {
            "access_token": tokens["access_token"],
            "token_type": "bearer",
            "user": tokens["user"]
        },
        "message": "Session token successfully rotated."
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    service: AuthService = Depends()
):
    """Terminate and invalidate user's active session keys."""
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        await service.terminate_session(refresh_token)
        
    # Invalidate and clear client browser cookie
    response.delete_cookie(
        key="refresh_token",
        path="/api/v1/auth/refresh"
    )
    
    return {
        "success": True,
        "message": "User session logged out successfully."
    }


@router.post("/change-password")
async def change_password(
    payload: ChangePassword,
    current_user: dict = Depends(get_current_user),
    service: AuthService = Depends()
):
    """Securely change logged-in user password."""
    await service.change_password(current_user, payload)
    return {
        "success": True,
        "message": "Password changed successfully."
    }


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPassword,
    service: AuthService = Depends()
):
    """Request a password reset link/token."""
    token = await service.forgot_password(payload)
    return {
        "success": True,
        "data": {"token": token},
        "message": "Password reset token generated successfully."
    }


@router.post("/reset-password")
async def reset_password(
    payload: ResetPassword,
    service: AuthService = Depends()
):
    """Reset password using a valid reset token."""
    await service.reset_password(payload)
    return {
        "success": True,
        "message": "Password reset successfully."
    }


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Retrieve details of the currently authenticated user."""
    return {
        "success": True,
        "data": {
            "id": str(current_user["_id"]),
            "name": current_user["name"],
            "email": current_user["email"],
            "role": current_user["role"],
            "warehouseId": current_user.get("warehouse_id"),
            "tenantId": current_user["tenant_id"],
            "avatar": current_user["avatar"],
            "status": current_user["status"],
            "permissionOverrides": current_user.get("permission_overrides"),
            "tableOverrides": current_user.get("table_overrides"),
            "warehouseOverrides": current_user.get("warehouse_overrides"),
            "moduleOverrides": current_user.get("module_overrides"),
            "employeeId": current_user.get("employee_id") or current_user.get("enterprise_id"),
            "profile": current_user.get("profile")
        },
        "message": "Current user retrieved successfully."
    }
