"""Candidate scoring logic based on feeder patterns and role requirements."""

import os
import json
import re
from datetime import datetime
from typing import Dict, Optional, List, Set, Tuple
from dataclasses import dataclass, field

from app.models import LinkedInCandidate, DateInfo, Experience
from app.feeder_models import RoleFeederConfig, FeederPattern, PedigreeCompany
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
    - Career pedigree (prestigious company history)
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

    # Score career pedigree
    pedigree_score, pedigree_breakdown = _score_pedigree(
        candidate, role_config
    )
    total_score += pedigree_score
    breakdown.update(pedigree_breakdown)

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

        # Calculate consecutive tenure at current company (handles internal moves)
        tenure_years = calculate_consecutive_company_tenure(
            candidate.experience,
            candidate.current_company,
            feeder,
            candidate.current_start_date
        )

        if not (feeder.min_tenure_years <= tenure_years <= feeder.max_tenure_years):
            continue

        # Company and tenure match - calculate S-curve score
        base_score = calculate_pedigree_s_curve(tenure_years, feeder.multiplier)
        score += base_score
        breakdown["feeder_match"] = f"{feeder.company} ({tenure_years:.1f}y, +{base_score})"
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
    """Score candidate based on weighted required skills coverage.

    Uses weighted coverage: if candidate has 80% of weighted skills,
    they get 80% of max points (16/20). Higher weight skills have more impact.

    Args:
        candidate: The candidate to score.
        role_config: Role configuration with weighted required skills.

    Returns:
        Tuple of (score, breakdown_dict).
    """
    score = 0
    breakdown = {}

    if not role_config.required_skills:
        return score, breakdown

    candidate_skills = {skill.name.lower() for skill in candidate.skills}

    # Calculate total weight and matched weight
    total_weight = sum(skill.weight for skill in role_config.required_skills)
    matched_weight = 0.0
    matched_skills = []
    missing_skills = []

    for skill in role_config.required_skills:
        if skill.name.lower() in candidate_skills:
            matched_weight += skill.weight
            matched_skills.append(f"{skill.name} (w:{skill.weight})")
        else:
            missing_skills.append(f"{skill.name} (w:{skill.weight})")

    # Calculate coverage percentage and score
    coverage = matched_weight / total_weight if total_weight > 0 else 0.0
    score = int(coverage * 20)  # Max 20 points

    breakdown["required_skills_coverage"] = f"{coverage*100:.1f}%"
    if matched_skills:
        breakdown["matched_required_skills"] = matched_skills
    if missing_skills:
        breakdown["missing_required_skills"] = missing_skills

    return score, breakdown


def _score_nice_to_have_skills(
    candidate: LinkedInCandidate,
    role_config: RoleFeederConfig
) -> Tuple[int, Dict]:
    """Score candidate based on weighted nice-to-have skills.

    Each matched skill contributes points equal to its weight.
    Higher weight skills are worth more points.

    Args:
        candidate: The candidate to score.
        role_config: Role configuration with weighted optional skills.

    Returns:
        Tuple of (score, breakdown_dict).
    """
    score = 0
    breakdown = {}

    if not role_config.nice_to_have_skills:
        return score, breakdown

    candidate_skills = {skill.name.lower() for skill in candidate.skills}
    matched_skills = []

    for skill in role_config.nice_to_have_skills:
        if skill.name.lower() in candidate_skills:
            score += int(skill.weight)
            matched_skills.append(f"{skill.name} (+{skill.weight:.1f})")

    if matched_skills:
        breakdown["nice_to_have_matched"] = matched_skills

    return score, breakdown


