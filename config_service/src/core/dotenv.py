from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def load_dotenv(path: Optional[str] = None, *, override: bool = False) -> bool:
    """Minimal .env loader (no external dependency).

    Loads key=value pairs into os.environ.
    Returns True if a file was found and loaded.
    """
    p = Path(path or ".env")
    if not p.exists():
        return False

    try:
        contents = p.read_text(encoding="utf-8")
    except OSError:
        # In restricted/sandboxed environments, reading .env may be disallowed.
        # Treat it as "not loaded" rather than failing hard.
        return False

    for raw in contents.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not override and k in os.environ:
            continue
        os.environ[k] = v

    return True
