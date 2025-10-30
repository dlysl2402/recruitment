"""Pydantic models for LinkedIn candidate profiles and related data structures."""

from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import date


class DateInfo(BaseModel):
    """Represents a date with optional month and year.

    Attributes:
        month: Month name (e.g., "Jan", "Feb").
        year: Four-digit year.
    """
    month: Optional[str] = None
    year: Optional[int] = None


class CompanyReference(BaseModel):
    """Reference to a company with optional link to companies table.

    Attributes:
        id: UUID of company in companies table (if matched).
        name: Company name (always present).
    """
    id: Optional[str] = None
    name: str


class Location(BaseModel):
    """Represents a geographic location.

    Attributes:
        city: City name.
        country: Country name.
        country_code: Two-letter country code (e.g., "US", "AU").
    """
    city: str
    country: str
    country_code: str


class Experience(BaseModel):
    """Represents a work experience entry from a LinkedIn profile.

    Attributes:
        title: Job title.
        company: Company reference (name + optional ID).
        company_linkedin_url: Optional LinkedIn company page URL.
        start_date: Employment start date.
        end_date: Employment end date (None if current position).
        duration: Duration string (e.g., "2 yrs 3 mos").
        description: Job description text.
        skills: List of skills used in this role.
    """
    title: str
    company: CompanyReference
    company_linkedin_url: Optional[str] = None
    start_date: Optional[DateInfo] = None
    end_date: Optional[DateInfo] = None
    duration: Optional[str] = None
    description: Optional[str] = None
    skills: List[str] = []


class Education(BaseModel):
    """Represents an education entry from a LinkedIn profile.

    Attributes:
        school: Institution name.
        degree: Degree or qualification earned.
        start_year: Year education started.
        end_year: Year education ended.
    """
    school: str
    degree: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None


class MediaItem(BaseModel):
    """Represents a media item (image, video) from a LinkedIn project.

    Attributes:
        title: Media item title/filename.
        url: Optional URL to the media file.
        thumbnail: Optional thumbnail URL.
    """
    title: str
    url: Optional[str] = None
    thumbnail: Optional[str] = None


class Project(BaseModel):
    """Represents a project entry from a LinkedIn profile.

    Attributes:
        name: Project name.
        start_date: Project start date.
        end_date: Project end date.
        description: Project description.
        associated_company: Company associated with the project.
        project_urls: List of URLs related to the project.
        media_items: List of media items with title and thumbnail info.
    """
    name: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    associated_company: Optional[str] = None
    project_urls: Optional[List[str]] = []
    media_items: Optional[List[MediaItem]] = []


class Certification(BaseModel):
    """Represents a certification entry from a LinkedIn profile.

    Attributes:
        name: Certification name.
        organization: Issuing organization.
        organization_urn: LinkedIn URN for the organization.
        credential_id: Unique identifier for the credential.
        issue_date: Date the certification was issued.
        expiration_date: Date the certification expires.
        credential_url: URL to verify the certification.
    """
    name: str
    organization: str
    organization_urn: Optional[str] = None
    credential_id: Optional[str] = None
    issue_date: Optional[str] = None
    expiration_date: Optional[str] = None
    credential_url: Optional[str] = None


class Skills(BaseModel):
    """Represents a skill from a LinkedIn profile.

    Attributes:
        name: Skill name (normalized lowercase).
        display_name: Original skill name for display.
        endorsement_count: Number of endorsements received.
    """
    name: str
    display_name: str
    endorsement_count: int


class PlacementRecord(BaseModel):
    """Represents a successful job placement for a candidate.

    Attributes:
        company: Company where candidate was placed.
        role: Role/position title.
        placement_date: Date when offer was accepted.
        base_salary: Base annual salary.
        total_comp: Total compensation including bonuses/equity.
        feeder_source: Which feeder pattern sourced this placement.
        interview_id: ID of the interview process that led to placement.
    """
    company: str
    role: str
    placement_date: date
    base_salary: Optional[float] = None
    total_comp: Optional[float] = None
    feeder_source: Optional[str] = None
    interview_id: Optional[str] = None


class LinkedInCandidate(BaseModel):
    """Complete LinkedIn candidate profile with all sections.

    Attributes:
        first_name: Candidate's first name.
        last_name: Candidate's last name.
        headline: Professional headline.
        about: About/summary section.
        location: Geographic location.
        linkedin_url: Full LinkedIn profile URL.
        current_title: Current job title.
        current_company: Current employer.
        current_description: Current job description.
        current_start_date: Start date of current position.
        experience: List of all work experiences.
        education: List of education entries.
        projects: List of projects.
        skills: List of skills.
        certifications: List of certifications.
        benchmark_scores: Dictionary of role-to-score mappings.
    """
    # Basic info
    first_name: str
    last_name: str
    headline: Optional[str] = None
    about: Optional[str] = None
    location: Location
    linkedin_url: str

    # Current position
    current_title: Optional[str] = None
    current_company: Optional[CompanyReference] = None
    current_description: Optional[str] = None
    current_start_date: Optional[DateInfo] = None

    # Full history
    experience: List[Experience] = []
    education: List[Education] = []
    projects: List[Project] = []
    skills: List[Skills] = []
    certifications: List[Certification] = []

    # Scoring
    benchmark_scores: Dict[str, float] = {}

    # Placement tracking
    placement_history: List[PlacementRecord] = []

    class Config:
        """Pydantic configuration."""
        extra = "ignore"
