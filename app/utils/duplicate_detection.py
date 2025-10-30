"""Utility functions for detecting duplicate candidates."""

from datetime import datetime
from typing import List, Optional

from app.models.candidate import Experience
from app.repositories.company_repository import CompanyRepository


def companies_match(
    company_a: str,
    company_b: str,
    company_repository: CompanyRepository
) -> bool:
    """Check if two company names match, including aliases.

    Args:
        company_a: First company name.
        company_b: Second company name.
        company_repository: Repository to check company aliases.

    Returns:
        True if companies match (exact or via aliases).
    """
    a = company_a.lower().strip()
    b = company_b.lower().strip()

    # Exact match
    if a == b:
        return True

    # Check if either company has aliases that match the other
    company_a_record = company_repository.find_by_name_or_alias(company_a)
    company_b_record = company_repository.find_by_name_or_alias(company_b)

    # If both found and have same ID, they're the same company
    if company_a_record and company_b_record:
        return company_a_record["id"] == company_b_record["id"]

    # Check if company_b matches any alias of company_a
    if company_a_record:
        aliases = [alias.lower() for alias in company_a_record.get("aliases", [])]
        if b in aliases or company_a_record["name"].lower() == b:
            return True

    # Check if company_a matches any alias of company_b
    if company_b_record:
        aliases = [alias.lower() for alias in company_b_record.get("aliases", [])]
        if a in aliases or company_b_record["name"].lower() == a:
            return True

    return False


def titles_match(title_a: str, title_b: str) -> bool:
    """Check if two job titles match exactly (case-insensitive).

    Args:
        title_a: First job title.
        title_b: Second job title.

    Returns:
        True if titles match.
    """
    return title_a.lower().strip() == title_b.lower().strip()


def previous_experience_matches(
    new_prev_exp: List[Experience],
    existing_prev_exp: List[Experience],
    company_repository: CompanyRepository
) -> bool:
    """Check if overlapping previous positions match exactly.

    Handles both cases:
    - New profile has MORE old positions (added details)
    - New profile has FEWER old positions (cleaned up)

    Match requires: same company AND same title for overlapping positions

    Args:
        new_prev_exp: Previous experience from new profile (excluding current).
        existing_prev_exp: Previous experience from existing profile (excluding current).
        company_repository: Repository to check company aliases.

    Returns:
        True if all overlapping positions match.
    """
    # Compare up to the shorter list length
    overlap_length = min(len(new_prev_exp), len(existing_prev_exp))

    if overlap_length == 0:
        return False  # No overlap to compare

    # Check each overlapping position
    for i in range(overlap_length):
        new_exp = new_prev_exp[i]
        existing_exp = existing_prev_exp[i]

        company_match = companies_match(
            new_exp.company.name,
            existing_exp.company.name,
            company_repository
        )
        title_match = titles_match(new_exp.title, existing_exp.title)

        if not (company_match and title_match):
            return False  # Mismatch → manual review

    return True  # All overlapping positions match
