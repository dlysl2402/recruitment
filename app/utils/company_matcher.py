"""Utility for matching company names across different formats and aliases."""

from typing import Union, Optional, Protocol

from app.models import CompanyReference


class CompanyAliasProvider(Protocol):
    """Protocol for objects that provide company name and aliases."""
    company: str
    company_aliases: list[str]


class CompanyMatcher:
    """Unified utility for matching company names.

    Handles various company formats (str, CompanyReference, FeederPattern, etc.)
    and checks for exact matches and alias matches.
    """

    @staticmethod
    def extract_name(company: Union[str, CompanyReference]) -> str:
        """Extract company name from various formats.

        Args:
            company: Company as string or CompanyReference object.

        Returns:
            Company name as string.
        """
        if isinstance(company, CompanyReference):
            return company.name
        elif isinstance(company, str):
            return company
        else:
            return str(company)

    @staticmethod
    def matches(
        company_a: Union[str, CompanyReference],
        company_b: Union[str, CompanyReference, CompanyAliasProvider],
        company_repository=None
    ) -> bool:
        """Check if two companies match, considering aliases.

        Supports two matching strategies:
        1. Exact name match (case-insensitive)
        2. Alias match via company_b's company_aliases or company_repository

        Args:
            company_a: First company (str or CompanyReference).
            company_b: Second company (str, CompanyReference, or object with
                company/company_aliases attributes like FeederPattern).
            company_repository: Optional repository for deep alias lookup.

        Returns:
            True if companies match, False otherwise.

        Examples:
            >>> CompanyMatcher.matches("Amazon", "amazon")
            True
            >>> CompanyMatcher.matches("AWS", feeder_pattern_with_aws_alias)
            True
        """
        # Extract name from company_a
        name_a = CompanyMatcher.extract_name(company_a)
        if not name_a:
            return False

        name_a_lower = name_a.lower().strip()

        # Handle company_b based on its type
        if isinstance(company_b, (str, CompanyReference)):
            # Simple string comparison
            name_b = CompanyMatcher.extract_name(company_b)
            if not name_b:
                return False

            name_b_lower = name_b.lower().strip()

            # Exact match only
            if name_a_lower == name_b_lower:
                return True

            # If company_repository provided, check database aliases
            if company_repository:
                return CompanyMatcher._matches_via_repository(
                    name_a, name_b, company_repository
                )

            return False

        else:
            # company_b has company + company_aliases (FeederPattern, PedigreeCompany, etc.)
            if not hasattr(company_b, 'company') or not hasattr(company_b, 'company_aliases'):
                return False

            # Check against primary company name and all aliases
            all_company_names = [company_b.company] + company_b.company_aliases

            for company_name in all_company_names:
                company_name_lower = company_name.lower().strip()

                # Exact match only
                if name_a_lower == company_name_lower:
                    return True

            return False

    @staticmethod
    def _matches_via_repository(
        company_a_name: str,
        company_b_name: str,
        company_repository
    ) -> bool:
        """Check if companies match via repository alias lookup.

        Args:
            company_a_name: First company name.
            company_b_name: Second company name.
            company_repository: Repository with find_by_name_or_alias method.

        Returns:
            True if both companies resolve to the same database record.
        """
        try:
            company_a_record = company_repository.find_by_name_or_alias(company_a_name)
            company_b_record = company_repository.find_by_name_or_alias(company_b_name)

            # If both found and have same ID, they're the same company
            if company_a_record and company_b_record:
                return company_a_record["id"] == company_b_record["id"]

            # Check if company_b matches any alias of company_a
            if company_a_record:
                aliases = [alias.lower() for alias in company_a_record.get("aliases", [])]
                if company_b_name.lower() in aliases or company_a_record["name"].lower() == company_b_name.lower():
                    return True

            # Check if company_a matches any alias of company_b
            if company_b_record:
                aliases = [alias.lower() for alias in company_b_record.get("aliases", [])]
                if company_a_name.lower() in aliases or company_b_record["name"].lower() == company_a_name.lower():
                    return True

            return False

        except Exception:
            # If repository lookup fails, fall back to no match
            return False