def _score_pedigree(
    candidate: LinkedInCandidate,
    role_config: RoleFeederConfig
) -> Tuple[int, Dict]:
    """Score candidate based on career pedigree from prestigious companies.

    Iterates through all work experiences and awards points using S-curve
    based on tenure at prestigious companies. Multiple companies stack.

    S-curve rewards commitment:
    - 0-3 years: No points (too early to exit)
    - 3-5 years: Slow growth (proving commitment)
    - 5-9 years: Fast exponential growth (proven performers)
    - 9-15 years: Slow growth (diminishing returns)
    - 15+ years: Capped at max points

    Title relevance is validated if relevant_title_keywords is configured.
    Only awards points if the title at that company was relevant to the role.

    Args:
        candidate: The candidate to score.
        role_config: Role configuration with pedigree companies and title keywords.

    Returns:
        Tuple of (score, breakdown_dict).
    """
    score = 0
    breakdown = {}

    if not role_config.pedigree_companies:
        return score, breakdown

    pedigree_details = []

    # Group consecutive experiences by company to avoid double-counting overlapping roles
    processed_companies = set()

    for i, experience in enumerate(candidate.experience):
        for pedigree_company in role_config.pedigree_companies:
            # Check if this experience matches a pedigree company
            if company_matches(experience.company, pedigree_company):
                # Skip if we already processed this pedigree company
                company_key = pedigree_company.company.lower()
                if company_key in processed_companies:
                    break

                # Check title relevance if keywords are configured
                if role_config.relevant_title_keywords:
                    title_lower = (experience.title or "").lower()
                    title_relevant = any(
                        keyword.lower() in title_lower
                        for keyword in role_config.relevant_title_keywords
                    )
                    if not title_relevant:
                        # Skip this experience - title not relevant to role
                        break

                # Find all consecutive experiences at this pedigree company
                earliest_start = experience.start_date
                latest_end = experience.end_date

                # Look ahead for more consecutive roles at same company
                for j in range(i + 1, len(candidate.experience)):
                    next_exp = candidate.experience[j]
                    if company_matches(next_exp.company, pedigree_company):
                        # Update earliest/latest dates
                        if next_exp.start_date and earliest_start:
                            if _date_is_earlier(next_exp.start_date, earliest_start):
                                earliest_start = next_exp.start_date
                        if next_exp.end_date and latest_end:
                            if _date_is_later(next_exp.end_date, latest_end):
                                latest_end = next_exp.end_date
                        elif next_exp.end_date is None:
                            latest_end = None  # Currently employed
                    else:
                        # Hit different company, stop looking
                        break

                # Calculate total tenure from earliest to latest
                tenure_years = 0.0
                if earliest_start:
                    if latest_end is None:
                        # Currently employed
                        tenure_years = calculate_tenure(earliest_start)
                    else:
                        start_tenure = calculate_tenure(earliest_start)
                        end_tenure = calculate_tenure(latest_end)
                        tenure_years = abs(start_tenure - end_tenure)

                if tenure_years > 0:
                    # Calculate points using S-curve with company multiplier
                    points = calculate_pedigree_s_curve(
                        tenure_years,
                        pedigree_company.multiplier
                    )
                    score += points

                    # Add to breakdown with tenure and points
                    pedigree_details.append(
                        f"{pedigree_company.company} ({tenure_years:.1f}y, +{points})"
                    )

                    # Mark this company as processed
                    processed_companies.add(company_key)

                # Only match one pedigree company per experience
                break

    if pedigree_details:
        breakdown["pedigree_companies"] = pedigree_details

    return score, breakdown


def _apply_negative_signals(
    candidate: LinkedInCandidate,
    role_config: RoleFeederConfig
) -> Tuple[int, Dict]:
    """Apply penalties for negative signals.

    Includes avoid companies, avoid title keywords, and job hopping penalties.

    Args:
        candidate: The candidate to score.
        role_config: Role configuration with negative signals.

    Returns:
        Tuple of (score_adjustment, breakdown_dict).
    """
    score = 0
    breakdown = {}

    # Avoid companies penalty
    from app.models import CompanyReference
    current_company_name = candidate.current_company.name if isinstance(candidate.current_company, CompanyReference) else candidate.current_company
    if current_company_name and current_company_name in role_config.avoid_companies:
        score -= 20
        breakdown["avoid_company"] = True

    # Avoid title keywords penalty (non-hands-on roles)
    if candidate.current_title and role_config.avoid_title_keywords:
        current_title_lower = candidate.current_title.lower()
        matched_avoid_keywords = [
            keyword
            for keyword in role_config.avoid_title_keywords
            if keyword.lower() in current_title_lower
        ]
        if matched_avoid_keywords:
            score -= 1000
            breakdown["avoid_title_match"] = matched_avoid_keywords

    # Job hopping penalty
    if len(candidate.experience) >= 3:
        average_tenure = calculate_average_tenure(candidate.experience)
        if average_tenure < 1.5:
            score -= 15
            breakdown["job_hopper"] = average_tenure

    return score, breakdown


