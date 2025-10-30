"""Service for job management and business logic."""

from typing import List, Dict, Optional, Any
from datetime import date

from app.repositories.job_repository import JobRepository
from app.models.job import JobStatus


class JobService:
    """Service for managing jobs with business logic.

    Attributes:
        job_repository: Repository for job data access.
    """

    def __init__(self, job_repository: JobRepository):
        """Initialize the service with a repository.

        Args:
            job_repository: JobRepository instance.
        """
        self.job_repository = job_repository

    def create_job(
        self,
        company_id: str,
        role_title: str,
        department: Optional[str] = None,
        location: Optional[str] = None,
        internal_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new job.

        Args:
            company_id: ID of company posting this job.
            role_title: Job title/position.
            department: Department or team.
            location: Job location.
            internal_notes: Internal notes.

        Returns:
            Created job record.

        Raises:
            ValueError: If required fields missing.
        """
        if not company_id or not role_title:
            raise ValueError("company_id and role_title are required")

        job_data = {
            "company_id": company_id,
            "role_title": role_title,
            "department": department,
            "location": location,
            "status": JobStatus.OPEN.value,
            "total_candidates_submitted": 0,
            "total_interviews_started": 0,
            "internal_notes": internal_notes
        }

        return self.job_repository.create(job_data)

    def get_job(self, job_id: str) -> Dict[str, Any]:
        """Get a job by ID.

        Args:
            job_id: Job UUID.

        Returns:
            Job record.

        Raises:
            ValueError: If job not found.
        """
        job = self.job_repository.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job with ID {job_id} not found")
        return job

    def list_jobs(self, company_id: Optional[str] = None, status: Optional[JobStatus] = None) -> List[Dict[str, Any]]:
        """List jobs with optional filters.

        Args:
            company_id: Filter by company.
            status: Filter by status.

        Returns:
            List of job records.
        """
        status_value = status.value if status else None

        if company_id:
            return self.job_repository.get_by_company(company_id, status_value)
        else:
            return self.job_repository.get_all(status_value)

    def update_job(self, job_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a job.

        Args:
            job_id: Job UUID.
            updates: Dictionary of fields to update.

        Returns:
            Updated job record.

        Raises:
            ValueError: If job not found or invalid data.
        """
        # Verify job exists
        job = self.job_repository.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job with ID {job_id} not found")

        # Don't allow updating metrics directly
        protected_fields = ["total_candidates_submitted", "total_interviews_started"]
        for field in protected_fields:
            if field in updates:
                raise ValueError(f"Cannot manually update {field}. Use feedback loop.")

        return self.job_repository.update(job_id, updates)

    def close_job(self, job_id: str, filled_by_candidate_id: Optional[str] = None) -> Dict[str, Any]:
        """Close a job (mark as filled or closed).

        Args:
            job_id: Job UUID.
            filled_by_candidate_id: ID of candidate who filled this position.

        Returns:
            Updated job record.
        """
        updates = {
            "status": JobStatus.FILLED.value if filled_by_candidate_id else JobStatus.CLOSED.value
        }

        if filled_by_candidate_id:
            updates["filled_by_candidate_id"] = filled_by_candidate_id
            updates["filled_date"] = date.today().isoformat()

        return self.job_repository.update(job_id, updates)

    def reopen_job(self, job_id: str) -> Dict[str, Any]:
        """Reopen a closed job.

        Args:
            job_id: Job UUID.

        Returns:
            Updated job record.
        """
        updates = {
            "status": JobStatus.OPEN.value,
            "filled_by_candidate_id": None,
            "filled_date": None
        }

        return self.job_repository.update(job_id, updates)

    def delete_job(self, job_id: str) -> bool:
        """Delete a job.

        Args:
            job_id: Job UUID.

        Returns:
            True if deletion successful.

        Raises:
            ValueError: If job not found.
        """
        # Verify job exists
        job = self.job_repository.get_by_id(job_id)
        if not job:
            raise ValueError(f"Job with ID {job_id} not found")

        return self.job_repository.delete(job_id)

    def update_metrics_from_interviews(
        self,
        job_id: str,
        total_submitted: int,
        total_started: int
    ) -> Dict[str, Any]:
        """Update job metrics based on interview data.

        Called by FeedbackService.

        Args:
            job_id: Job UUID.
            total_submitted: Total candidates submitted.
            total_started: Total interviews started.

        Returns:
            Updated job record.
        """
        return self.job_repository.update_metrics(
            job_id=job_id,
            candidates_submitted=total_submitted,
            interviews_started=total_started
        )
