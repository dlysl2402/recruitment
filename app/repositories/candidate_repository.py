"""Repository for candidate data access operations."""

import json
from typing import Dict, Optional, Set, Any, List

from supabase import Client

from app.models import LinkedInCandidate
from app.transformers.scraper_to_database import db_row_to_candidate


class CandidateRepository:
    """Repository for managing candidate data persistence.

    Encapsulates all database operations for candidates, providing
    a clean interface for data access without exposing database details.

    Attributes:
        db_client: Supabase client instance for database operations.
    """

    def __init__(self, db_client: Client):
        """Initialize the repository with a database client.

        Args:
            db_client: Supabase client instance.
        """
        self.db_client = db_client

    def insert(self, candidate_data: Dict[str, Any]):
        """Insert a new candidate into the database.

        Args:
            candidate_data: Dictionary containing candidate information matching
                the database schema.

        Returns:
            Supabase response object containing the inserted record.

        Raises:
            Exception: If insertion fails (e.g., duplicate linkedin_url).
        """
        return self.db_client.table("candidates").insert(candidate_data).execute()

    def get_all(self) -> List[Dict[str, Any]]:
        """Retrieve all candidates from the database.

        Returns:
            List of candidate records as dictionaries.

        Note:
            This loads all candidates into memory. Consider pagination for
            large datasets.
        """
        response = self.db_client.table("candidates").select("*").execute()
        return response.data

    def get_by_id(self, candidate_id: str) -> Optional[LinkedInCandidate]:
        """Retrieve a single candidate by their database ID.

        Args:
            candidate_id: The unique identifier of the candidate.

        Returns:
            LinkedInCandidate object if found, None otherwise.
        """
        response = (
            self.db_client.table("candidates")
            .select("*")
            .eq("id", candidate_id)
            .limit(1)
            .execute()
        )

        if not response.data:
            return None

        database_row = response.data[0]
        return db_row_to_candidate(database_row)

    def get_with_filters(
        self,
        filters: Optional[Dict[str, str]] = None,
        skills: Optional[Set[str]] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve candidates matching specified filters.

        Args:
            filters: Dictionary of field-value pairs for case-insensitive matching.
                Example: {"current_company": "Amazon"}
            skills: Set of skill names (lowercase) to filter by. Candidates must
                have all specified skills.

        Returns:
            List of candidate records matching the filters.

        Note:
            Multiple skills are combined with AND logic (all must match).
        """
        query = self.db_client.table("candidates").select("*")

        if filters:
            for field, value in filters.items():
                query = query.ilike(field, f"%{value}%")

        if skills:
            for skill in skills:
                # Filter JSONB array for objects with matching name
                query = query.filter("skills", "cs", json.dumps([{"name": skill}]))

        response = query.execute()
        return response.data
