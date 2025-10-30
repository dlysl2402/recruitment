"""Request and response schemas for job endpoints."""

from pydantic import BaseModel
from typing import Optional
from app.models.job import JobStatus


class CreateJobRequest(BaseModel):
    """Request model for creating a new job."""
    company_id: str
    role_title: str
    department: Optional[str] = None
    location: Optional[str] = None
    internal_notes: Optional[str] = None


class UpdateJobRequest(BaseModel):
    """Request model for updating a job."""
    role_title: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    status: Optional[JobStatus] = None
    internal_notes: Optional[str] = None


class CloseJobRequest(BaseModel):
    """Request model for closing a job."""
    filled_by_candidate_id: Optional[str] = None
