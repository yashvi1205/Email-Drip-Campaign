from fastapi import APIRouter

from app.services.profiles_service import list_profiles_clean, list_profiles_raw

router = APIRouter(tags=["Profiles"])


@router.get("/api/profiles")
def get_profiles():
    return list_profiles_clean()


@router.get("/api/profiles/raw")
def get_profiles_raw():
    return list_profiles_raw()

