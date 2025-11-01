"""Response schemas for API endpoints."""

from pydantic import BaseModel
from typing import List, Dict, Optional, Any


class CandidateScoreResponse(BaseModel):
    """Response model for candidate scoring endpoints."""
    linkedin_url: str
    score: float
    breakdown: Dict


class CandidateFilterResponse(BaseModel):
    """Response model for filtered candidate results."""
    id: str
    first_name: str
    last_name: str
    linkedin_url: str
    current_company: Optional[Dict[str, Any]] = None
    current_title: Optional[str] = None
    location: Optional[Dict[str, Any]] = None
    matched_skills: List[str]
