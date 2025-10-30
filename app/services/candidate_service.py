"""Service for candidate CRUD operations."""

from typing import List, Dict, Set, Optional, Any

from app.models import LinkedInCandidate, PlacementRecord
from app.repositories.candidate_repository import CandidateRepository


class CandidateService:
    """Service for managing candidate data.

    Provides business logic layer for candidate CRUD operations.

    Attributes:
        candidate_repository: Repository for candidate data access.
    """

    def __init__(self, candidate_repository: CandidateRepository):
        """Initialize the candidate service.

        Args:
            candidate_repository: Repository for candidate operations.
        """
        self.candidate_repository = candidate_repository

    def create_candidate(self, candidate: LinkedInCandidate) -> Dict[str, Any]:
        """Create a new candidate in the database.

        Args:
            candidate: LinkedInCandidate object to create.

        Returns:
            Dictionary with success message and candidate ID.

        Raises:
            ValueError: If candidate creation fails or duplicate exists.
        """
        result = self.candidate_repository.insert(candidate.dict())

        if not result.data:
            raise ValueError("Failed to insert candidate")

        return {
            "message": "Candidate added",
            "id": result.data[0]["id"]
        }

    def get_candidate_by_id(self, candidate_id: str) -> LinkedInCandidate:
        """Retrieve a candidate by ID.

        Args:
            candidate_id: Database ID of the candidate.

        Returns:
            LinkedInCandidate object.

        Raises:
            ValueError: If candidate not found.
        """
        candidate = self.candidate_repository.get_by_id(candidate_id)

        if candidate is None:
            raise ValueError(f"Candidate with ID '{candidate_id}' not found")

        return candidate

    def get_all_candidates(self) -> List[Dict[str, Any]]:
        """Get all candidates from database.

        Returns:
            List of candidate records.
        """
        return self.candidate_repository.get_all()

    def filter_candidates(
        self,
        current_company: Optional[str] = None,
        skills: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Filter candidates by criteria.

        Args:
            current_company: Company name to filter by.
            skills: Comma-separated skill names.

        Returns:
            List of dictionaries with filtered candidates and matched skills.
        """
        query_filters = {}
        if current_company:
            query_filters["current_company"] = current_company

        requested_skills = None
        if skills:
            requested_skills = {
                skill.strip().lower()
                for skill in skills.split(",")
                if skill.strip()
            }

        candidate_data_list = self.candidate_repository.get_with_filters(
            filters=query_filters,
            skills=requested_skills
        )

        filtered_candidates = []
        for candidate_data in candidate_data_list:
            candidate_skills = candidate_data.get("skills", [])

            # Extract skill names from JSONB array
            candidate_skill_names = {
                skill["name"].lower()
                for skill in candidate_skills
                if isinstance(skill, dict) and "name" in skill
            }

            # Find intersection of requested and candidate skills
            matched_skills = [
                skill
                for skill in requested_skills
                if skill in candidate_skill_names
            ] if requested_skills else []

            filtered_candidates.append({
                "first_name": candidate_data.get("first_name", ""),
                "last_name": candidate_data.get("last_name", ""),
                "linkedin_url": candidate_data.get("linkedin_url", ""),
                "matched_skills": matched_skills
            })

        return filtered_candidates

    def add_placement_to_history(
        self,
        candidate_id: str,
        placement: PlacementRecord
    ) -> LinkedInCandidate:
        """Add a placement record to candidate's placement history.

        Args:
            candidate_id: Database ID of the candidate.
            placement: PlacementRecord to add to history.

        Returns:
            Updated LinkedInCandidate object.

        Raises:
            ValueError: If candidate not found or update fails.
        """
        # Get current candidate
        candidate = self.candidate_repository.get_by_id(candidate_id)
        if not candidate:
            raise ValueError(f"Candidate with ID '{candidate_id}' not found")

        # Add placement to history
        candidate.placement_history.append(placement)

        # Update in database
        update_data = {"placement_history": [p.dict() for p in candidate.placement_history]}

        try:
            response = (
                self.candidate_repository.db_client.table("candidates")
                .update(update_data)
                .eq("id", candidate_id)
                .execute()
            )

            if not response.data:
                raise ValueError(f"Failed to update candidate {candidate_id}")

            # Return updated candidate
            return self.candidate_repository.get_by_id(candidate_id)

        except Exception as error:
            raise ValueError(f"Failed to add placement to history: {str(error)}")
