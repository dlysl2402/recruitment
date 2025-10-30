"""Repository for job data access operations."""

from typing import Dict, List, Optional, Any

from supabase import Client


class JobRepository:
    """Repository for managing job data persistence.

    Attributes:
        db_client: Supabase client instance for database operations.
    """

    def __init__(self, db_client: Client):
        """Initialize the repository with a database client.

        Args:
            db_client: Supabase client instance.
        """
        self.db_client = db_client

    def create(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new job into the database.

        Args:
            job_data: Dictionary containing job information.

        Returns:
            Dictionary containing the inserted job record.

        Raises:
            Exception: If insertion fails.
        """
        try:
            response = self.db_client.table("jobs").insert(job_data).execute()
            return response.data[0] if response.data else {}
        except Exception as error:
            raise Exception(f"Failed to create job: {str(error)}")

    def get_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a job by its ID.

        Args:
            job_id: The unique identifier of the job.

        Returns:
            Job record as dictionary if found, None otherwise.
        """
        try:
            response = (
                self.db_client.table("jobs")
                .select("*")
                .eq("id", job_id)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as error:
            raise Exception(f"Failed to get job by ID: {str(error)}")

    def get_by_company(self, company_id: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all jobs for a specific company.

        Args:
            company_id: The company's unique identifier.
            status: Optional status filter.

        Returns:
            List of job records for the company.
        """
        try:
            query = (
                self.db_client.table("jobs")
                .select("*")
                .eq("company_id", company_id)
            )

            if status:
                query = query.eq("status", status)

            response = query.order("created_at", desc=True).execute()
            return response.data
        except Exception as error:
            raise Exception(f"Failed to get jobs by company: {str(error)}")

    def get_all(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all jobs from the database.

        Args:
            status: Optional status filter.

        Returns:
            List of job records.
        """
        try:
            query = self.db_client.table("jobs").select("*")

            if status:
                query = query.eq("status", status)

            response = query.order("created_at", desc=True).execute()
            return response.data
        except Exception as error:
            raise Exception(f"Failed to get all jobs: {str(error)}")

    def update(self, job_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a job with new data.

        Args:
            job_id: The unique identifier of the job.
            updates: Dictionary of fields to update.

        Returns:
            Updated job record.

        Raises:
            Exception: If update fails or job not found.
        """
        try:
            response = (
                self.db_client.table("jobs")
                .update(updates)
                .eq("id", job_id)
                .execute()
            )

            if not response.data:
                raise Exception(f"Job with ID {job_id} not found")

            return response.data[0]
        except Exception as error:
            raise Exception(f"Failed to update job: {str(error)}")

    def delete(self, job_id: str) -> bool:
        """Delete a job from the database.

        Args:
            job_id: The unique identifier of the job.

        Returns:
            True if deletion was successful.

        Raises:
            Exception: If deletion fails.
        """
        try:
            response = (
                self.db_client.table("jobs")
                .delete()
                .eq("id", job_id)
                .execute()
            )
            return True
        except Exception as error:
            raise Exception(f"Failed to delete job: {str(error)}")

    def update_metrics(
        self,
        job_id: str,
        candidates_submitted: int,
        interviews_started: int
    ) -> Dict[str, Any]:
        """Update job metrics (called by feedback loop).

        Args:
            job_id: The unique identifier of the job.
            candidates_submitted: Total candidates submitted.
            interviews_started: Total interviews started.

        Returns:
            Updated job record.

        Raises:
            Exception: If update fails.
        """
        try:
            updates = {
                "total_candidates_submitted": candidates_submitted,
                "total_interviews_started": interviews_started
            }

            return self.update(job_id, updates)

        except Exception as error:
            raise Exception(f"Failed to update job metrics: {str(error)}")
