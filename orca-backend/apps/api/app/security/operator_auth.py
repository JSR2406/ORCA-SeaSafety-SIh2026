# Operator authentication for maritime-safety write endpoints.
#
# Publishing or acknowledging a safety alert is an authority action: a false or
# suppressed advisory can put crews at sea in danger.  These endpoints therefore
# require a signed bearer token carrying an authority role.
#
# Fails closed: when AUTH_JWT_SECRET / operator credentials are not configured,
# every protected write is rejected instead of silently staying public.
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

JWT_ALGORITHM = "HS256"
TOKEN_TTL_HOURS = 8
AUTHORITY_ROLE = "authority"

_bearer = HTTPBearer(auto_error=False)


def _secret() -> str:
    return settings.auth_jwt_secret


def _operator_email() -> str:
    return settings.auth_operator_email.strip().lower()


def _operator_password() -> str:
    return settings.auth_operator_password


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def authenticate_operator(email: str, password: str) -> Dict[str, str]:
    """Verify the seeded authority operator. Raises 401 on any mismatch."""
    configured_email = _operator_email()
    configured_password = _operator_password()
    if not _secret() or not configured_email or not configured_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Operator authentication is not configured",
        )

    # Hash on every attempt so a wrong email costs the same as a wrong password.
    expected_hash = hash_password(configured_password)
    email_ok = (email or "").strip().lower() == configured_email
    password_ok = verify_password(password or "", expected_hash)
    if not (email_ok and password_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid operator credentials",
        )
    return {"sub": configured_email, "role": AUTHORITY_ROLE}


def create_access_token(subject: str, role: str = AUTHORITY_ROLE) -> str:
    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALGORITHM)


def _decode(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, _secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Session expired, sign in again")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid token")


async def require_authority(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> Dict[str, Any]:
    """Dependency: valid operator token with the authority role."""
    if not _secret():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Operator authentication is not configured")
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Authority sign-in required")

    claims = _decode(credentials.credentials)
    if claims.get("type") != "access" or claims.get("role") != AUTHORITY_ROLE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Authority role required")
    return claims
