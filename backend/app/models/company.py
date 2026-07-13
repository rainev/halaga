"""Company schemas."""

from pydantic import BaseModel, Field


class Company(BaseModel):
    id: int
    ticker: str
    name: str
    sector: str | None = None
    currency: str = "PHP"


class CompanyCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    name: str = Field(min_length=1)
    sector: str | None = None
    currency: str = "PHP"
