"""Service for linking unlinked company references to companies table."""

import logging
from typing import Dict, List, Any
from datetime import datetime

from app.repositories.candidate_repository import CandidateRepository
from app.services.company_service import CompanyService
from app.models.candidate import CompanyReference

logger = logging.getLogger(__name__)


class CompanyLinkageService:
    """Service for sweeping database and linking companies by name/alias."""

    def __init__(
        self,
        candidate_repository: CandidateRepository,
        company_service: CompanyService
    ):
        """Initialize the linkage service.

        Args:
            candidate_repository: Repository for candidate data access.
            company_service: Service for company matching.
        """
        self.candidate_repository = candidate_repository
        self.company_service = company_service

    def _build_company_cache(self) -> Dict[str, str]:
        """Build a cache of company name/alias -> company ID mappings.

        Returns:
            Dictionary mapping lowercase company names/aliases to company IDs.
        """
        logger.info("Building company cache...")
        companies = self.company_service.list_companies()

        cache = {}
        for company in companies:
            # Add primary name
            cache[company["name"].lower()] = company["id"]

            # Add all aliases
            if company.get("aliases"):
                for alias in company["aliases"]:
                    cache[alias.lower()] = company["id"]

        logger.info(f"Company cache built with {len(cache)} entries")
        return cache

    def sweep_and_link_companies(self, dry_run: bool = True) -> Dict[str, Any]:
        """Sweep all candidates and link unlinked company references.

        Finds all candidates with empty company IDs and attempts to link them
        to existing companies in the database using name/alias matching.

        Args:
            dry_run: If True, only report what would be updated without saving.

        Returns:
            Dictionary with sweep results:
                - total_candidates: Total candidates scanned
                - unlinked_current_companies: Candidates with unlinked current_company
                - unlinked_experiences: Total experience entries with unlinked companies
                - linked_current_companies: Successfully linked current companies
                - linked_experiences: Successfully linked experience companies
                - not_found_companies: Set of company names not found in database
                - dry_run: Whether this was a dry run
                - timestamp: When the sweep was performed
        """
        # Build company name->ID cache once
        company_cache = self._build_company_cache()

        # Fetch all candidates
        logger.info("Fetching all candidates from database...")
        all_candidates = self.candidate_repository.get_with_filters()
        logger.info(f"Fetched {len(all_candidates)} candidates")

        total_candidates = len(all_candidates)
        unlinked_current = 0
        unlinked_exp = 0
        linked_current = 0
        linked_exp = 0
        not_found_companies = set()
        linked_companies = {}  # Track company_id -> count of linkages

        candidates_to_update = []

        logger.info("Starting company linkage sweep...")
        for idx, candidate_data in enumerate(all_candidates):
            if idx % 100 == 0:
                logger.info(f"Processing candidate {idx}/{total_candidates}...")
            candidate_id = candidate_data["id"]
            updated = False

            # Check current_company
            current_company = candidate_data.get("current_company")
            if current_company and isinstance(current_company, dict):
                company_name = current_company.get("name")
                company_id = current_company.get("id", "")

                if company_name and not company_id:
                    unlinked_current += 1
                    # Look up in cache
                    found_id = company_cache.get(company_name.lower())

                    if found_id:
                        candidate_data["current_company"]["id"] = found_id
                        linked_current += 1
                        updated = True
                        # Track linkage
                        if found_id not in linked_companies:
                            linked_companies[found_id] = {"name": company_name, "count": 0}
                        linked_companies[found_id]["count"] += 1
                    else:
                        not_found_companies.add(company_name)

            # Check experience companies
            experiences = candidate_data.get("experience", [])
            if experiences and isinstance(experiences, list):
                for exp in experiences:
                    company = exp.get("company")
                    if company and isinstance(company, dict):
                        company_name = company.get("name")
                        company_id = company.get("id", "")

                        if company_name and not company_id:
                            unlinked_exp += 1
                            # Look up in cache
                            found_id = company_cache.get(company_name.lower())

                            if found_id:
                                company["id"] = found_id
                                linked_exp += 1
                                updated = True
                                # Track linkage
                                if found_id not in linked_companies:
                                    linked_companies[found_id] = {"name": company_name, "count": 0}
                                linked_companies[found_id]["count"] += 1
                            else:
                                not_found_companies.add(company_name)

            # Track candidates that need updates
            if updated:
                candidates_to_update.append(candidate_data)

        # Update candidates if not dry run
        if not dry_run and candidates_to_update:
            logger.info(f"Updating {len(candidates_to_update)} candidates in database...")
            for idx, candidate_data in enumerate(candidates_to_update):
                if idx % 50 == 0:
                    logger.info(f"Updated {idx}/{len(candidates_to_update)} candidates...")
                self.candidate_repository.update(
                    candidate_data["id"],
                    {
                        "current_company": candidate_data.get("current_company"),
                        "experience": candidate_data.get("experience")
                    }
                )
            logger.info("Database update complete")

        logger.info(f"Sweep complete. Linked {linked_current + linked_exp} companies across {len(candidates_to_update)} candidates")

        # Convert linked_companies to sorted list
        linked_companies_list = [
            {
                "company_id": company_id,
                "company_name": data["name"],
                "linkages_count": data["count"]
            }
            for company_id, data in linked_companies.items()
        ]
        linked_companies_list.sort(key=lambda x: x["linkages_count"], reverse=True)

        return {
            "total_candidates": total_candidates,
            "unlinked_current_companies": unlinked_current,
            "unlinked_experiences": unlinked_exp,
            "linked_current_companies": linked_current,
            "linked_experiences": linked_exp,
            "total_linked": linked_current + linked_exp,
            "linked_companies": linked_companies_list,
            "not_found_companies": sorted(list(not_found_companies)),
            "dry_run": dry_run,
            "timestamp": datetime.now().isoformat()
        }
