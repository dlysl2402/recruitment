"""Repository for interview data access operations."""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from supabase import Client


class InterviewRepository:
    """Repository for managing interview process and stage data persistence.

    Encapsulates all database operations for interviews, providing
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

    # Interview Process Methods

    def create_interview_process(self, interview_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new interview process into the database.

        Args:
            interview_data: Dictionary containing interview process information.
                Should include: candidate_id, company_name, role_title, status,
                and optional fields like feeder_source, recruiter_name.

        Returns:
            Dictionary containing the inserted interview process record.

        Raises:
            Exception: If insertion fails.
        """
        try:
            # Ensure offer_details is properly serialized as JSONB
            if interview_data.get("offer_details"):
                interview_data["offer_details"] = json.dumps(interview_data["offer_details"])

            response = self.db_client.table("interview_processes").insert(interview_data).execute()
            return response.data[0] if response.data else {}
        except Exception as error:
            raise Exception(f"Failed to create interview process: {str(error)}")

    def get_interview_by_id(self, interview_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single interview process by its ID.

        Args:
            interview_id: The unique identifier of the interview process.

        Returns:
            Interview process record as dictionary if found, None otherwise.
        """
        try:
            response = (
                self.db_client.table("interview_processes")
                .select("*")
                .eq("id", interview_id)
                .limit(1)
                .execute()
            )

            if not response.data:
                return None

            interview = response.data[0]

            # Parse JSONB offer_details if present
            if interview.get("offer_details") and isinstance(interview["offer_details"], str):
                interview["offer_details"] = json.loads(interview["offer_details"])

            return interview
        except Exception as error:
            raise Exception(f"Failed to get interview by ID: {str(error)}")

    def get_interviews_by_candidate(self, candidate_id: str) -> List[Dict[str, Any]]:
        """Retrieve all interview processes for a specific candidate.

        Args:
            candidate_id: The candidate's unique identifier.

        Returns:
            List of interview process records for the candidate.
        """
        try:
            response = (
                self.db_client.table("interview_processes")
                .select("*")
                .eq("candidate_id", candidate_id)
                .order("created_at", desc=True)
                .execute()
            )

            interviews = response.data

            # Parse JSONB fields
            for interview in interviews:
                if interview.get("offer_details") and isinstance(interview["offer_details"], str):
                    interview["offer_details"] = json.loads(interview["offer_details"])

            return interviews
        except Exception as error:
            raise Exception(f"Failed to get interviews by candidate: {str(error)}")

    def get_all_interviews(self) -> List[Dict[str, Any]]:
        """Retrieve all interview processes ordered by creation date.

        Returns:
            List of all interview process records, sorted newest first.
        """
        try:
            response = (
                self.db_client.table("interview_processes")
                .select("*")
                .order("created_at", desc=True)
                .execute()
            )
            return response.data if response.data else []
        except Exception as error:
            raise Exception(f"Failed to retrieve interviews: {str(error)}")

    def get_interviews_by_company(self, company_name: str) -> List[Dict[str, Any]]:
        """Retrieve all interview processes for a specific company.

        Args:
            company_name: The company name to filter by.

        Returns:
            List of interview process records for the company.
        """
        try:
            response = (
                self.db_client.table("interview_processes")
                .select("*")
                .eq("company_name", company_name)
                .order("created_at", desc=True)
                .execute()
            )

            interviews = response.data

            # Parse JSONB fields
            for interview in interviews:
                if interview.get("offer_details") and isinstance(interview["offer_details"], str):
                    interview["offer_details"] = json.loads(interview["offer_details"])

            return interviews
        except Exception as error:
            raise Exception(f"Failed to get interviews by company: {str(error)}")

    def update_interview(self, interview_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an interview process with new data.

        Args:
            interview_id: The unique identifier of the interview process.
            updates: Dictionary of fields to update.

        Returns:
            Updated interview process record.

        Raises:
            Exception: If update fails or interview not found.
        """
        try:
            # Auto-update the updated_at timestamp
            updates["updated_at"] = datetime.now().isoformat()

            # Handle JSONB serialization for offer_details
            if "offer_details" in updates and updates["offer_details"]:
                updates["offer_details"] = json.dumps(updates["offer_details"])

            response = (
                self.db_client.table("interview_processes")
                .update(updates)
                .eq("id", interview_id)
                .execute()
            )

            if not response.data:
                raise Exception(f"Interview process with ID {interview_id} not found")

            interview = response.data[0]

            # Parse JSONB offer_details if present
            if interview.get("offer_details") and isinstance(interview["offer_details"], str):
                interview["offer_details"] = json.loads(interview["offer_details"])

            return interview
        except Exception as error:
            raise Exception(f"Failed to update interview: {str(error)}")

    # Interview Stage Methods

    def create_interview_stage(self, stage_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new interview stage into the database.

        Args:
            stage_data: Dictionary containing stage information.
                Should include: interview_process_id, stage_name, stage_order,
                and optional fields like scheduled_date, outcome, ratings.

        Returns:
            Dictionary containing the inserted stage record.

        Raises:
            Exception: If insertion fails.
        """
        try:
            response = self.db_client.table("interview_stages").insert(stage_data).execute()
            return response.data[0] if response.data else {}
        except Exception as error:
            raise Exception(f"Failed to create interview stage: {str(error)}")

    def get_stages_by_interview(self, interview_id: str) -> List[Dict[str, Any]]:
        """Retrieve all stages for a specific interview process.

        Args:
            interview_id: The interview process ID.

        Returns:
            List of stage records ordered by stage_order.
        """
        try:
            response = (
                self.db_client.table("interview_stages")
                .select("*")
                .eq("interview_process_id", interview_id)
                .order("stage_order")
                .execute()
            )

            return response.data
        except Exception as error:
            raise Exception(f"Failed to get stages by interview: {str(error)}")

    def get_stage_by_id(self, stage_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single interview stage by its ID.

        Args:
            stage_id: The unique identifier of the stage.

        Returns:
            Stage record as dictionary if found, None otherwise.
        """
        try:
            response = (
                self.db_client.table("interview_stages")
                .select("*")
                .eq("id", stage_id)
                .limit(1)
                .execute()
            )

            return response.data[0] if response.data else None
        except Exception as error:
            raise Exception(f"Failed to get stage by ID: {str(error)}")

    def update_stage(self, stage_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an interview stage with new data.

        Args:
            stage_id: The unique identifier of the stage.
            updates: Dictionary of fields to update.

        Returns:
            Updated stage record.

        Raises:
            Exception: If update fails or stage not found.
        """
        try:
            response = (
                self.db_client.table("interview_stages")
                .update(updates)
                .eq("id", stage_id)
                .execute()
            )

            if not response.data:
                raise Exception(f"Interview stage with ID {stage_id} not found")

            return response.data[0]
        except Exception as error:
            raise Exception(f"Failed to update stage: {str(error)}")
