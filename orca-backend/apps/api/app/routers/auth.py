# Operator sign-in for maritime-authority actions (alert publish / acknowledge).
# Public marine data stays open; only safety-alert writes need this token.
from typing import Any, Dict

import structlog
from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from app.security.operator_auth import (
    authenticate_operator,
    create_access_token,
    require_authority,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class OperatorLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


@router.post("/login")
async def operator_login(body: OperatorLoginRequest) -> Dict[str, Any]:
    claims = authenticate_operator(body.email, body.password)
    logger.info("operator_login", subject=claims["sub"])
    return {
        "access_token": create_access_token(claims["sub"], claims["role"]),
        "token_type": "bearer",
        "role": claims["role"],
        "email": claims["sub"],
    }


@router.get("/me")
async def operator_me(claims: Dict[str, Any] = Depends(require_authority)) -> Dict[str, Any]:
    return {"email": claims.get("sub"), "role": claims.get("role")}