def company_matches(candidate_company, feeder: FeederPattern) -> bool:
    """Check if candidate's company matches the feeder company or its aliases.

    Args:
        candidate_company: The company from the candidate's profile (str or CompanyReference).
        feeder: The feeder pattern containing company name and aliases.

    Returns:
        True if the candidate's company matches, False otherwise.
    """
    # Handle CompanyReference objects (extract name) or plain strings
    from app.models import CompanyReference
    if isinstance(candidate_company, CompanyReference):
        candidate_name = candidate_company.name
    elif isinstance(candidate_company, str):
        candidate_name = candidate_company
    else:
        return False

    candidate_lower = candidate_name.lower().strip()

    all_companies = [feeder.company] + feeder.company_aliases

    for company_name in all_companies:
        company_lower = company_name.lower().strip()
        if candidate_lower == company_lower or company_lower in candidate_lower:
            return True

    return False


def calculate_pedigree_s_curve(tenure_years: float, multiplier: float = 1.0) -> int:
    """Calculate pedigree points using S-curve based on tenure.

    S-curve design:
    - 0-3 years: 0 points (too early to exit, no signal)
    - 3-5 years: Slow linear growth (0 to 8 points, proving commitment)
    - 5-9 years: Fast exponential growth (8 to 40 points, proven performer)
    - 9-15 years: Slow logarithmic growth (40 to 50 points, diminishing returns)
    - 15+ years: Capped at 50 points

    Args:
        tenure_years: Years of tenure at the company.
        multiplier: Company prestige multiplier (1.0 for top tier, 0.8-0.9 for high tier).

    Returns:
        Pedigree points as integer.

    Examples:
        >>> calculate_pedigree_s_curve(2.5, 1.0)
        0  # Too early
        >>> calculate_pedigree_s_curve(4.0, 1.0)
        4  # Slow growth phase
        >>> calculate_pedigree_s_curve(8.0, 1.0)
        36  # Fast growth phase
        >>> calculate_pedigree_s_curve(15.0, 1.0)
        50  # Capped
        >>> calculate_pedigree_s_curve(8.0, 0.8)
        29  # High tier company (80% of 36)
    """
    if tenure_years < 3.0:
        # Too early to exit - no signal
        base_points = 0.0

    elif tenure_years < 5.0:
        # Years 3-5: Slow linear growth (0 to 8 points)
        progress = (tenure_years - 3.0) / 2.0  # 0.0 to 1.0
        base_points = progress * 8.0

    elif tenure_years < 9.0:
        # Years 5-9: Fast exponential growth (8 to 40 points)
        years_in_range = tenure_years - 5.0  # 0.0 to 4.0
        progress = years_in_range / 4.0  # 0.0 to 1.0
        # Exponential curve: 8 + (32 * progress^1.5)
        base_points = 8.0 + (32.0 * (progress ** 1.5))

    elif tenure_years <= 15.0:
        # Years 9-15: Slow logarithmic growth (40 to 50 points)
        years_in_range = tenure_years - 9.0  # 0.0 to 6.0
        progress = years_in_range / 6.0  # 0.0 to 1.0
        # Logarithmic slow growth: 40 + (10 * sqrt(progress))
        base_points = 40.0 + (10.0 * (progress ** 0.5))

    else:
        # Cap at 15 years
        base_points = 50.0

    return int(base_points * multiplier)


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


