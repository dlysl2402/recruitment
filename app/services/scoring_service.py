"""Service for candidate scoring operations."""

from typing import List, Optional

from app.models import LinkedInCandidate
from app.scoring import score_candidate, ScoringResult
from app.repositories.candidate_repository import CandidateRepository
from app.transformers.scraper_to_database import db_row_to_candidate


class ScoringService:
    """Service for scoring candidates against role requirements.

    Encapsulates scoring business logic and coordinates between
    repository and scoring algorithm.

    Attributes:
        candidate_repository: Repository for candidate data access.
    """

    def __init__(self, candidate_repository: CandidateRepository):
        """Initialize the scoring service.

        Args:
            candidate_repository: Repository for accessing candidate data.
        """
        self.candidate_repository = candidate_repository

    def score_single_candidate(
        self,
        candidate_id: str,
        target_role: str
    ) -> tuple[LinkedInCandidate, ScoringResult]:
        """Score a single candidate for a target role.

        Args:
            candidate_id: Database ID of the candidate.
            target_role: Name of the role to score against.

        Returns:
            Tuple of (candidate, scoring_result).

        Raises:
            ValueError: If candidate not found or role invalid.
        """
        candidate = self.candidate_repository.get_by_id(candidate_id)

        if candidate is None:
            raise ValueError(f"Candidate with ID '{candidate_id}' not found")

        scoring_result = score_candidate(candidate, target_role)

        return candidate, scoring_result

    def get_top_candidates_for_role(
        self,
        target_role: str,
        num_candidates: int,
        country: Optional[str] = None
    ) -> List[tuple[LinkedInCandidate, ScoringResult]]:
        """Score all candidates and return top N for a role.

        Args:
            target_role: Name of the role to score against.
            num_candidates: Number of top candidates to return.
            country: Optional country filter (case-insensitive).

        Returns:
            List of (candidate, scoring_result) tuples sorted by score.

        Raises:
            ValueError: If num_candidates invalid or role invalid.
        """
        if num_candidates <= 0:
            raise ValueError("num_candidates must be greater than 0")

        all_profiles = self.candidate_repository.get_all()

        scored_candidates = []

        for raw_candidate in all_profiles:
            candidate = db_row_to_candidate(raw_candidate)

            # Filter by country if specified
            if country:
                candidate_country = candidate.location.country if candidate.location else None
                if not candidate_country or candidate_country.lower() != country.lower():
                    continue

            scoring_result = score_candidate(candidate, target_role)
            scored_candidates.append((candidate, scoring_result))

        # Sort by score descending
        sorted_candidates = sorted(
            scored_candidates,
            key=lambda x: x[1].score,
            reverse=True
        )

        return sorted_candidates[:num_candidates]
