from fastapi import APIRouter, Depends, Response, status
from src.modules.auth.schema import UserSignup, UserLogin, TokenResponse
from src.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(payload: UserSignup, service: AuthService = Depends()):
    """Register a new Super Admin and tenant."""
    # SKELETON PLACEHOLDER
    return {"success": True, "message": "Super Admin signed up successfully", "data": {"email": payload.email}}


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin, response: Response, service: AuthService = Depends()):
    """Authenticate credentials, return access token and set refresh token httpOnly cookie."""
    # SKELETON PLACEHOLDER
    return {
        "success": True,
        "access_token": "mock_access_token_placeholder",
        "token_type": "bearer"
    }


@router.post("/refresh")
async def refresh(response: Response, service: AuthService = Depends()):
    """Rotate expired JWT access token using httpOnly refresh token cookie."""
    # SKELETON PLACEHOLDER
    return {
        "success": True,
        "access_token": "mock_refreshed_access_token_placeholder",
        "token_type": "bearer"
    }


@router.post("/logout")
async def logout(service: AuthService = Depends()):
    """Revoke user's refresh token sessions."""
    # SKELETON PLACEHOLDER
    return {"success": True, "message": "User logged out successfully"}