def calculate_consecutive_company_tenure(
    experiences: List[Experience],
    current_company: str,
    feeder: FeederPattern,
    fallback_start_date: Optional[DateInfo] = None
) -> float:
    """Calculate tenure for current consecutive stint at company.

    Tracks earliest start date and latest end date across consecutive roles
    at the same company to handle promotions/role changes without double-counting.

    This handles internal moves, promotions, and transfers within the same
    company without counting previous stints at the same company after gaps.

    Args:
        experiences: List of work experience entries (sorted newest first).
        current_company: The candidate's current company name.
        feeder: Feeder pattern with company name and aliases for matching.
        fallback_start_date: Fallback to single date calculation if no durations.

    Returns:
        Total consecutive years at current company. Returns 0.0 if no valid data.

    Examples:
        >>> # Candidate worked at Amazon 1yr, then Amazon 2yrs (consecutive)
        >>> calculate_consecutive_company_tenure(experiences, "Amazon", feeder)
        3.0  # Counts both roles

        >>> # Candidate worked at Amazon 5yr, left for Telstra 10yr, back to Amazon 1yr
        >>> calculate_consecutive_company_tenure(experiences, "Amazon", feeder)
        1.0  # Only counts current stint
    """
    if not experiences:
        # No experience data, fall back to start date calculation
        return calculate_tenure(fallback_start_date)

    # Track earliest start and latest end across consecutive roles at same company
    earliest_start: Optional[DateInfo] = None
    latest_end: Optional[DateInfo] = None
    found_matching_experiences = False

    for experience in experiences:
        # Check if this experience is at the current company
        if company_matches(experience.company, feeder):
            found_matching_experiences = True

            # Track earliest start date
            if experience.start_date:
                if earliest_start is None:
                    earliest_start = experience.start_date
                else:
                    # Compare dates to find earliest
                    if _date_is_earlier(experience.start_date, earliest_start):
                        earliest_start = experience.start_date

            # Track latest end date (None = present, which is latest)
            if experience.end_date is None:
                latest_end = None  # Currently employed
            elif latest_end is not None:
                # Both have end dates, compare them
                if _date_is_later(experience.end_date, latest_end):
                    latest_end = experience.end_date
            # If latest_end is None (already at present), keep it as None
        else:
            # Hit a different company - stop counting
            if found_matching_experiences:
                break

    # Calculate tenure from earliest start to latest end (or present)
    if earliest_start:
        if latest_end is None:
            # Currently employed - calculate from start to now
            return calculate_tenure(earliest_start)
        else:
            # Calculate span between earliest start and latest end
            start_tenure = calculate_tenure(earliest_start)
            end_tenure = calculate_tenure(latest_end)
            return abs(start_tenure - end_tenure)

    # If no valid experience data found, fall back to start date
    if not found_matching_experiences:
        return calculate_tenure(fallback_start_date)

    return 0.0


def _date_is_earlier(date1: DateInfo, date2: DateInfo) -> bool:
    """Check if date1 is earlier than date2."""
    if date1.year != date2.year:
        return date1.year < date2.year
    # Same year, compare months if available
    if date1.month and date2.month:
        from app.constants import MONTH_NAME_TO_NUMBER
        return MONTH_NAME_TO_NUMBER.get(date1.month, 1) < MONTH_NAME_TO_NUMBER.get(date2.month, 1)
    return False


def _date_is_later(date1: DateInfo, date2: DateInfo) -> bool:
    """Check if date1 is later than date2."""
    if date1.year != date2.year:
        return date1.year > date2.year
    # Same year, compare months if available
    if date1.month and date2.month:
        from app.constants import MONTH_NAME_TO_NUMBER
        return MONTH_NAME_TO_NUMBER.get(date1.month, 1) > MONTH_NAME_TO_NUMBER.get(date2.month, 1)
    return False


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
