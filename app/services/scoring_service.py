"""Service for candidate scoring operations."""

from typing import List, Optional

from app.models import LinkedInCandidate
from app.scoring import score_candidate, ScoringResult, score_candidate_with_config
from app.repositories.candidate_repository import CandidateRepository
from app.transformers.scraper_to_database import db_row_to_candidate
from app.utils.config_manager import ConfigManager


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

    def score_candidate_for_firm(
        self,
        candidate_id: str,
        target_role: str,
        firm_name: str,
        general_weight: float = 0.6,
    ) -> tuple[LinkedInCandidate, ScoringResult]:
        """Score a candidate using weighted combination of general + firm-specific feeders.

        This method combines general feeders (universal patterns) with firm-specific
        feeders (patterns unique to target firm) using a weighted average.

        Args:
            candidate_id: Database ID of the candidate.
            target_role: Name of the role to score against.
            firm_name: Target HFT firm (e.g., "Citadel", "Jane Street").
            general_weight: Weight for general score (0.0-1.0), default 0.6.
                           Firm weight = 1.0 - general_weight.

        Returns:
            Tuple of (candidate, weighted_scoring_result).

        Raises:
            ValueError: If candidate not found, role invalid, or weights invalid.
            FileNotFoundError: If general or firm-specific config not found.

        Example:
            >>> service.score_candidate_for_firm("123", "network_engineer", "Citadel")
            (candidate, ScoringResult(score=85.5, breakdown={...}))
        """
        # Validate weights
        if not 0.0 <= general_weight <= 1.0:
            raise ValueError("general_weight must be between 0.0 and 1.0")

        firm_weight = 1.0 - general_weight

        # Fetch candidate
        candidate = self.candidate_repository.get_by_id(candidate_id)
        if candidate is None:
            raise ValueError(f"Candidate with ID '{candidate_id}' not found")

        # Load both general and firm-specific configs
        general_config, firm_config = ConfigManager.load_combined_feeders(
            target_role, firm_name
        )

        # Require at least one config to be available
        if general_config is None and firm_config is None:
            raise ValueError(
                f"No feeder configs found for role '{target_role}'. "
                f"Run optimization to generate configs."
            )

        # Score with general feeders (if available)
        general_score = 0
        general_breakdown = {}
        if general_config:
            general_result = score_candidate_with_config(candidate, general_config)
            general_score = general_result.score
            general_breakdown = {
                f"general_{k}": v for k, v in general_result.breakdown.items()
            }

        # Score with firm-specific feeders (if available)
        firm_score = 0
        firm_breakdown = {}
        if firm_config:
            firm_result = score_candidate_with_config(candidate, firm_config)
            firm_score = firm_result.score
            firm_breakdown = {
                f"firm_{k}": v for k, v in firm_result.breakdown.items()
            }

        # Calculate weighted score
        if general_config and firm_config:
            # Both configs available - use weighted average
            weighted_score = (general_score * general_weight) + (firm_score * firm_weight)
            matched_feeder = f"Combined (Gen: {general_result.matched_feeder}, Firm: {firm_result.matched_feeder})"
        elif general_config:
            # Only general config available
            weighted_score = general_score
            matched_feeder = f"General only: {general_result.matched_feeder}"
        else:
            # Only firm config available
            weighted_score = firm_score
            matched_feeder = f"Firm-specific only: {firm_result.matched_feeder}"

        # Combine breakdowns with metadata
        combined_breakdown = {
            **general_breakdown,
            **firm_breakdown,
            "general_score": general_score,
            "firm_score": firm_score,
            "general_weight": general_weight,
            "firm_weight": firm_weight,
            "weighted_score": round(weighted_score, 2),
        }

        # Create weighted scoring result
        weighted_result = ScoringResult(
            score=round(weighted_score, 2),
            breakdown=combined_breakdown,
            matched_feeder=matched_feeder,
        )

        return candidate, weighted_result
