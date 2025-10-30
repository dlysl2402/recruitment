"""Service for LinkedIn profile scraping operations."""

import logging
import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from app.scrapers.profile_scraper import (
    scrape_linkedin_profiles,
    extract_linkedin_username,
    is_error_response
)
from app.scrapers.company_scraper import scrape_linkedin_company
from app.transformers.scraper_to_database import transform_scraped_profile
from app.repositories.candidate_repository import CandidateRepository


# Setup structured logging for scraping errors
def setup_scraping_logger() -> logging.Logger:
    """Configure and return logger for scraping errors.

    Creates logs directory if it doesn't exist and sets up JSON-formatted logging.

    Returns:
        Configured logger instance.
    """
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    logger = logging.getLogger("scraping_service")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers if logger already configured
    if not logger.handlers:
        file_handler = logging.FileHandler(logs_dir / "scraping_errors.log")
        file_handler.setLevel(logging.ERROR)

        # Use basic format for now, could be enhanced with JSON formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# Initialize logger
scraping_logger = setup_scraping_logger()


class ScrapingService:
    """Service for scraping and processing LinkedIn profiles.

    Coordinates scraping, transformation, and storage of LinkedIn data.

    Attributes:
        candidate_repository: Repository for candidate data storage.
        candidate_service: CandidateService for duplicate detection and storage.
        company_service: Optional CompanyService for auto-matching companies.
    """

    def __init__(
        self,
        candidate_repository: CandidateRepository,
        company_service=None,
        candidate_service=None
    ):
        """Initialize the scraping service.

        Args:
            candidate_repository: Repository for storing candidates (legacy).
            company_service: Optional CompanyService for auto-matching companies.
            candidate_service: Optional CandidateService for duplicate detection.
        """
        self.candidate_repository = candidate_repository
        self.company_service = company_service
        self.candidate_service = candidate_service

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
        # Check if profile data is empty
        if not profile_data:
            error_details = {
                "username": username,
                "error": "No data returned from scraper",
                "error_type": "scraping_failed",
                "status": "failed"
            }
            scraping_logger.error(
                f"Scraping failed - {json.dumps(error_details)}"
            )
            return {**error_details, "success": False}

        # Check if Apify returned an error response
        is_error, error_message = is_error_response(profile_data)
        if is_error:
            error_details = {
                "username": username,
                "error": error_message,
                "error_type": "profile_not_found",
                "status": "failed"
            }
            scraping_logger.error(
                f"Profile not found - {json.dumps(error_details)}"
            )
            return {**error_details, "success": False}

        try:
            # Transform and validate profile data
            candidate = transform_scraped_profile(profile_data)

            # Use candidate_service for duplicate detection if available
            if self.candidate_service:
                # Check for duplicates
                auto_match_id, manual_review = self.candidate_service.find_potential_duplicates(candidate)

                if auto_match_id:
                    # Auto-merge exact match
                    result = self.candidate_service.merge_candidate(auto_match_id, candidate)
                    return {
                        "id": result["id"],
                        "candidate_name": f"{candidate.first_name} {candidate.last_name}",
                        "current_company": candidate.current_company.name if candidate.current_company else "Unknown",
                        "status": "auto_merged",
                        "success": True
                    }
                elif manual_review:
                    # Name matches but experience doesn't - needs manual review
                    return {
                        "username": username,
                        "candidate_name": f"{candidate.first_name} {candidate.last_name}",
                        "current_company": candidate.current_company.name if candidate.current_company else "Unknown",
                        "status": "manual_review_required",
                        "potential_duplicates": manual_review,
                        "candidate_data": candidate.model_dump(),
                        "success": False
                    }
                else:
                    # No duplicates, create new
                    result = self.candidate_service.create_candidate(candidate)
                    return {
                        "id": result["id"],
                        "candidate_name": f"{candidate.first_name} {candidate.last_name}",
                        "current_company": candidate.current_company.name if candidate.current_company else "Unknown",
                        "status": "created",
                        "success": True
                    }

            # Fallback to old behavior if candidate_service not available
            else:
                # Auto-match companies if company_service is available
                if self.company_service:
                    # Match current_company
                    if candidate.current_company:
                        candidate.current_company = self.company_service.match_company_reference_no_create(
                            candidate.current_company
                        )

                    # Match all experience companies
                    for experience in candidate.experience:
                        experience.company = self.company_service.match_company_reference_no_create(
                            experience.company
                        )

                candidate_dict = candidate.model_dump()

                # Save to database
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

            # Check if error is duplicate constraint violation
            if self._is_duplicate_error(error_message):
                error_details = {
                    "username": username,
                    "error": "Duplicate profile (already exists)",
                    "candidate_name": f"{candidate.first_name} {candidate.last_name}",
                    "error_type": "duplicate",
                    "status": "skipped"
                }
                scraping_logger.info(
                    f"Duplicate profile skipped - {json.dumps(error_details)}"
                )
                return {**error_details, "success": False}

            # Check if error is validation failure
            elif "validation error" in error_message.lower():
                error_details = {
                    "username": username,
                    "error": f"Validation failed: {error_message}",
                    "error_type": "validation_failed",
                    "status": "failed"
                }
                scraping_logger.error(
                    f"Validation failed - {json.dumps(error_details)}"
                )
                return {**error_details, "success": False}

            # Generic processing failure
            else:
                error_details = {
                    "username": username,
                    "error": f"Processing failed: {error_message}",
                    "error_type": "processing_failed",
                    "status": "failed"
                }
                scraping_logger.error(
                    f"Processing failed - {json.dumps(error_details)}"
                )
                return {**error_details, "success": False}

    def scrape_and_save_profiles(
        self,
        usernames: List[str]
    ) -> Dict[str, Any]:
        """Scrape LinkedIn profiles and save to database with duplicate detection.

        Args:
            usernames: List of LinkedIn usernames to scrape.

        Returns:
            Dictionary with categorized results:
                - created: New candidates created
                - auto_merged: Existing candidates updated (exact match)
                - manual_review: Require user decision (name match, different experience)
                - failed: Scraping or processing failures
                - summary: Counts for each category

        Raises:
            Exception: If scraping API call fails.
        """
        scraped_results = scrape_linkedin_profiles(usernames)

        created = []
        auto_merged = []
        manual_review = []
        failed = []

        for username, profile_data in zip(usernames, scraped_results):
            result = self._process_single_profile(username, profile_data)

            status = result.get("status", "")

            if result.get("success"):
                result.pop("success")
                if status == "created":
                    created.append(result)
                elif status == "auto_merged":
                    auto_merged.append(result)
            else:
                result.pop("success", None)
                if status == "manual_review_required":
                    manual_review.append(result)
                else:
                    failed.append(result)

        response = {
            "created": created,
            "auto_merged": auto_merged,
            "summary": {
                "total": len(usernames),
                "created": len(created),
                "auto_merged": len(auto_merged),
                "manual_review": len(manual_review),
                "failed": len(failed)
            }
        }

        if manual_review:
            response["manual_review"] = manual_review
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
