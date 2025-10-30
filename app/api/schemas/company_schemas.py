"""Request and response schemas for company endpoints."""

from pydantic import BaseModel
from typing import Optional, List


class CreateCompanyRequest(BaseModel):
    """Request model for creating a new company."""
    name: str
    aliases: Optional[List[str]] = None
    industry: Optional[str] = None
    headquarters_city: Optional[str] = None
    headquarters_country: Optional[str] = None
    internal_notes: Optional[str] = None


class UpdateCompanyRequest(BaseModel):
    """Request model for updating a company."""
    name: Optional[str] = None
    aliases: Optional[List[str]] = None
    industry: Optional[str] = None
    headquarters_city: Optional[str] = None
    headquarters_country: Optional[str] = None
    internal_notes: Optional[str] = None
