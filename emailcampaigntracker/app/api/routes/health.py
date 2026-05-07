from fastapi import APIRouter

from app.services.health_service import health_payload

router = APIRouter(tags=["Health"])


@router.get("/api/health")
def health_check():
    return health_payload()

