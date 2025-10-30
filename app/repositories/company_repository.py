"""Repository for company data access operations."""

from typing import Dict, List, Optional, Any

from supabase import Client


class CompanyRepository:
    """Repository for managing company data persistence.

    Encapsulates all database operations for companies, providing
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

    def create(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new company into the database.

        Args:
            company_data: Dictionary containing company information.

        Returns:
            Dictionary containing the inserted company record.

        Raises:
            Exception: If insertion fails (e.g., duplicate name).
        """
        try:
            response = self.db_client.table("companies").insert(company_data).execute()
            return response.data[0] if response.data else {}
        except Exception as error:
            raise Exception(f"Failed to create company: {str(error)}")

    def get_by_id(self, company_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a company by its ID.

        Args:
            company_id: The unique identifier of the company.

        Returns:
            Company record as dictionary if found, None otherwise.
        """
        try:
            response = (
                self.db_client.table("companies")
                .select("*")
                .eq("id", company_id)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as error:
            raise Exception(f"Failed to get company by ID: {str(error)}")

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve a company by its name.

        Args:
            name: The company name (case-insensitive).

        Returns:
            Company record as dictionary if found, None otherwise.
        """
        try:
            response = (
                self.db_client.table("companies")
                .select("*")
                .ilike("name", name)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as error:
            raise Exception(f"Failed to get company by name: {str(error)}")

    def get_all(self) -> List[Dict[str, Any]]:
        """Retrieve all companies from the database.

        Returns:
            List of company records as dictionaries.
        """
        try:
            response = (
                self.db_client.table("companies")
                .select("*")
                .order("name")
                .execute()
            )
            return response.data
        except Exception as error:
            raise Exception(f"Failed to get all companies: {str(error)}")

    def update(self, company_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update a company with new data.

        Args:
            company_id: The unique identifier of the company.
            updates: Dictionary of fields to update.

        Returns:
            Updated company record.

        Raises:
            Exception: If update fails or company not found.
        """
        try:
            response = (
                self.db_client.table("companies")
                .update(updates)
                .eq("id", company_id)
                .execute()
            )

            if not response.data:
                raise Exception(f"Company with ID {company_id} not found")

            return response.data[0]
        except Exception as error:
            raise Exception(f"Failed to update company: {str(error)}")

    def delete(self, company_id: str) -> bool:
        """Delete a company from the database.

        Args:
            company_id: The unique identifier of the company.

        Returns:
            True if deletion was successful.

        Raises:
            Exception: If deletion fails.
        """
        try:
            response = (
                self.db_client.table("companies")
                .delete()
                .eq("id", company_id)
                .execute()
            )
            return True
        except Exception as error:
            raise Exception(f"Failed to delete company: {str(error)}")

    def search_by_name_or_alias(self, search_term: str) -> List[Dict[str, Any]]:
        """Find companies by name or any alias.

        Searches both the name field and the aliases array.

        Args:
            search_term: Term to search for (e.g., "SIG", "Susquehanna").

        Returns:
            List of matching company records.
        """
        try:
            # Search by name (case-insensitive)
            name_results = (
                self.db_client.table("companies")
                .select("*")
                .ilike("name", f"%{search_term}%")
                .execute()
            )

            # Search by alias (contains in array)
            # Note: Supabase/PostgreSQL array contains is case-sensitive
            # For case-insensitive, we'd need a custom query
            alias_results = (
                self.db_client.table("companies")
                .select("*")
                .contains("aliases", [search_term])
                .execute()
            )

            # Combine and deduplicate results
            all_results = name_results.data + alias_results.data
            seen_ids = set()
            unique_results = []

            for company in all_results:
                if company["id"] not in seen_ids:
                    seen_ids.add(company["id"])
                    unique_results.append(company)

            return unique_results

        except Exception as error:
            raise Exception(f"Failed to search companies: {str(error)}")

    def update_metrics(
        self,
        company_id: str,
        candidates_sent: int,
        placements: int,
        placement_rate: float
    ) -> Dict[str, Any]:
        """Update company metrics (called by feedback loop).

        Args:
            company_id: The unique identifier of the company.
            candidates_sent: Total candidates sent to this company.
            placements: Total successful placements.
            placement_rate: Calculated placement rate (placements / sent).

        Returns:
            Updated company record.

        Raises:
            Exception: If update fails.
        """
        try:
            updates = {
                "total_candidates_sent": candidates_sent,
                "total_placements": placements,
                "placement_rate": round(placement_rate, 4)
            }

            return self.update(company_id, updates)

        except Exception as error:
            raise Exception(f"Failed to update company metrics: {str(error)}")
