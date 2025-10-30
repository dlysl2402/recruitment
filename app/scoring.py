"""Candidate scoring logic based on feeder patterns and role requirements."""

import os
import json
import re
from datetime import datetime
from typing import Dict, Optional, List, Set, Tuple
from dataclasses import dataclass, field

from app.models import LinkedInCandidate, DateInfo, Experience
from app.feeder_models import RoleFeederConfig, FeederPattern
from app.constants import FEEDER_CONFIG_FILE, MONTH_NAME_TO_NUMBER, DAYS_PER_YEAR, MONTHS_PER_YEAR


# Cache for feeder configs
_FEEDER_CONFIGS = None


@dataclass
class ScoringResult:
    """Result of scoring a candidate against a role.

    Attributes:
        score: Final score (floored at 0).
        breakdown: Dictionary of scoring components and their values.
        matched_feeder: Name of the feeder pattern that matched (if any).
    """
    score: float
    breakdown: Dict[str, any] = field(default_factory=dict)
    matched_feeder: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary format for API responses."""
        return {
            "score": self.score,
            "breakdown": self.breakdown
        }


def load_feeder_configs(filepath: str = FEEDER_CONFIG_FILE) -> Dict[str, RoleFeederConfig]:
    """Load and validate feeder configurations from JSON file.

    Args:
        filepath: Path to the feeder configuration JSON file.

    Returns:
        Dictionary mapping role names to their feeder configurations.

    Raises:
        FileNotFoundError: If the config file doesn't exist.
        json.JSONDecodeError: If the config file is invalid JSON.
        ValidationError: If the config doesn't match the expected schema.
    """
    with open(filepath, "r") as config_file:
        data = json.load(config_file)

    configs = {}
    for role_name, config_data in data.items():
        configs[role_name] = RoleFeederConfig(**config_data)

    return configs


def get_feeder_configs() -> Dict[str, RoleFeederConfig]:
    """Lazy-load and cache feeder configurations.

    Returns:
        Dictionary of all feeder configurations, cached after first load.
    """
    global _FEEDER_CONFIGS

    if _FEEDER_CONFIGS is None:
        config_path = os.path.join(os.path.dirname(__file__), FEEDER_CONFIG_FILE)
        _FEEDER_CONFIGS = load_feeder_configs(config_path)

    return _FEEDER_CONFIGS


def score_candidate(candidate: LinkedInCandidate, target_role: str) -> ScoringResult:
    """Score a candidate against a target role using feeder patterns.

    Scoring is based on multiple factors:
    - Company and tenure match (primary signal)
    - Job title match
    - Keyword presence in description
    - Required skills coverage
    - Nice-to-have skills
    - Negative signals (avoid companies, job hopping)

    Args:
        candidate: The candidate to score.
        target_role: The role name to score against (must exist in feeder configs).

    Returns:
        ScoringResult containing score, breakdown, and matched feeder.

    Raises:
        ValueError: If target_role doesn't exist in configurations.
    """
    feeder_configs = get_feeder_configs()

    if target_role not in feeder_configs:
        raise ValueError(
            f"Unknown target role: '{target_role}'. "
            f"Available roles: {list(feeder_configs.keys())}"
        )

    role_config = feeder_configs[target_role]
    total_score = 0
    breakdown = {}
    matched_feeder_name = None

    # Score feeder pattern match (company, tenure, title, keywords)
    feeder_score, feeder_breakdown, feeder_name = _score_feeder_match(
        candidate, role_config
    )
    total_score += feeder_score
    breakdown.update(feeder_breakdown)
    matched_feeder_name = feeder_name

    # Score required skills
    required_score, required_breakdown = _score_required_skills(
        candidate, role_config
    )
    total_score += required_score
    breakdown.update(required_breakdown)

    # Score nice-to-have skills
    nice_score, nice_breakdown = _score_nice_to_have_skills(
        candidate, role_config
    )
    total_score += nice_score
    breakdown.update(nice_breakdown)

    # Apply negative signals
    negative_score, negative_breakdown = _apply_negative_signals(
        candidate, role_config
    )
    total_score += negative_score
    breakdown.update(negative_breakdown)

    return ScoringResult(
        score=max(0, total_score),
        breakdown=breakdown,
        matched_feeder=matched_feeder_name
    )


def _score_feeder_match(
    candidate: LinkedInCandidate,
    role_config: RoleFeederConfig
) -> Tuple[int, Dict, Optional[str]]:
    """Score candidate based on feeder pattern matching.

    Includes company/tenure match, title match bonus, and keyword boosts.

    Args:
        candidate: The candidate to score.
        role_config: Role configuration with feeder patterns.

    Returns:
        Tuple of (score, breakdown_dict, matched_feeder_name).
    """
    score = 0
    breakdown = {}
    matched_feeder = None

    for feeder in role_config.feeders:
        if not company_matches(candidate.current_company, feeder):
            continue

        tenure_years = calculate_tenure(candidate.current_start_date)

        if not (feeder.min_tenure_years <= tenure_years <= feeder.max_tenure_years):
            continue

        # Company and tenure match
        score += feeder.score_boost
        breakdown["feeder_match"] = f"{feeder.company} ({tenure_years:.1f}y)"
        matched_feeder = feeder.company

        # Title match bonus
        if feeder.required_titles and candidate.current_title:
            if any(
                title.lower() in candidate.current_title.lower()
                for title in feeder.required_titles
            ):
                score += 10
                breakdown["title_match"] = True

        # Keyword boost
        description = (candidate.current_description or "").lower()
        matched_keywords = [
            keyword
            for keyword in feeder.boost_keywords
            if keyword.lower() in description
        ]
        if matched_keywords:
            keyword_score = min(len(matched_keywords) * 5, 15)
            score += keyword_score
            breakdown["keywords_matched"] = matched_keywords

        break  # Only match one feeder

    return score, breakdown, matched_feeder


def _score_required_skills(
    candidate: LinkedInCandidate,
    role_config: RoleFeederConfig
) -> Tuple[int, Dict]:
    """Score candidate based on required skills coverage.

    Args:
        candidate: The candidate to score.
        role_config: Role configuration with required skills.

    Returns:
        Tuple of (score, breakdown_dict).
    """
    score = 0
    breakdown = {}

    candidate_skills = {skill.name.lower() for skill in candidate.skills}
    required_matched = [
        skill
        for skill in role_config.required_skills
        if skill.lower() in candidate_skills
    ]

    if len(required_matched) == len(role_config.required_skills):
        score += 20
        breakdown["all_required_skills"] = True
    else:
        missing_count = len(role_config.required_skills) - len(required_matched)
        score -= missing_count * 5
        breakdown["missing_required_skills"] = missing_count

    return score, breakdown


def _score_nice_to_have_skills(
    candidate: LinkedInCandidate,
    role_config: RoleFeederConfig
) -> Tuple[int, Dict]:
    """Score candidate based on nice-to-have skills.

    Args:
        candidate: The candidate to score.
        role_config: Role configuration with optional skills.

    Returns:
        Tuple of (score, breakdown_dict).
    """
    score = 0
    breakdown = {}

    candidate_skills = {skill.name.lower() for skill in candidate.skills}
    nice_to_have_matched = [
        skill
        for skill in role_config.nice_to_have_skills
        if skill.lower() in candidate_skills
    ]

    if nice_to_have_matched:
        score += len(nice_to_have_matched) * 3
        breakdown["nice_to_have_matched"] = nice_to_have_matched

    return score, breakdown


def _apply_negative_signals(
    candidate: LinkedInCandidate,
    role_config: RoleFeederConfig
) -> Tuple[int, Dict]:
    """Apply penalties for negative signals.

    Includes avoid companies and job hopping penalties.

    Args:
        candidate: The candidate to score.
        role_config: Role configuration with negative signals.

    Returns:
        Tuple of (score_adjustment, breakdown_dict).
    """
    score = 0
    breakdown = {}

    # Avoid companies penalty
    if candidate.current_company in role_config.avoid_companies:
        score -= 20
        breakdown["avoid_company"] = True

    # Job hopping penalty
    if len(candidate.experience) >= 3:
        average_tenure = calculate_average_tenure(candidate.experience)
        if average_tenure < 1.5:
            score -= 15
            breakdown["job_hopper"] = average_tenure

    return score, breakdown


def company_matches(candidate_company: str, feeder: FeederPattern) -> bool:
    """Check if candidate's company matches the feeder company or its aliases.

    Args:
        candidate_company: The company name from the candidate's profile.
        feeder: The feeder pattern containing company name and aliases.

    Returns:
        True if the candidate's company matches, False otherwise.
    """
    candidate_lower = candidate_company.lower().strip()

    all_companies = [feeder.company] + feeder.company_aliases

    for company_name in all_companies:
        company_lower = company_name.lower().strip()
        if candidate_lower == company_lower or company_lower in candidate_lower:
            return True

    return False


def calculate_tenure(start_date: Optional[DateInfo]) -> float:
    """Calculate years of tenure from start date to present.

    Args:
        start_date: The start date containing year and optional month, or None.

    Returns:
        Years of tenure as a float. Returns 0.0 if start_date is None or has no year.
    """
    if not start_date or not start_date.year:
        return 0.0

    month_num = MONTH_NAME_TO_NUMBER.get(start_date.month, 1) if start_date.month else 1

    current = datetime.now()
    start = datetime(start_date.year, month_num, 1)

    days = (current - start).days
    return days / DAYS_PER_YEAR


def calculate_average_tenure(experiences: List[Experience]) -> float:
    """Calculate average tenure across all work experiences.

    Args:
        experiences: List of work experience entries.

    Returns:
        Average tenure in years. Returns 0.0 if no valid durations found.
    """
    tenures = []
    for experience in experiences:
        if experience.duration:
            years = parse_duration_to_years(experience.duration)
            if years > 0:
                tenures.append(years)

    return sum(tenures) / len(tenures) if tenures else 0.0


def parse_duration_to_years(duration: str) -> float:
    """Parse LinkedIn duration string to years using regex.

    Handles various formats robustly:
    - "2 yrs 3 mos" -> 2.25
    - "6 mos" -> 0.5
    - "1 yr" -> 1.0
    - "3 years 2 months" -> 3.17

    Args:
        duration: Duration string from LinkedIn profile.

    Returns:
        Duration in years as a float. Returns 0.0 if parsing fails.
    """
    if not duration:
        return 0.0

    years = 0.0

    # Match year patterns: "2 yrs", "2 years", "1 yr", "1 year"
    year_match = re.search(r'(\d+)\s*(?:yrs?|years?)', duration, re.IGNORECASE)
    if year_match:
        years += float(year_match.group(1))

    # Match month patterns: "3 mos", "3 months", "3 mo", "3 month"
    month_match = re.search(r'(\d+)\s*(?:mos?|months?)', duration, re.IGNORECASE)
    if month_match:
        years += float(month_match.group(1)) / MONTHS_PER_YEAR

    return years
