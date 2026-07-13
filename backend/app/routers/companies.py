"""Company routes. Listing/reading is available to any authenticated user;
creating is admin-only."""

from fastapi import APIRouter, status

from ..deps import AdminUser, CurrentUser
from ..errors import AppError
from ..models.company import Company, CompanyCreate
from ..services import company_service

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[Company])
def list_companies(_user: CurrentUser, sector: str | None = None) -> list[dict]:
    return company_service.list_all(sector)


@router.get("/{company_id}", response_model=Company)
def get_company(company_id: int, _user: CurrentUser) -> dict:
    company = company_service.get(company_id)
    if not company:
        raise AppError("Company not found", 404)
    return company


@router.post("", response_model=Company, status_code=status.HTTP_201_CREATED)
def create_company(body: CompanyCreate, _admin: AdminUser) -> dict:
    return company_service.upsert(body.ticker, body.name, body.sector, body.currency)
