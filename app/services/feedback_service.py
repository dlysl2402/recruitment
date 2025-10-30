"""Service for processing interview outcomes and updating feeder metrics."""

import json
from typing import Dict, Any, Optional
from datetime import date

from app.repositories.interview_repository import InterviewRepository
from app.services.candidate_service import CandidateService
from app.models.interview import InterviewStatus, InterviewProcess
from app.models.candidate import PlacementRecord


class FeedbackService:
    """Service for managing feedback loops between interviews and feeder metrics.

    Processes interview outcomes to update conversion rates, track placements,
    and feed learnings back into the scoring system.

    Attributes:
        interview_repository: Repository for interview data access.
        candidate_service: Service for candidate operations.
        feeders_file_path: Path to feeders.json configuration file.
    """

    def __init__(
        self,
        interview_repository: InterviewRepository,
        candidate_service: CandidateService,
        feeders_file_path: str = "app/feeders.json"
    ):
        """Initialize the feedback service.

        Args:
            interview_repository: InterviewRepository instance.
            candidate_service: CandidateService instance.
            feeders_file_path: Path to feeders.json file.
        """
        self.interview_repository = interview_repository
        self.candidate_service = candidate_service
        self.feeders_file_path = feeders_file_path

    def process_interview_outcome(self, interview_id: str) -> Dict[str, Any]:
        """Process interview outcome and update all relevant metrics.

        This is the main entry point for the feedback loop. When an interview
        reaches a terminal state (offer_accepted, rejected, etc.), this method:
        1. Updates feeder conversion rates if feeder_source is tracked
        2. Adds placement record to candidate history if offer accepted
        3. Returns metrics for logging/analysis

        Args:
            interview_id: ID of the completed interview process.

        Returns:
            Dictionary with updated metrics and processing results.

        Raises:
            ValueError: If interview not found.
        """
        # Get interview details
        interview_dict = self.interview_repository.get_interview_by_id(interview_id)
        if not interview_dict:
            raise ValueError(f"Interview with ID {interview_id} not found")

        # Only process terminal states
        terminal_states = [
            InterviewStatus.OFFER_ACCEPTED.value,
            InterviewStatus.REJECTED_BY_COMPANY.value,
            InterviewStatus.CANDIDATE_WITHDREW.value
        ]

        if interview_dict["status"] not in terminal_states:
            return {
                "processed": False,
                "reason": "Interview not in terminal state",
                "status": interview_dict["status"]
            }

        result = {
            "processed": True,
            "interview_id": interview_id,
            "status": interview_dict["status"],
            "updates": {}
        }

        # Update feeder conversion rates if feeder_source exists
        if interview_dict.get("feeder_source"):
            feeder_update = self.update_feeder_conversion_rates(
                interview_dict["feeder_source"]
            )
            result["updates"]["feeder"] = feeder_update

        # Add placement to candidate history if offer accepted
        if interview_dict["status"] == InterviewStatus.OFFER_ACCEPTED.value:
            placement_update = self._add_placement_to_candidate(interview_dict)
            result["updates"]["placement"] = placement_update

        return result

    def update_feeder_conversion_rates(self, feeder_source: str) -> Dict[str, Any]:
        """Calculate and update conversion rates for a feeder pattern.

        Queries all interviews with this feeder_source, calculates metrics,
        and updates the feeders.json file.

        Logic:
        1. Query all interviews with this feeder_source
        2. Count total interviews started (candidates_sourced)
        3. Count successful placements (status = offer_accepted)
        4. Calculate conversion_rate = placements / sourced
        5. Update feeders.json with new metrics

        Args:
            feeder_source: Name of the feeder pattern to update.

        Returns:
            Dictionary with updated metrics.

        Raises:
            ValueError: If feeder_source not found in feeders.json.
        """
        # Load current feeders config
        with open(self.feeders_file_path, 'r') as f:
            feeders_config = json.load(f)

        # Find the feeder pattern in the config
        feeder_pattern = None
        role_name = None

        for role_key, role_config in feeders_config.items():
            for feeder in role_config.get("feeders", []):
                # Match by company name (feeder_source might be "Amazon", "Google", etc.)
                if feeder["company"].lower() == feeder_source.lower():
                    feeder_pattern = feeder
                    role_name = role_key
                    break
            if feeder_pattern:
                break

        if not feeder_pattern:
            raise ValueError(f"Feeder source '{feeder_source}' not found in feeders.json")

        # Query all interviews for this feeder source
        # Note: This queries across all companies, filtered by feeder_source field
        # We need to query the database directly since we're filtering by feeder_source
        all_interviews = self._get_interviews_by_feeder_source(feeder_source)

        # Calculate metrics
        total_sourced = len(all_interviews)
        total_placed = sum(
            1 for interview in all_interviews
            if interview["status"] == InterviewStatus.OFFER_ACCEPTED.value
        )

        conversion_rate = (total_placed / total_sourced) if total_sourced > 0 else 0.0

        # Update the feeder pattern in the config
        feeder_pattern["candidates_sourced"] = total_sourced
        feeder_pattern["candidates_placed"] = total_placed
        feeder_pattern["conversion_rate"] = round(conversion_rate, 4)
        feeder_pattern["last_updated"] = date.today().isoformat()

        # Write updated config back to file
        with open(self.feeders_file_path, 'w') as f:
            json.dump(feeders_config, f, indent=2)

        return {
            "feeder_source": feeder_source,
            "role": role_name,
            "candidates_sourced": total_sourced,
            "candidates_placed": total_placed,
            "conversion_rate": conversion_rate
        }

    def get_feeder_performance_report(self, feeder_source: str) -> Dict[str, Any]:
        """Generate comprehensive performance report for a feeder.

        Args:
            feeder_source: Name of the feeder pattern.

        Returns:
            Dictionary with detailed performance metrics:
            - Total candidates sourced
            - Success rate by stage
            - Average time to hire
            - Common rejection reasons
        """
        all_interviews = self._get_interviews_by_feeder_source(feeder_source)

        if not all_interviews:
            return {
                "feeder_source": feeder_source,
                "total_candidates": 0,
                "message": "No interview data found for this feeder"
            }

        # Basic metrics
        total = len(all_interviews)
        placed = sum(1 for i in all_interviews if i["status"] == InterviewStatus.OFFER_ACCEPTED.value)
        rejected = sum(1 for i in all_interviews if i["status"] == InterviewStatus.REJECTED_BY_COMPANY.value)
        withdrew = sum(1 for i in all_interviews if i["status"] == InterviewStatus.CANDIDATE_WITHDREW.value)
        in_progress = sum(1 for i in all_interviews if i["status"] == InterviewStatus.IN_PROGRESS.value)

        # Stage analysis
        stage_outcomes = {}
        for interview in all_interviews:
            stages = self.interview_repository.get_stages_by_interview(interview["id"])
            for stage in stages:
                stage_name = stage["stage_name"]
                if stage_name not in stage_outcomes:
                    stage_outcomes[stage_name] = {"pass": 0, "fail": 0, "total": 0}

                stage_outcomes[stage_name]["total"] += 1
                if stage["outcome"] == "pass":
                    stage_outcomes[stage_name]["pass"] += 1
                elif stage["outcome"] == "fail":
                    stage_outcomes[stage_name]["fail"] += 1

        # Calculate pass rates per stage
        stage_performance = {}
        for stage_name, outcomes in stage_outcomes.items():
            if outcomes["total"] > 0:
                pass_rate = outcomes["pass"] / outcomes["total"]
                stage_performance[stage_name] = {
                    "total_interviews": outcomes["total"],
                    "pass_rate": round(pass_rate, 3),
                    "passes": outcomes["pass"],
                    "fails": outcomes["fail"]
                }

        return {
            "feeder_source": feeder_source,
            "total_candidates_sourced": total,
            "placement_rate": round(placed / total, 3) if total > 0 else 0,
            "outcomes": {
                "placed": placed,
                "rejected_by_company": rejected,
                "candidate_withdrew": withdrew,
                "in_progress": in_progress
            },
            "stage_performance": stage_performance
        }

    def _get_interviews_by_feeder_source(self, feeder_source: str) -> list:
        """Query all interviews for a specific feeder source.

        This is a helper method that queries the database directly.
        Since we need to filter by feeder_source across all companies,
        we use the Supabase client directly.

        Args:
            feeder_source: Name of the feeder pattern.

        Returns:
            List of interview dictionaries.
        """
        try:
            response = (
                self.interview_repository.db_client.table("interview_processes")
                .select("*")
                .eq("feeder_source", feeder_source)
                .execute()
            )
            return response.data
        except Exception as error:
            raise Exception(f"Failed to query interviews by feeder source: {str(error)}")

    def _add_placement_to_candidate(self, interview_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Add placement record to candidate's history.

        Args:
            interview_dict: Interview dictionary with placement details.

        Returns:
            Dictionary with placement update results.
        """
        try:
            # Extract offer details
            offer_details = interview_dict.get("offer_details", {})
            base_salary = offer_details.get("base_salary") if offer_details else None
            total_comp = offer_details.get("total_comp") if offer_details else None

            # Create placement record
            placement = PlacementRecord(
                company=interview_dict["company_name"],
                role=interview_dict["role_title"],
                placement_date=date.today(),
                base_salary=base_salary,
                total_comp=total_comp,
                feeder_source=interview_dict.get("feeder_source"),
                interview_id=interview_dict["id"]
            )

            # Add to candidate history
            self.candidate_service.add_placement_to_history(
                candidate_id=interview_dict["candidate_id"],
                placement=placement
            )

            return {
                "candidate_id": interview_dict["candidate_id"],
                "company": placement.company,
                "role": placement.role,
                "placement_date": placement.placement_date.isoformat()
            }

        except Exception as error:
            # Log error but don't fail the entire feedback loop
            return {
                "error": f"Failed to add placement to candidate: {str(error)}",
                "candidate_id": interview_dict.get("candidate_id")
            }
