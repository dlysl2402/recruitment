"""Response schemas for API endpoints."""

from pydantic import BaseModel
from typing import List, Dict


class CandidateScoreResponse(BaseModel):
    """Response model for candidate scoring endpoints."""
    linkedin_url: str
    score: float
    breakdown: Dict


class CandidateFilterResponse(BaseModel):
    """Response model for filtered candidate results."""
    first_name: str
    last_name: str
    linkedin_url: str
    matched_skills: List[str]
