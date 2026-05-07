def health_payload() -> dict:
    return {
        "status": "healthy",
        "version": "1.1.0",
        "endpoints": ["/api/dashboard/drip", "/api/profiles/raw"],
    }

