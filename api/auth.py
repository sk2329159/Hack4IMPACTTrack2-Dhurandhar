"""
api/auth.py
============
JWT creation/verification + RBAC dependencies + login route.
Merged from: routes/auth.py + dependencies.py

WHO OWNS THIS: Backend team

Contains:
  - ROLE_HIERARCHY and require_role() dependency factory
  - get_current_user() JWT decode dependency
  - /auth/login route handler

Bugs fixed:
  - Timezone-aware JWT timestamps (was naive datetime.utcnow)
  - Timing-safe login: dummy hash prevents username enumeration via response time
  - Failed login attempts are logged (username only, never password)
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from api.config import get_settings
from api.schemas import LoginRequest, TokenResponse

logger   = logging.getLogger("sentinel.auth")
router   = APIRouter(tags=["auth"])
settings = get_settings()
bearer   = HTTPBearer()
pwd_ctx  = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ── RBAC ──────────────────────────────────────────────────────────────────────

ROLE_HIERARCHY: dict[str, set[str]] = {
    "viewer":  {"viewer"},
    "analyst": {"viewer", "analyst"},
    "admin":   {"viewer", "analyst", "admin"},
}


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret,
                          algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> dict:
    return _decode_token(credentials.credentials)


def require_role(*allowed_roles: str):
    """
    FastAPI dependency factory.
    Usage: Depends(require_role("analyst", "admin"))
    """
    def _check(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("role", "")
        granted   = ROLE_HIERARCHY.get(user_role, set())
        if not granted.intersection(set(allowed_roles)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user
    return _check


# ── Demo users (replace with DB lookup for production) ────────────────────────

_DEMO_USERS: dict[str, dict] = {
    "admin":   {"hashed": pwd_ctx.hash("admin123"),   "role": "admin"},
    "analyst": {"hashed": pwd_ctx.hash("analyst123"), "role": "analyst"},
    "viewer":  {"hashed": pwd_ctx.hash("viewer123"),  "role": "viewer"},
}

# Constant-time dummy hash prevents username enumeration via timing
_DUMMY_HASH = pwd_ctx.hash("dummy_sentinel_value_never_matches")


# ── Login route ───────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse,
             summary="Authenticate and receive a JWT")
async def login(body: LoginRequest) -> TokenResponse:
    """
    Demo credentials:
      admin / admin123 → role: admin
      analyst / analyst123 → role: analyst
      viewer / viewer123 → role: viewer
    """
    user           = _DEMO_USERS.get(body.username)
    hash_to_check  = user["hashed"] if user else _DUMMY_HASH  # timing-safe

    password_ok = pwd_ctx.verify(body.password, hash_to_check)

    if not user or not password_ok:
        logger.warning("Failed login: username=%s", body.username[:32])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    now        = datetime.now(timezone.utc)
    expires_in = settings.jwt_expire_minutes * 60
    token      = jwt.encode(
        {
            "sub":  body.username,
            "role": user["role"],
            "iat":  int(now.timestamp()),
            "exp":  int((now + timedelta(seconds=expires_in)).timestamp()),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    logger.info("JWT issued: sub=%s role=%s", body.username, user["role"])
    return TokenResponse(access_token=token, role=user["role"], expires_in=expires_in)