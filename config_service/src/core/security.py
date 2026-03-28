import hashlib
import os
import secrets


def generate_token(token_bytes: int = 32) -> str:
    # URL-safe token (suitable for Authorization: Bearer ...)
    return secrets.token_urlsafe(token_bytes)


def hash_token(token: str, *, pepper: str) -> str:
    """Hash an opaque bearer token for storage.

    Uses SHA-256(token + pepper). Pepper must be set via env var and kept secret.
    """
    h = hashlib.sha256()
    h.update(token.encode("utf-8"))
    h.update(pepper.encode("utf-8"))
    return h.hexdigest()


def get_token_pepper() -> str:
    pepper = os.getenv("TOKEN_PEPPER")
    if not pepper:
        raise RuntimeError("TOKEN_PEPPER is not set")
    return pepper
