import datetime

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import ADMIN_USERNAME, ADMIN_PASSWORD, JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES

security = HTTPBearer()


def authenticate(username: str, password: str) -> str | None:
    """Checks credentials against the single admin account and returns a JWT."""
    if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
        payload = {
            "sub": username,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(minutes=JWT_EXPIRE_MINUTES),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return None


def require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """FastAPI dependency that protects dashboard routes."""
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
