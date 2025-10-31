"""Repository for company data access operations."""

from typing import Dict, List, Optional, Any

from supabase import Client

from app.repositories.base_repository import BaseRepository


class CompanyRepository(BaseRepository):
    """Repository for managing company data persistence.

    Extends BaseRepository to provide company-specific operations
    while inheriting common CRUD functionality.

    Attributes:
        db_client: Supabase client instance for database operations.
        table_name: Set to "companies" for this repository.
    """

    def __init__(self, db_client: Client):
        """Initialize the repository with a database client.

        Args:
            db_client: Supabase client instance.
        """
        super().__init__(db_client, "companies")

    def get_all(self) -> List[Dict[str, Any]]:
        """Retrieve all companies from the database, ordered by name.

        Returns:
            List of company records as dictionaries, sorted alphabetically.
        """
        try:
            response = (
                self.db_client.table(self.table_name)
                .select("*")
                .order("name")
                .execute()
            )
            return response.data
        except Exception as error:
            raise Exception(f"Failed to get all companies: {str(error)}")

    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve a company by its name.

        Args:
            name: The company name (case-insensitive).

        Returns:
            Company record as dictionary if found, None otherwise.
        """
        try:
            response = (
                self.db_client.table(self.table_name)
                .select("*")
                .ilike("name", name)
                .limit(1)
                .execute()
            )
            return response.data[0] if response.data else None
        except Exception as error:
            raise Exception(f"Failed to get company by name: {str(error)}")

    def find_by_name_or_alias(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Find a company by exact name or alias match (case-insensitive).

        Used for auto-linking candidates to companies during import.

        Args:
            company_name: Exact company name to match (e.g., "Amazon", "AWS").

        Returns:
            Company record if found, None otherwise.
        """
        try:
            # First, try exact name match (case-insensitive)
            name_match = (
                self.db_client.table("companies")
                .select("*")
                .ilike("name", company_name)
                .limit(1)
                .execute()
            )

            if name_match.data:
                return name_match.data[0]

            # If no name match, check if it matches any alias
            # We need to fetch all companies and check aliases manually since
            # Supabase doesn't support case-insensitive array contains
            all_companies = self.get_all()

            for company in all_companies:
                aliases = company.get("aliases", [])
                if aliases:
                    # Case-insensitive check if company_name is in aliases
                    aliases_lower = [alias.lower() for alias in aliases]
                    if company_name.lower() in aliases_lower:
                        return company

            return None

        except Exception as error:
            raise Exception(f"Failed to find company by name or alias: {str(error)}")

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
        updates = {
            "total_candidates_sent": candidates_sent,
            "total_placements": placements,
            "placement_rate": round(placement_rate, 4)
        }

        # Use inherited update() method from BaseRepository
        return self.update(company_id, updates)
