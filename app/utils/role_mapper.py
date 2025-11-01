"""Utility for mapping company-specific job titles to canonical roles.

This module handles cross-company role equivalence, allowing the system to recognize
that different companies use different titles for the same role (e.g., Optiver's
"Application Engineer" = IMC's "Trading Systems Engineer").
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from functools import lru_cache

from app.utils.company_matcher import CompanyMatcher


class RoleMapper:
    """Maps company-specific job titles to canonical roles and job functions."""

    _config: Optional[Dict] = None
    _company_title_index: Optional[Dict[str, Dict[str, str]]] = None

    @classmethod
    def _load_config(cls) -> Dict:
        """Loads role equivalence configuration from JSON file.

        Returns:
            Dictionary of role equivalence mappings.
        """
        if cls._config is None:
            config_path = Path(__file__).parent.parent / "role_equivalence.json"
            with open(config_path, "r") as f:
                cls._config = json.load(f)
        return cls._config

    @classmethod
    def _build_index(cls) -> Dict[str, Dict[str, str]]:
        """Builds reverse index: company -> title -> job_function.

        Returns:
            Nested dict mapping company -> title -> job_function.
        """
        if cls._company_title_index is None:
            config = cls._load_config()
            index = {}

            for job_function, role_data in config.items():
                for company, titles in role_data["companies"].items():
                    company_lower = company.lower()
                    if company_lower not in index:
                        index[company_lower] = {}

                    for title in titles:
                        title_lower = title.lower()
                        index[company_lower][title_lower] = job_function

            cls._company_title_index = index

        return cls._company_title_index

    @classmethod
    def get_canonical_role(cls, company: str, title: str, company_repository=None) -> Optional[str]:
        """Gets the job function for a company-specific title.

        Uses CompanyMatcher for exact + alias matching. No longer cached due to
        company_repository dependency.

        Args:
            company: Company name (e.g., "IMC", "Optiver").
            title: Job title (e.g., "Trading Systems Engineer").
            company_repository: Optional repository for alias lookup.

        Returns:
            Job function (e.g., "trading_system_engineer"), or None if no mapping exists.

        Example:
            >>> RoleMapper.get_canonical_role("IMC", "Trading Systems Engineer")
            'trading_system_engineer'
            >>> RoleMapper.get_canonical_role("Optiver", "Application Engineer")
            'trading_system_engineer'
        """
        config = cls._load_config()
        title_lower = title.lower()

        # Iterate through all job functions and companies
        for job_function, role_data in config.items():
            for config_company, titles in role_data["companies"].items():
                # Use CompanyMatcher for exact + alias matching
                if CompanyMatcher.matches(company, config_company, company_repository):
                    # Check if title matches
                    if title_lower in [t.lower() for t in titles]:
                        return job_function

        return None

    @classmethod
    def get_job_function(cls, company: str, title: str, company_repository=None) -> Optional[str]:
        """Gets the job function for a company-specific title.

        This is now an alias for get_canonical_role since the parent key IS the job function.

        Args:
            company: Company name.
            title: Job title.
            company_repository: Optional repository for alias lookup.

        Returns:
            Job function key (e.g., "trading_system_engineer"), or None if no mapping.

        Example:
            >>> RoleMapper.get_job_function("IMC", "Trading Systems Engineer")
            'trading_system_engineer'
        """
        return cls.get_canonical_role(company, title, company_repository)

    @classmethod
    def are_roles_equivalent(
        cls, company1: str, title1: str, company2: str, title2: str, company_repository=None
    ) -> bool:
        """Checks if two (company, title) pairs represent equivalent roles.

        Args:
            company1: First company name.
            title1: First job title.
            company2: Second company name.
            title2: Second job title.
            company_repository: Optional repository for alias lookup.

        Returns:
            True if roles are equivalent, False otherwise.

        Example:
            >>> RoleMapper.are_roles_equivalent(
            ...    "IMC", "Trading Systems Engineer",
            ...    "Optiver", "Application Engineer"
            ... )
            True
        """
        role1 = cls.get_canonical_role(company1, title1, company_repository)
        role2 = cls.get_canonical_role(company2, title2, company_repository)

        if role1 is None or role2 is None:
            return False

        return role1 == role2

    @classmethod
    def get_equivalent_titles(cls, job_function: str) -> Dict[str, List[str]]:
        """Gets all company-specific titles for a job function.

        Args:
            job_function: Job function key (e.g., "trading_system_engineer").

        Returns:
            Dictionary mapping company -> list of equivalent titles.

        Example:
            >>> RoleMapper.get_equivalent_titles("trading_system_engineer")
            {
                'IMC': ['Trading Systems Engineer', 'Trading Engineer'],
                'Optiver': ['Application Engineer'],
                'Citadel Securities': ['Site Reliability Engineer']
            }
        """
        config = cls._load_config()
        role_data = config.get(job_function)

        if role_data:
            return role_data.get("companies", {})
        return {}

    @classmethod
    def get_all_job_functions(cls) -> List[str]:
        """Gets list of all job functions.

        Returns:
            List of job function keys.
        """
        config = cls._load_config()
        return list(config.keys())

    @classmethod
    def get_role_info(cls, job_function: str) -> Optional[Dict]:
        """Gets full information about a job function.

        Args:
            job_function: Job function key (e.g., "trading_system_engineer").

        Returns:
            Dict with canonical_name, description, companies.

        Example:
            >>> RoleMapper.get_role_info("trading_system_engineer")
            {
                'canonical_name': 'Trading Systems Engineer',
                'description': 'Keep trading environment up and running',
                'companies': {...}
            }
        """
        config = cls._load_config()
        return config.get(job_function)

    @classmethod
    def match_title_with_context(
        cls, candidate_title: str, candidate_company: str, target_title: str,
        target_company: Optional[str] = None, company_repository=None
    ) -> bool:
        """Checks if candidate's title matches target title with company context.

        This is used for title matching bonuses in scoring. If both have company context,
        checks role equivalence. Otherwise falls back to string matching.

        Args:
            candidate_title: Candidate's job title.
            candidate_company: Candidate's company.
            target_title: Target job title to match.
            target_company: Optional target company for equivalence check.
            company_repository: Optional repository for alias lookup.

        Returns:
            True if titles match (directly or via equivalence), False otherwise.

        Example:
            >>> RoleMapper.match_title_with_context(
            ...    "Application Engineer", "Optiver",
            ...    "Trading Systems Engineer", "IMC"
            ... )
            True
        """
        # Direct string match (case-insensitive)
        if candidate_title.lower() == target_title.lower():
            return True

        # If we have both company contexts, check role equivalence
        if target_company:
            return cls.are_roles_equivalent(
                candidate_company, candidate_title, target_company, target_title, company_repository
            )

        # Without target company context, check if candidate role matches any
        # company's version of the target title
        candidate_role = cls.get_canonical_role(candidate_company, candidate_title, company_repository)
        if candidate_role:
            equivalent_titles = cls.get_equivalent_titles(candidate_role)
            for titles in equivalent_titles.values():
                if target_title.lower() in [t.lower() for t in titles]:
                    return True

        return False

    @classmethod
    def reload_config(cls):
        """Reloads configuration from disk. Useful after updating role_equivalence.json."""
        cls._config = None
        cls._company_title_index = None
