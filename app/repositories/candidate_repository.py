"""Repository for candidate data access operations."""

import json
from typing import Dict, Optional, Set, Any, List

from supabase import Client

from app.models import LinkedInCandidate
from app.transformers.scraper_to_database import db_row_to_candidate
from app.repositories.base_repository import BaseRepository


class CandidateRepository(BaseRepository):
    """Repository for managing candidate data persistence.

    Extends BaseRepository to provide candidate-specific operations
    while inheriting common CRUD functionality.

    Attributes:
        db_client: Supabase client instance for database operations.
        table_name: Set to "candidates" for this repository.
    """

    def __init__(self, db_client: Client):
        """Initialize the repository with a database client.

        Args:
            db_client: Supabase client instance.
        """
        super().__init__(db_client, "candidates")

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
        return self.db_client.table(self.table_name).insert(candidate_data).execute()

    def get_by_id(self, candidate_id: str) -> Optional[LinkedInCandidate]:
        """Retrieve a single candidate by their database ID.

        Args:
            candidate_id: The unique identifier of the candidate.

        Returns:
            LinkedInCandidate object if found, None otherwise.
        """
        # Use inherited get_by_id() and convert to LinkedInCandidate
        database_row = super().get_by_id(candidate_id)

        if not database_row:
            return None

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
            JSONB fields (current_company) are filtered on nested properties.
        """
        query = self.db_client.table(self.table_name).select("*")

        if filters:
            for field, value in filters.items():
                # Handle JSONB fields specially
                if field == "current_company":
                    # Filter on the 'name' property inside the JSONB object
                    query = query.ilike("current_company->>name", f"%{value}%")
                else:
                    # Regular text field filtering
                    query = query.ilike(field, f"%{value}%")

        if skills:
            for skill in skills:
                # Filter JSONB array for objects with matching name
                query = query.filter("skills", "cs", json.dumps([{"name": skill}]))

        response = query.execute()
        return response.data

    def get_by_name(self, first_name: str, last_name: str) -> List[Dict[str, Any]]:
        """Retrieve candidates by full name (case-insensitive).

        Args:
            first_name: Candidate's first name.
            last_name: Candidate's last name.

        Returns:
            List of candidate records matching the name.
        """
        response = (
            self.db_client.table(self.table_name)
            .select("*")
            .ilike("first_name", first_name)
            .ilike("last_name", last_name)
            .execute()
        )
        return response.data
