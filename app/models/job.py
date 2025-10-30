"""Pydantic models for job postings and tracking."""

from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from enum import Enum


class JobStatus(str, Enum):
    """Status of a job posting."""
    OPEN = "open"
    FILLED = "filled"
    CLOSED = "closed"
    ON_HOLD = "on_hold"


class Job(BaseModel):
    """Represents a job opening at a company.

    Attributes:
        id: Unique job identifier (UUID from database).
        company_id: ID of the company posting this job.
        role_title: Job title/position.
        department: Department or team.
        location: Job location (city, remote, hybrid).
        status: Current status of the job.
        total_candidates_submitted: Total candidates submitted for this job.
        total_interviews_started: Total interviews started.
        filled_by_candidate_id: ID of candidate who filled this position.
        filled_date: Date when position was filled.
        internal_notes: Internal notes about the job.
        created_at: When this job was created.
        updated_at: Last update timestamp.
    """
    id: Optional[str] = None
    company_id: str
    role_title: str
    department: Optional[str] = None
    location: Optional[str] = None
    status: JobStatus = JobStatus.OPEN
    total_candidates_submitted: int = 0
    total_interviews_started: int = 0
    filled_by_candidate_id: Optional[str] = None
    filled_date: Optional[date] = None
    internal_notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        """Pydantic configuration."""
        use_enum_values = True
