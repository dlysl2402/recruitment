"""Database query functions for candidate operations."""

import json
from typing import Dict, Optional, Set, Any

from app.database.client import supabase
from app.helper.scraper_to_database import db_row_to_candidate
from app.models import LinkedInCandidate


def insert_candidate(candidate_data: Dict[str, Any]):
    """Insert a new candidate into the database.

    Args:
        candidate_data: Dictionary containing candidate information matching
            the database schema.

    Returns:
        Supabase response object containing the inserted record.

    Raises:
        Exception: If insertion fails (e.g., duplicate linkedin_url).
    """
    return supabase.table("candidates").insert(candidate_data).execute()


def get_all_candidates():
    """Retrieve all candidates from the database.

    Returns:
        Supabase response object containing all candidate records.

    Note:
        This loads all candidates into memory. Consider pagination for
        large datasets.
    """
    return supabase.table("candidates").select("*").execute()


def get_candidate_with_id(candidate_id: str) -> Optional[LinkedInCandidate]:
    """Retrieve a single candidate by their database ID.

    Args:
        candidate_id: The unique identifier of the candidate.

    Returns:
        LinkedInCandidate object if found, None otherwise.
    """
    response = (
        supabase.table("candidates")
        .select("*")
        .eq("id", candidate_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    database_row = response.data[0]
    return db_row_to_candidate(database_row)


def get_candidates_with_filters(
    filters: Optional[Dict[str, str]] = None,
    skills: Optional[Set[str]] = None
):
    """Retrieve candidates matching specified filters.

    Args:
        filters: Dictionary of field-value pairs for case-insensitive matching.
            Example: {"current_company": "Amazon"}
        skills: Set of skill names (lowercase) to filter by. Candidates must
            have all specified skills.

    Returns:
        Supabase response object containing matching candidate records.

    Note:
        Multiple skills are combined with AND logic (all must match).
    """
    query = supabase.table("candidates").select("*")

    if filters:
        for field, value in filters.items():
            query = query.ilike(field, f"%{value}%")

    if skills:
        for skill in skills:
            # Filter JSONB array for objects with matching name
            query = query.filter("skills", "cs", json.dumps([{"name": skill}]))

    return query.execute()
