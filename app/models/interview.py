"""Pydantic models for interview tracking and placement management."""

from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import date, datetime
from enum import Enum


class InterviewStatus(str, Enum):
    """Status of an interview process."""
    IN_PROGRESS = "in_progress"
    OFFER_EXTENDED = "offer_extended"
    OFFER_ACCEPTED = "offer_accepted"
    REJECTED_BY_COMPANY = "rejected_by_company"
    CANDIDATE_WITHDREW = "candidate_withdrew"
    ON_HOLD = "on_hold"


class StageOutcome(str, Enum):
    """Outcome of an individual interview stage."""
    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"
    NO_SHOW = "no_show"
    CANCELLED = "cancelled"


class OfferDetails(BaseModel):
    """Details of a job offer.

    Attributes:
        base_salary: Base annual salary.
        total_comp: Total compensation including bonuses/equity.
        equity_value: Estimated equity value.
        signing_bonus: One-time signing bonus.
        currency: Currency code (e.g., "USD", "AUD").
        start_date: Proposed start date.
        other_benefits: Additional benefits or notes.
    """
    base_salary: Optional[float] = None
    total_comp: Optional[float] = None
    equity_value: Optional[float] = None
    signing_bonus: Optional[float] = None
    currency: str = "AUD"
    start_date: Optional[str] = None
    other_benefits: Optional[str] = None


class InterviewStage(BaseModel):
    """Represents a single stage in an interview process.

    Attributes:
        id: Unique stage identifier (UUID from database).
        interview_process_id: Parent interview process ID.
        stage_name: Name of the stage (e.g., "phone_screen", "technical", "onsite").
        stage_order: Order in the interview process (1, 2, 3...).
        scheduled_date: When the stage is scheduled.
        completed_date: When the stage was completed.
        outcome: Result of this stage.
        overall_rating: Overall rating 1-5.
        technical_rating: Technical skills rating 1-5.
        culture_fit_rating: Culture fit rating 1-5.
        communication_rating: Communication skills rating 1-5.
        feedback_notes: Detailed feedback from interviewers.
        interviewer_names: List of interviewer names.
        next_steps: Action items or next steps.
        created_at: When this stage was created.
    """
    id: Optional[str] = None
    interview_process_id: Optional[str] = None
    stage_name: str
    stage_order: int
    scheduled_date: Optional[date] = None
    completed_date: Optional[date] = None
    outcome: StageOutcome = StageOutcome.PENDING
    overall_rating: Optional[int] = None
    technical_rating: Optional[int] = None
    culture_fit_rating: Optional[int] = None
    communication_rating: Optional[int] = None
    feedback_notes: Optional[str] = None
    interviewer_names: List[str] = []
    next_steps: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        """Pydantic configuration."""
        use_enum_values = True


class InterviewProcess(BaseModel):
    """Represents a complete interview process for a candidate at a company.

    Attributes:
        id: Unique process identifier (UUID from database).
        candidate_id: ID of the candidate being interviewed.
        company_name: Company conducting the interview.
        role_title: Role/position being interviewed for.
        status: Current status of the interview process.
        feeder_source: Which feeder pattern this came from (for conversion tracking).
        recruiter_name: Name of recruiter managing this process.
        final_outcome: Final outcome description.
        offer_details: Details if offer was extended.
        stages: List of interview stages.
        created_at: When this process started.
        updated_at: Last update timestamp.
    """
    id: Optional[str] = None
    candidate_id: str
    company_name: str
    role_title: str
    status: InterviewStatus = InterviewStatus.IN_PROGRESS
    feeder_source: Optional[str] = None
    recruiter_name: Optional[str] = None
    final_outcome: Optional[str] = None
    offer_details: Optional[OfferDetails] = None
    stages: List[InterviewStage] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        """Pydantic configuration."""
        use_enum_values = True
