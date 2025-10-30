"""Service layer for interview process management and business logic."""

from typing import List, Optional, Dict, Any, TYPE_CHECKING
from datetime import date, datetime

from app.repositories.interview_repository import InterviewRepository
from app.services.company_service import CompanyService
from app.services.job_service import JobService
from app.models.interview import (
    InterviewProcess,
    InterviewStage,
    InterviewStatus,
    StageOutcome,
    OfferDetails
)

# Avoid circular import
if TYPE_CHECKING:
    from app.services.feedback_service import FeedbackService


class InterviewService:
    """Service for managing interview processes with business logic.

    Handles interview lifecycle management, stage progression, status transitions,
    and data validation. Acts as the business layer between API and repository.

    Attributes:
        interview_repository: Repository for interview data access.
        company_service: CompanyService for company operations.
        job_service: JobService for job operations.
        feedback_service: Optional FeedbackService for processing outcomes.
    """

    def __init__(
        self,
        interview_repository: InterviewRepository,
        company_service: CompanyService,
        job_service: JobService,
        feedback_service: Optional["FeedbackService"] = None
    ):
        """Initialize the service with a repository.

        Args:
            interview_repository: InterviewRepository instance.
            company_service: CompanyService instance.
            job_service: JobService instance.
            feedback_service: Optional FeedbackService for feedback loop.
        """
        self.interview_repository = interview_repository
        self.company_service = company_service
        self.job_service = job_service
        self.feedback_service = feedback_service

    def create_interview_process(
        self,
        candidate_id: str,
        company_name: str,
        role_title: str,
        feeder_source: Optional[str] = None,
        recruiter_name: Optional[str] = None
    ) -> InterviewProcess:
        """Create a new interview process for a candidate.

        Args:
            candidate_id: ID of the candidate being interviewed.
            company_name: Company conducting the interview.
            role_title: Position being interviewed for.
            feeder_source: Which feeder pattern sourced this candidate.
            recruiter_name: Name of recruiter managing this process.

        Returns:
            InterviewProcess object with the created interview.

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        if not candidate_id or not company_name or not role_title:
            raise ValueError("candidate_id, company_name, and role_title are required")

        # Find or create company
        company = self.company_service.find_or_create_company(company_name)

        # Find or create job
        job = self.job_service.create_job(
            company_id=company["id"],
            role_title=role_title
        )

        interview_data = {
            "candidate_id": candidate_id,
            "company_id": company["id"],
            "company_name": company_name,
            "job_id": job["id"],
            "role_title": role_title,
            "status": InterviewStatus.IN_PROGRESS.value,
            "feeder_source": feeder_source,
            "recruiter_name": recruiter_name
        }

        result = self.interview_repository.create_interview_process(interview_data)
        return self._dict_to_interview_process(result)

    def add_interview_stage(
        self,
        interview_id: str,
        stage_name: str,
        stage_order: int,
        scheduled_date: Optional[date] = None
    ) -> InterviewStage:
        """Add a new stage to an interview process.

        Args:
            interview_id: ID of the interview process.
            stage_name: Name of the stage (e.g., "phone_screen", "technical", "onsite").
            stage_order: Order in the interview process (1, 2, 3...).
            scheduled_date: When the stage is scheduled.

        Returns:
            InterviewStage object with the created stage.

        Raises:
            ValueError: If interview doesn't exist or stage_order invalid.
        """
        # Validate interview exists
        interview = self.interview_repository.get_interview_by_id(interview_id)
        if not interview:
            raise ValueError(f"Interview with ID {interview_id} not found")

        # Validate stage_order is sequential
        existing_stages = self.interview_repository.get_stages_by_interview(interview_id)
        if existing_stages:
            max_order = max(stage["stage_order"] for stage in existing_stages)
            if stage_order != max_order + 1 and stage_order not in [s["stage_order"] for s in existing_stages]:
                raise ValueError(
                    f"stage_order must be sequential. Expected {max_order + 1}, got {stage_order}"
                )

        stage_data = {
            "interview_process_id": interview_id,
            "stage_name": stage_name,
            "stage_order": stage_order,
            "scheduled_date": scheduled_date.isoformat() if scheduled_date else None,
            "outcome": StageOutcome.PENDING.value
        }

        result = self.interview_repository.create_interview_stage(stage_data)
        return self._dict_to_interview_stage(result)

    def update_stage_outcome(
        self,
        stage_id: str,
        outcome: StageOutcome,
        ratings: Optional[Dict[str, int]] = None,
        feedback: Optional[str] = None,
        interviewer_names: Optional[List[str]] = None,
        next_steps: Optional[str] = None
    ) -> InterviewStage:
        """Update the outcome and feedback for an interview stage.

        Args:
            stage_id: ID of the stage to update.
            outcome: Result of this stage (pass, fail, pending, etc.).
            ratings: Dictionary with keys: overall_rating, technical_rating,
                culture_fit_rating, communication_rating (values 1-5).
            feedback: Detailed feedback notes from interviewers.
            interviewer_names: List of interviewer names.
            next_steps: Action items or next steps.

        Returns:
            Updated InterviewStage object.

        Raises:
            ValueError: If stage not found or ratings invalid.
        """
        # Validate stage exists
        stage = self.interview_repository.get_stage_by_id(stage_id)
        if not stage:
            raise ValueError(f"Stage with ID {stage_id} not found")

        # Validate ratings if provided
        if ratings:
            for rating_key, rating_value in ratings.items():
                if rating_value is not None and (rating_value < 1 or rating_value > 5):
                    raise ValueError(f"{rating_key} must be between 1 and 5")

        updates = {
            "outcome": outcome.value,
            "completed_date": date.today().isoformat(),
            "feedback_notes": feedback
        }

        if ratings:
            updates.update({
                "overall_rating": ratings.get("overall_rating"),
                "technical_rating": ratings.get("technical_rating"),
                "culture_fit_rating": ratings.get("culture_fit_rating"),
                "communication_rating": ratings.get("communication_rating")
            })

        if interviewer_names:
            updates["interviewer_names"] = interviewer_names

        if next_steps:
            updates["next_steps"] = next_steps

        result = self.interview_repository.update_stage(stage_id, updates)

        # Auto-update interview process status based on stage outcome
        if outcome in [StageOutcome.FAIL, StageOutcome.NO_SHOW]:
            interview_id = stage["interview_process_id"]
            self.interview_repository.update_interview(
                interview_id,
                {"status": InterviewStatus.REJECTED_BY_COMPANY.value}
            )

        return self._dict_to_interview_stage(result)

    def complete_interview_process(
        self,
        interview_id: str,
        final_status: InterviewStatus,
        offer_details: Optional[OfferDetails] = None,
        final_outcome: Optional[str] = None
    ) -> InterviewProcess:
        """Complete an interview process and set final status.

        Args:
            interview_id: ID of the interview process.
            final_status: Final status (offer_extended, offer_accepted, etc.).
            offer_details: Details if offer was extended.
            final_outcome: Free-text description of final outcome.

        Returns:
            Updated InterviewProcess object.

        Raises:
            ValueError: If interview not found or status transition invalid.
        """
        # Validate interview exists
        interview = self.interview_repository.get_interview_by_id(interview_id)
        if not interview:
            raise ValueError(f"Interview with ID {interview_id} not found")

        # Validate status transition
        if final_status == InterviewStatus.IN_PROGRESS:
            raise ValueError("Cannot complete interview with status IN_PROGRESS")

        updates = {
            "status": final_status.value,
            "final_outcome": final_outcome
        }

        if offer_details:
            updates["offer_details"] = offer_details.model_dump()

        result = self.interview_repository.update_interview(interview_id, updates)

        # Trigger feedback loop if feedback_service is configured
        if self.feedback_service:
            try:
                self.feedback_service.process_interview_outcome(interview_id)
            except Exception as error:
                # Log error but don't fail the interview completion
                print(f"Warning: Feedback loop failed for interview {interview_id}: {error}")

        return self._dict_to_interview_process(result)

    def get_candidate_interview_history(
        self,
        candidate_id: str,
        include_stages: bool = True
    ) -> List[InterviewProcess]:
        """Get all interviews for a candidate with optional stage details.

        Args:
            candidate_id: ID of the candidate.
            include_stages: If True, includes all stages for each interview.

        Returns:
            List of InterviewProcess objects.
        """
        interviews = self.interview_repository.get_interviews_by_candidate(candidate_id)

        result = []
        for interview_dict in interviews:
            interview = self._dict_to_interview_process(interview_dict)

            if include_stages:
                stages = self.interview_repository.get_stages_by_interview(interview.id)
                interview.stages = [self._dict_to_interview_stage(s) for s in stages]

            result.append(interview)

        return result

    def get_company_interviews(
        self,
        company_name: str,
        status_filter: Optional[InterviewStatus] = None
    ) -> List[InterviewProcess]:
        """Get all interviews for a company with optional status filter.

        Args:
            company_name: Name of the company.
            status_filter: Optional status to filter by.

        Returns:
            List of InterviewProcess objects.
        """
        interviews = self.interview_repository.get_interviews_by_company(company_name)

        result = []
        for interview_dict in interviews:
            interview = self._dict_to_interview_process(interview_dict)

            # Apply status filter if specified
            if status_filter and interview.status != status_filter:
                continue

            result.append(interview)

        return result

    def get_interview_with_stages(self, interview_id: str) -> Optional[InterviewProcess]:
        """Get a complete interview process with all its stages.

        Args:
            interview_id: ID of the interview process.

        Returns:
            InterviewProcess object with stages, or None if not found.
        """
        interview_dict = self.interview_repository.get_interview_by_id(interview_id)
        if not interview_dict:
            return None

        interview = self._dict_to_interview_process(interview_dict)

        # Load stages
        stages = self.interview_repository.get_stages_by_interview(interview_id)
        interview.stages = [self._dict_to_interview_stage(s) for s in stages]

        return interview

    # Helper methods for converting between dicts and Pydantic models

    def _dict_to_interview_process(self, data: Dict[str, Any]) -> InterviewProcess:
        """Convert database dict to InterviewProcess model.

        Args:
            data: Dictionary from database.

        Returns:
            InterviewProcess Pydantic model.
        """
        # Convert offer_details dict to OfferDetails model
        offer_details = None
        if data.get("offer_details"):
            offer_data = data["offer_details"]
            if isinstance(offer_data, dict):
                offer_details = OfferDetails(**offer_data)

        return InterviewProcess(
            id=data.get("id"),
            candidate_id=data["candidate_id"],
            company_id=data.get("company_id"),
            company_name=data["company_name"],
            job_id=data.get("job_id"),
            role_title=data["role_title"],
            status=InterviewStatus(data["status"]),
            feeder_source=data.get("feeder_source"),
            recruiter_name=data.get("recruiter_name"),
            final_outcome=data.get("final_outcome"),
            offer_details=offer_details,
            stages=[],  # Populated separately if needed
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at")
        )

    def _dict_to_interview_stage(self, data: Dict[str, Any]) -> InterviewStage:
        """Convert database dict to InterviewStage model.

        Args:
            data: Dictionary from database.

        Returns:
            InterviewStage Pydantic model.
        """
        return InterviewStage(
            id=data.get("id"),
            interview_process_id=data.get("interview_process_id"),
            stage_name=data["stage_name"],
            stage_order=data["stage_order"],
            scheduled_date=data.get("scheduled_date"),
            completed_date=data.get("completed_date"),
            outcome=StageOutcome(data["outcome"]),
            overall_rating=data.get("overall_rating"),
            technical_rating=data.get("technical_rating"),
            culture_fit_rating=data.get("culture_fit_rating"),
            communication_rating=data.get("communication_rating"),
            feedback_notes=data.get("feedback_notes"),
            interviewer_names=data.get("interviewer_names", []),
            next_steps=data.get("next_steps"),
            created_at=data.get("created_at")
        )
