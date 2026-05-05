"""Admin authentication — PROTECTED from Qwen modification.

Simple API key auth via X-Admin-Key header.
Qwen should use `Depends(require_admin)` on admin routes, never write its own auth.
"""

import hashlib
import os
import secrets

from fastapi import Header, HTTPException


def hash_key(key: str) -> str:
    """Hash an admin key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def require_admin(x_admin_key: str = Header(...)) -> str:
    """FastAPI dependency — validates admin API key.

    Returns the key on success for downstream use.
    Raises 401 if invalid, 503 if not configured.
    """
    expected = os.getenv("QTOWN_ADMIN_KEY")

    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Admin authentication not configured",
        )

    if not secrets.compare_digest(x_admin_key, expected):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin key",
        )

    return x_admin_key
