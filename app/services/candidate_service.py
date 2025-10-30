"""Service for candidate CRUD operations."""

from typing import List, Dict, Set, Optional, Any, TYPE_CHECKING, Tuple

from app.models import LinkedInCandidate, PlacementRecord
from app.repositories.candidate_repository import CandidateRepository
from app.utils.duplicate_detection import previous_experience_matches

# Avoid circular import
if TYPE_CHECKING:
    from app.services.company_service import CompanyService


class CandidateService:
    """Service for managing candidate data.

    Provides business logic layer for candidate CRUD operations.

    Attributes:
        candidate_repository: Repository for candidate data access.
        company_service: Optional CompanyService for auto-matching companies.
    """

    def __init__(
        self,
        candidate_repository: CandidateRepository,
        company_service: Optional["CompanyService"] = None
    ):
        """Initialize the candidate service.

        Args:
            candidate_repository: Repository for candidate operations.
            company_service: Optional CompanyService for auto-matching companies.
        """
        self.candidate_repository = candidate_repository
        self.company_service = company_service

    def create_candidate(self, candidate: LinkedInCandidate) -> Dict[str, Any]:
        """Create a new candidate in the database.

        Auto-matches companies in experience and current_company to existing
        companies in the database (by name or alias) if company_service is configured.

        Args:
            candidate: LinkedInCandidate object to create.

        Returns:
            Dictionary with success message and candidate ID.

        Raises:
            ValueError: If candidate creation fails or duplicate exists.
        """
        # Auto-match companies if company_service is available
        if self.company_service:
            # Match current_company
            if candidate.current_company:
                candidate.current_company = self.company_service.match_company_reference_no_create(
                    candidate.current_company
                )

            # Match all experience companies
            for experience in candidate.experience:
                experience.company = self.company_service.match_company_reference_no_create(
                    experience.company
                )

        result = self.candidate_repository.insert(candidate.model_dump())

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

    def delete_candidate(self, candidate_id: str) -> Dict[str, Any]:
        """Delete a candidate by ID.

        Args:
            candidate_id: Database ID of the candidate to delete.

        Returns:
            Dictionary with success message.

        Raises:
            ValueError: If candidate not found or deletion fails.
        """
        # Verify candidate exists first
        candidate = self.candidate_repository.get_by_id(candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate with ID '{candidate_id}' not found")

        # Delete the candidate
        self.candidate_repository.delete(candidate_id)

        return {
            "message": "Candidate deleted successfully",
            "id": candidate_id
        }

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
        update_data = {"placement_history": [p.model_dump() for p in candidate.placement_history]}

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

    def find_potential_duplicates(
        self,
        candidate: LinkedInCandidate
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Find potential duplicate candidates by name and experience match.

        Checks for candidates with matching name. If found, compares previous
        experience (excluding current position). If previous experience matches,
        returns the ID for auto-update. Otherwise, returns all name matches
        for manual review.

        Args:
            candidate: LinkedInCandidate to check for duplicates.

        Returns:
            Tuple of (auto_match_id, manual_review_candidates):
                - auto_match_id: ID of exact match found (None if no match)
                - manual_review_candidates: List of potential duplicates for review

        Raises:
            ValueError: If company_service not configured.
        """
        if not self.company_service:
            raise ValueError("Company service required for duplicate detection")

        # Search for candidates with same name
        full_name = f"{candidate.first_name} {candidate.last_name}".strip()
        name_matches = self.candidate_repository.get_with_filters(
            filters={"first_name": candidate.first_name, "last_name": candidate.last_name}
        )

        if not name_matches:
            return None, []

        # Extract previous experience (skip current position at index 0)
        new_prev_exp = candidate.experience[1:] if len(candidate.experience) > 1 else []

        auto_match_id = None
        manual_review = []

        for match in name_matches:
            # Get full candidate object
            existing_candidate = self.candidate_repository.get_by_id(match["id"])
            if not existing_candidate:
                continue

            # Extract previous experience
            existing_prev_exp = (
                existing_candidate.experience[1:]
                if len(existing_candidate.experience) > 1
                else []
            )

            # Check if previous experience matches
            if previous_experience_matches(
                new_prev_exp,
                existing_prev_exp,
                self.company_service.company_repository
            ):
                # Found exact match - return for auto-update
                auto_match_id = match["id"]
                break

            # Add to manual review list
            manual_review.append({
                "id": match["id"],
                "name": f"{match.get('first_name', '')} {match.get('last_name', '')}".strip(),
                "current_company": match.get("current_company", {}).get("name", "Unknown"),
                "current_title": (
                    existing_candidate.experience[0].title
                    if existing_candidate.experience
                    else "Unknown"
                ),
                "previous_experience": [
                    {
                        "company": exp.company.name,
                        "title": exp.title,
                        "start_date": exp.start_date.model_dump() if exp.start_date else None,
                        "end_date": exp.end_date.model_dump() if exp.end_date else None
                    }
                    for exp in existing_prev_exp[:3]  # Show up to 3 previous positions
                ]
            })

        return auto_match_id, manual_review

    def merge_candidate(
        self,
        existing_id: str,
        new_candidate: LinkedInCandidate
    ) -> Dict[str, Any]:
        """Merge new candidate data into existing candidate record.

        Updates the existing candidate with new current position and appends
        any new previous experience entries.

        Args:
            existing_id: Database ID of existing candidate.
            new_candidate: New candidate data to merge.

        Returns:
            Dictionary with success message and updated candidate ID.

        Raises:
            ValueError: If existing candidate not found or update fails.
        """
        # Get existing candidate
        existing_candidate = self.candidate_repository.get_by_id(existing_id)
        if not existing_candidate:
            raise ValueError(f"Candidate with ID '{existing_id}' not found")

        # Auto-match companies if company_service is available
        if self.company_service:
            if new_candidate.current_company:
                new_candidate.current_company = self.company_service.match_company_reference_no_create(
                    new_candidate.current_company
                )
            for experience in new_candidate.experience:
                experience.company = self.company_service.match_company_reference_no_create(
                    experience.company
                )

        # Update current company and position
        update_data = {
            "current_company": new_candidate.current_company.model_dump(),
            "headline": new_candidate.headline or existing_candidate.headline,
            "location": new_candidate.location.model_dump() if new_candidate.location else None,
        }

        # Merge experience: replace with new experience (includes current + all previous)
        update_data["experience"] = [exp.model_dump() for exp in new_candidate.experience]

        # Update education, skills, certifications if provided
        if new_candidate.education:
            update_data["education"] = [edu.model_dump() for edu in new_candidate.education]
        if new_candidate.skills:
            update_data["skills"] = [skill.model_dump() for skill in new_candidate.skills]
        if new_candidate.certifications:
            update_data["certifications"] = [cert.model_dump() for cert in new_candidate.certifications]

        try:
            response = (
                self.candidate_repository.db_client.table("candidates")
                .update(update_data)
                .eq("id", existing_id)
                .execute()
            )

            if not response.data:
                raise ValueError(f"Failed to update candidate {existing_id}")

            return {
                "message": "Candidate merged successfully",
                "id": existing_id
            }

        except Exception as error:
            raise ValueError(f"Failed to merge candidate: {str(error)}")
