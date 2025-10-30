"""Service for company management and business logic."""

from typing import List, Dict, Optional, Any

from app.repositories.company_repository import CompanyRepository
from app.models.candidate import CompanyReference


class CompanyService:
    """Service for managing companies with business logic.

    Provides business logic layer for company operations.

    Attributes:
        company_repository: Repository for company data access.
    """

    def __init__(self, company_repository: CompanyRepository):
        """Initialize the service with a repository.

        Args:
            company_repository: CompanyRepository instance.
        """
        self.company_repository = company_repository

    def create_company(
        self,
        name: str,
        aliases: Optional[List[str]] = None,
        industry: Optional[str] = None,
        headquarters_city: Optional[str] = None,
        headquarters_country: Optional[str] = None,
        internal_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new company.

        Args:
            name: Company name (required).
            aliases: Alternative names for the company.
            industry: Industry classification.
            headquarters_city: HQ city.
            headquarters_country: HQ country.
            internal_notes: Internal notes about the company.

        Returns:
            Created company record.

        Raises:
            ValueError: If name is empty or company already exists.
        """
        if not name or not name.strip():
            raise ValueError("Company name is required")

        # Check if company already exists
        existing = self.company_repository.get_by_name(name)
        if existing:
            raise ValueError(f"Company '{name}' already exists")

        company_data = {
            "name": name.strip(),
            "aliases": aliases or [],
            "industry": industry,
            "headquarters_city": headquarters_city,
            "headquarters_country": headquarters_country,
            "internal_notes": internal_notes,
            "total_candidates_sent": 0,
            "total_placements": 0,
            "placement_rate": 0.0
        }

        return self.company_repository.create(company_data)

    def get_company(self, company_id: str) -> Dict[str, Any]:
        """Get a company by ID.

        Args:
            company_id: Company UUID.

        Returns:
            Company record.

        Raises:
            ValueError: If company not found.
        """
        company = self.company_repository.get_by_id(company_id)
        if not company:
            raise ValueError(f"Company with ID {company_id} not found")
        return company

    def get_company_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a company by name.

        Args:
            name: Company name.

        Returns:
            Company record if found, None otherwise.
        """
        return self.company_repository.get_by_name(name)

    def list_companies(self) -> List[Dict[str, Any]]:
        """Get all companies.

        Returns:
            List of all company records.
        """
        return self.company_repository.get_all()

    def update_company(
        self,
        company_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update a company.

        Args:
            company_id: Company UUID.
            updates: Dictionary of fields to update.

        Returns:
            Updated company record.

        Raises:
            ValueError: If company not found or invalid data.
        """
        # Verify company exists
        company = self.company_repository.get_by_id(company_id)
        if not company:
            raise ValueError(f"Company with ID {company_id} not found")

        # Don't allow updating metrics directly (only via feedback loop)
        protected_fields = ["total_candidates_sent", "total_placements", "placement_rate"]
        for field in protected_fields:
            if field in updates:
                raise ValueError(f"Cannot manually update {field}. Use feedback loop.")

        return self.company_repository.update(company_id, updates)

    def delete_company(self, company_id: str) -> bool:
        """Delete a company.

        Args:
            company_id: Company UUID.

        Returns:
            True if deletion successful.

        Raises:
            ValueError: If company not found.
        """
        # Verify company exists
        company = self.company_repository.get_by_id(company_id)
        if not company:
            raise ValueError(f"Company with ID {company_id} not found")

        return self.company_repository.delete(company_id)

    def search_companies(self, search_term: str) -> List[Dict[str, Any]]:
        """Search companies by name or alias.

        Args:
            search_term: Term to search for (e.g., "SIG", "Citadel").

        Returns:
            List of matching company records.
        """
        if not search_term or not search_term.strip():
            return []

        return self.company_repository.search_by_name_or_alias(search_term.strip())

    def find_or_create_company(self, name: str) -> Dict[str, Any]:
        """Find existing company by name or create new one.

        Useful for interview creation - ensures company exists.

        Args:
            name: Company name.

        Returns:
            Existing or newly created company record.
        """
        # Try to find existing
        existing = self.company_repository.get_by_name(name)
        if existing:
            return existing

        # Create new company with minimal data
        return self.create_company(name=name)

    def recalculate_metrics(self, company_id: str) -> Dict[str, Any]:
        """Recalculate company metrics from interview data.

        Called by feedback loop when interviews complete.

        Args:
            company_id: Company UUID.

        Returns:
            Updated company record with recalculated metrics.

        Raises:
            ValueError: If company not found.
        """
        # Verify company exists
        company = self.company_repository.get_by_id(company_id)
        if not company:
            raise ValueError(f"Company with ID {company_id} not found")

        # Query all interviews for this company
        # Note: This requires access to interview_repository
        # For now, we'll accept the counts as parameters via update_metrics_from_interviews

        # This method is a placeholder - actual implementation will be in feedback_service
        return company

    def update_metrics_from_interviews(
        self,
        company_id: str,
        total_sent: int,
        total_placed: int
    ) -> Dict[str, Any]:
        """Update company metrics based on interview outcomes.

        Called by FeedbackService.

        Args:
            company_id: Company UUID.
            total_sent: Total candidates sent to this company.
            total_placed: Total successful placements.

        Returns:
            Updated company record.
        """
        placement_rate = (total_placed / total_sent) if total_sent > 0 else 0.0

        return self.company_repository.update_metrics(
            company_id=company_id,
            candidates_sent=total_sent,
            placements=total_placed,
            placement_rate=placement_rate
        )

    def match_company_reference(self, company_ref: CompanyReference) -> CompanyReference:
        """Match a CompanyReference to companies table and populate ID.

        Searches by name (including aliases) and adds company_id if found.
        If not found, creates the company.

        Args:
            company_ref: CompanyReference with name (and possibly ID already set).

        Returns:
            CompanyReference with ID populated.
        """
        # Already has ID, return as-is
        if company_ref.id:
            return company_ref

        # Try to find existing company
        company = self.company_repository.get_by_name(company_ref.name)

        # If not found, create it
        if not company:
            company = self.find_or_create_company(company_ref.name)

        # Return reference with ID
        return CompanyReference(
            name=company_ref.name,
            id=company["id"]
        )
