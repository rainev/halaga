"""Holdings (owned-company watchlist) routes. Scoped to the authenticated user.
Adding a company is what turns its news on in the insights feed."""

from fastapi import APIRouter, status

from ..deps import CurrentUser
from ..models.holding import Holding, HoldingCreate
from ..services import holdings_service

router = APIRouter(prefix="/holdings", tags=["holdings"])


@router.get("", response_model=list[Holding])
def list_holdings(user: CurrentUser) -> list[dict]:
    return holdings_service.list_for_user(user["sub"])


@router.post("", response_model=Holding, status_code=status.HTTP_201_CREATED)
def add_holding(body: HoldingCreate, user: CurrentUser) -> dict:
    return holdings_service.add(user["sub"], body.ticker)


@router.delete("/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_holding(holding_id: int, user: CurrentUser) -> None:
    holdings_service.remove(user["sub"], holding_id)
