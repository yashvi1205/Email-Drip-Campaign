import hmac
import time
from hashlib import sha256

from fastapi import HTTPException

from app.core.settings import get_settings


def compute_tracking_signature(tracking_id: str, exp: int) -> str:
    settings = get_settings()
    msg = f"{tracking_id}:{exp}".encode("utf-8")
    return hmac.new(settings.tracking_signing_secret.encode("utf-8"), msg, sha256).hexdigest()


def validate_tracking_signature(tracking_id: str, exp: int | None, sig: str | None) -> None:
    settings = get_settings()
    # Compatibility mode unless explicitly required
    if not settings.require_signed_tracking and (exp is None or sig is None):
        return

    if exp is None or sig is None:
        raise HTTPException(status_code=401, detail="Missing tracking signature")

    now = int(time.time())
    if exp < now:
        raise HTTPException(status_code=401, detail="Tracking token expired")

    expected = compute_tracking_signature(tracking_id, exp)
    if not hmac.compare_digest(expected, sig):
        raise HTTPException(status_code=401, detail="Invalid tracking signature")

