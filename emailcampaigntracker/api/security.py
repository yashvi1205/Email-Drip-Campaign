from fastapi import HTTPException, Request


def _extract_api_key(request: Request) -> str | None:
    # Prefer explicit header
    header_key = request.headers.get("x-api-key")
    if header_key:
        return header_key.strip()

    # Support Authorization: Bearer <key>
    auth = request.headers.get("authorization")
    if not auth:
        return None
    parts = auth.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def require_api_key(expected_key: str):
    async def _dependency(request: Request) -> None:
        provided = _extract_api_key(request)
        if not provided or provided != expected_key:
            raise HTTPException(status_code=401, detail="Unauthorized")

    return _dependency

