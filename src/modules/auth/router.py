import logging
from fastapi import APIRouter, Depends, Response, Cookie, status, Request
from src.modules.auth.schema import UserSignup, UserLogin, UserResponse
from src.modules.auth.service import AuthService
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
