from datetime import datetime, timedelta
import jwt
from argon2 import PasswordHasher
from src.config import settings

# Argon2id configuration hashing defaults
# m=65536, t=3, p=4 parameters are preserved for brute-force resistance
ph = PasswordHasher(memory_cost=65536, time_cost=3, parallelism=4)


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return ph.hash(password)


def verify_password(hashed: str, plain: str) -> bool:
    """Verify standard Argon2id hashed passwords."""
    try:
        return ph.verify(hashed, plain)
    except Exception:
        return False


def create_access_token(data: dict) -> str:
    """Sign and generate short-lived access JWT."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")


def create_refresh_token(data: dict) -> str:
    """Sign and generate long-lived refresh JWT."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decode and cryptographically verify a JWT. Raises appropriate JWT errors on failure."""
    return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
