"""Admin-only routes. Gated by the require_admin dependency."""

from fastapi import APIRouter

from ..deps import AdminUser
from ..services import user_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(_admin: AdminUser) -> dict:
    return {"users": user_service.list_public()}
