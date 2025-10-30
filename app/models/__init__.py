"""Pydantic models for the recruitment application."""

from app.models.candidate import (
    DateInfo,
    CompanyReference,
    Location,
    Experience,
    Education,
    MediaItem,
    Project,
    Certification,
    Skills,
    PlacementRecord,
    LinkedInCandidate
)
from app.models.feeder import WeightedSkill, PedigreeCompany, FeederPattern, RoleFeederConfig
from app.models.interview import (
    InterviewStatus,
    StageOutcome,
    OfferDetails,
    InterviewStage,
    InterviewProcess
)
from app.models.job import JobStatus, Job

__all__ = [
    "DateInfo",
    "CompanyReference",
    "Location",
    "Experience",
    "Education",
    "MediaItem",
    "Project",
    "Certification",
    "Skills",
    "PlacementRecord",
    "LinkedInCandidate",
    "WeightedSkill",
    "PedigreeCompany",
    "FeederPattern",
    "RoleFeederConfig",
    "InterviewStatus",
    "StageOutcome",
    "OfferDetails",
    "InterviewStage",
    "InterviewProcess",
    "JobStatus",
    "Job"
]
