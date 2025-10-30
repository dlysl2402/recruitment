"""Pydantic models for feeder patterns and role-based scoring configuration."""

from pydantic import BaseModel
from typing import List, Optional, Dict


class WeightedSkill(BaseModel):
    """Represents a skill with an importance weight for scoring.

    Attributes:
        name: Skill name (e.g., "multicast", "bgp").
        weight: Importance weight for this skill (default: 1.0).
                Higher weights mean more important skills.
                Used for proportional scoring calculations.
    """
    name: str
    weight: float = 1.0


class PedigreeCompany(BaseModel):
    """Represents a prestigious company for career pedigree scoring.

    Pedigree companies are those where working there signals high quality,
    regardless of whether they're a feeder for the current role.

    Attributes:
        company: Primary company name.
        company_aliases: Alternative names for the same company.
        multiplier: Prestige multiplier applied to S-curve points (default: 1.0).
                    Top tier (Google/Meta) = 1.0, High tier (Microsoft) = 0.8-0.9.
    """
    company: str
    company_aliases: List[str] = []
    multiplier: float = 1.0


class FeederPattern(BaseModel):
    """Defines a company-based pattern for identifying strong candidates.

    Feeder patterns represent companies that historically produce strong
    candidates for specific roles (e.g., Amazon NDEs for HFT network roles).

    Attributes:
        company: Primary company name.
        company_aliases: Alternative names for the same company.
        priority: Pattern priority (1=primary, 2=secondary, etc.).
        min_tenure_years: Minimum years at company to qualify.
        max_tenure_years: Maximum years at company to qualify.
        required_titles: Job titles that match this pattern.
        boost_keywords: Keywords that boost the score if found in description.
        multiplier: S-curve multiplier for tenure-based scoring (default: 1.0).
        candidates_sourced: Number of candidates sourced via this pattern.
        candidates_placed: Number of successful placements.
        conversion_rate: Placement success rate (0.0-1.0).
        last_updated: Date this pattern was last updated (YYYY-MM-DD).
    """
    company: str
    company_aliases: List[str]
    priority: int
    min_tenure_years: float
    max_tenure_years: float
    required_titles: List[str] = []
    boost_keywords: List[str] = []
    multiplier: float = 1.0

    # Performance tracking
    candidates_sourced: int = 0
    candidates_placed: int = 0
    conversion_rate: float = 0.0
    last_updated: str


class RoleFeederConfig(BaseModel):
    """Complete configuration for scoring candidates for a specific role.

    Defines all criteria for evaluating candidates including feeder patterns,
    required/optional skills, and negative signals.

    Attributes:
        role_name: Machine-readable role identifier (e.g., "network_engineer").
        display_name: Human-readable role name (e.g., "Network Engineer").
        feeders: List of feeder patterns to match against.
        required_skills: Weighted skills that candidates must have.
        nice_to_have_skills: Weighted optional skills that boost the score.
        pedigree_companies: Prestigious companies for career pedigree scoring.
        relevant_title_keywords: Keywords required in job title for pedigree to count.
        avoid_companies: Companies that are red flags for this role.
        red_flags: Other negative signals to watch for.
        typical_salary_range: Salary range metadata for the role.
        notes: Additional notes about this role configuration.
    """
    role_name: str
    display_name: str

    feeders: List[FeederPattern]

    # Role requirements
    required_skills: List[WeightedSkill] = []
    nice_to_have_skills: List[WeightedSkill] = []

    # Pedigree scoring
    pedigree_companies: List[PedigreeCompany] = []
    relevant_title_keywords: List[str] = []  # Required keywords in title for pedigree to count

    # Negative signals
    avoid_companies: List[str] = []
    red_flags: List[str] = []

    # Metadata
    typical_salary_range: Optional[Dict] = None
    notes: str = ""
