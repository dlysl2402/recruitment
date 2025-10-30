"""Service for LinkedIn profile scraping operations."""

from typing import List, Dict, Any

from app.scrapers.profile_scraper import (
    scrape_linkedin_profiles,
    extract_linkedin_username
)
from app.scrapers.company_scraper import scrape_linkedin_company
from app.transformers.scraper_to_database import transform_scraped_profile
from app.repositories.candidate_repository import CandidateRepository


class ScrapingService:
    """Service for scraping and processing LinkedIn profiles.

    Coordinates scraping, transformation, and storage of LinkedIn data.

    Attributes:
        candidate_repository: Repository for candidate data storage.
    """

    def __init__(self, candidate_repository: CandidateRepository):
        """Initialize the scraping service.

        Args:
            candidate_repository: Repository for storing candidates.
        """
        self.candidate_repository = candidate_repository

    @staticmethod
    def _is_duplicate_error(error_message: str) -> bool:
        """Check if error indicates duplicate database entry.

        Args:
            error_message: The error message to check.

        Returns:
            True if error is a duplicate constraint violation.
        """
        duplicate_indicators = [
            "23505",
            "unique constraint",
            "already exists",
            "candidates_linkedin_url_key"
        ]
        return any(indicator in error_message for indicator in duplicate_indicators)

    def _process_single_profile(
        self,
        username: str,
        profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process a single scraped profile and save to database.

        Args:
            username: LinkedIn username.
            profile_data: Raw scraped profile data.

        Returns:
            Dictionary with processing result (success or failure info).
        """
        if not profile_data:
            return {
                "username": username,
                "error": "No data scraped",
                "status": "scraping_failed",
                "success": False
            }

        try:
            candidate = transform_scraped_profile(profile_data)
            candidate_dict = candidate.dict()

            database_result = self.candidate_repository.insert(candidate_dict)

            if not database_result.data:
                raise ValueError("Insert returned no data")

            record = database_result.data[0]
            return {
                "id": record.get("id", ""),
                "candidate_name": f"{candidate.first_name} {candidate.last_name}",
                "current_company": candidate.current_company,
                "status": "inserted",
                "success": True
            }

        except Exception as processing_error:
            error_message = str(processing_error)

            if self._is_duplicate_error(error_message):
                return {
                    "username": username,
                    "error": "Duplicate profile (already exists)",
                    "candidate_name": f"{candidate.first_name} {candidate.last_name}",
                    "status": "skipped_duplicate",
                    "success": False
                }
            else:
                return {
                    "username": username,
                    "error": f"Processing failed: {error_message}",
                    "status": "failed",
                    "success": False
                }

    def scrape_and_save_profiles(
        self,
        usernames: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Scrape LinkedIn profiles and save to database.

        Args:
            usernames: List of LinkedIn usernames to scrape.

        Returns:
            Dictionary with "success" and "failed" lists.

        Raises:
            Exception: If scraping API call fails.
        """
        scraped_results = scrape_linkedin_profiles(usernames)

        success = []
        failed = []

        for username, profile_data in zip(usernames, scraped_results):
            result = self._process_single_profile(username, profile_data)

            if result.get("success"):
                result.pop("success")
                success.append(result)
            else:
                result.pop("success")
                failed.append(result)

        response = {"success": success}
        if failed:
            response["failed"] = failed

        return response

    def scrape_company_employees_and_save(
        self,
        company_url: str,
        max_employees: int = None,
        job_title: str = None,
        batch_name: str = "batch"
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Scrape company employees and save to database.

        Args:
            company_url: LinkedIn company page URL.
            max_employees: Maximum number of employees to scrape.
            job_title: Filter by job title.
            batch_name: Name for this scraping batch.

        Returns:
            Dictionary with "success" and "failed" lists.

        Raises:
            Exception: If scraping fails.
        """
        employee_results = scrape_linkedin_company(
            company_url,
            max_employees,
            job_title,
            batch_name
        )

        usernames = []
        for employee in employee_results:
            profile_url = employee.get("profile_url", "")
            usernames.append(extract_linkedin_username(profile_url))

        return self.scrape_and_save_profiles(usernames)
