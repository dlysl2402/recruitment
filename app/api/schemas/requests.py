"""Request schemas for API endpoints."""

from pydantic import BaseModel
from typing import Optional, List, Dict
from datetime import date

from app.models.interview import InterviewStatus, StageOutcome, OfferDetails


class CreateInterviewRequest(BaseModel):
    """Request model for creating a new interview process."""
    candidate_id: str
    company_name: str
    role_title: str
    feeder_source: Optional[str] = None
    recruiter_name: Optional[str] = None


class AddStageRequest(BaseModel):
    """Request model for adding a stage to an interview."""
    stage_name: str
    stage_order: int
    scheduled_date: Optional[date] = None


class UpdateStageOutcomeRequest(BaseModel):
    """Request model for updating stage outcome and feedback."""
    outcome: StageOutcome
    overall_rating: Optional[int] = None
    technical_rating: Optional[int] = None
    culture_fit_rating: Optional[int] = None
    communication_rating: Optional[int] = None
    feedback_notes: Optional[str] = None
    interviewer_names: Optional[List[str]] = None
    next_steps: Optional[str] = None


class CompleteInterviewRequest(BaseModel):
    """Request model for completing an interview process."""
    final_status: InterviewStatus
    offer_details: Optional[OfferDetails] = None
    final_outcome: Optional[str] = None
