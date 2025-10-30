"""FastAPI application for recruitment candidate management and scoring."""

import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict

from app.feeder_models import RoleFeederConfig
from app.scoring import score_candidate, load_feeder_configs
from app.linkedin_scraper.profile_scraper import (
    scrape_linkedin_profiles,
    extract_linkedin_username
)
from app.linkedin_scraper.company_scraper import scrape_linkedin_company
from app.helper.scraper_to_database import (
    transform_scraped_profile,
    db_row_to_candidate
)
from app.models import DateInfo, Experience, Education, LinkedInCandidate
from app.database.queries import (
    insert_candidate,
    get_candidate_with_id,
    get_all_candidates,
    get_candidates_with_filters
)


app = FastAPI()


# API Response Models
class CandidateScoreResponse(BaseModel):
    """Response model for candidate scoring endpoints."""
    linkedin_url: str
    score: float
    breakdown: Dict


class CandidateFilterResponse(BaseModel):
    """Response model for filtered candidate results."""
    first_name: str
    last_name: str
    linkedin_url: str
    matched_skills: List[str]


@app.get("/")
def root():
    """Health check endpoint.

    Returns:
        Dictionary with status indicator.
    """
    return {"status": "ok"}


# Scoring endpoints
@app.get("/score-candidate", response_model=CandidateScoreResponse)
def score_candidate_endpoint(candidate_id: str, target_role: str):
    """Score a single candidate for a target role.

    Args:
        candidate_id: Database ID of the candidate to score.
        target_role: Name of the role to score against.

    Returns:
        CandidateScoreResponse containing score and breakdown.

    Raises:
        HTTPException: If candidate not found or role invalid.
    """
    candidate = get_candidate_with_id(candidate_id)

    scoring_result = score_candidate(candidate, target_role)

    return CandidateScoreResponse(
        linkedin_url=candidate.linkedin_url,
        score=scoring_result.get("score", 0),
        breakdown=scoring_result.get("breakdown", {})
    )


@app.get("/get-top-candidates", response_model=List[CandidateScoreResponse])
def get_top_candidates(target_role: str, num_of_profiles: int):
    """Score all candidates and return the top N for a role.

    Args:
        target_role: Name of the role to score against.
        num_of_profiles: Number of top candidates to return.

    Returns:
        List of CandidateScoreResponse sorted by score (descending).

    Note:
        This loads all candidates into memory. Consider pagination
        for large datasets.
    """
    all_profiles = get_all_candidates().data

    results = []

    for raw_candidate in all_profiles:
        candidate = db_row_to_candidate(raw_candidate)

        scoring_result = score_candidate(candidate, target_role)

        results.append(CandidateScoreResponse(
            linkedin_url=candidate.linkedin_url,
            score=scoring_result.get("score", 0),
            breakdown=scoring_result.get("breakdown", {})
        ))

    sorted_results = sorted(results, key=lambda x: x.score, reverse=True)
    return sorted_results[:num_of_profiles]


# Database CRUD endpoints
@app.post("/candidates")
def create_candidate(candidate: LinkedInCandidate):
    """Add a new candidate to the database.

    Args:
        candidate: LinkedInCandidate object with profile information.

    Returns:
        Dictionary with success message and inserted candidate ID.

    Raises:
        HTTPException: If insertion fails (e.g., duplicate).
    """
    result = insert_candidate(candidate.dict())
    return {"message": "Candidate added", "id": result.data[0]["id"]}


@app.get("/candidates")
def list_candidates():
    """Get all candidates from database.

    Returns:
        List of all candidate records.

    Note:
        Returns raw database records. Consider pagination for production.
    """
    result = get_all_candidates()
    return result.data


@app.get("/candidates/id")
def get_specific_candidate(candidate_id: str):
    """Retrieve a single candidate by ID.

    Args:
        candidate_id: Database ID of the candidate.

    Returns:
        LinkedInCandidate object if found, None otherwise.
    """
    return get_candidate_with_id(candidate_id)


@app.get("/candidates/filter", response_model=List[CandidateFilterResponse])
def filter_candidates(
    current_company: Optional[str] = None,
    skills: Optional[str] = None
):
    """Filter candidates by company and/or skills.

    Args:
        current_company: Company name to filter by (case-insensitive).
        skills: Comma-separated list of skill names to filter by.

    Returns:
        List of CandidateFilterResponse with matched skills highlighted.

    Note:
        Multiple skills use AND logic (candidate must have all).
    """
    query_filters = {}
    if current_company:
        query_filters["current_company"] = current_company

    requested_skills = None
    if skills:
        requested_skills = {
            skill.strip().lower()
            for skill in skills.split(",")
            if skill.strip()
        }

    result = get_candidates_with_filters(
        filters=query_filters,
        skills=requested_skills
    )

    filtered_candidates = []
    for candidate_data in result.data:
        candidate_skills = candidate_data.get("skills", [])

        # Extract skill names from JSONB array of objects
        candidate_skill_names = {
            skill["name"].lower()
            for skill in candidate_skills
            if isinstance(skill, dict) and "name" in skill
        }

        # Find intersection of requested and candidate skills
        matched_skills = [
            skill
            for skill in requested_skills
            if skill in candidate_skill_names
        ] if requested_skills else []

        filtered_candidates.append(CandidateFilterResponse(
            first_name=candidate_data.get("first_name", ""),
            last_name=candidate_data.get("last_name", ""),
            linkedin_url=candidate_data.get("linkedin_url", ""),
            matched_skills=matched_skills
        ))

    return filtered_candidates


# LinkedIn scraping endpoints
@app.post("/linkedin-scrape-and-save-batch")
def scrape_and_save_candidate_batch(profile_usernames: str):
    """Scrape LinkedIn profiles and save to database.

    Args:
        profile_usernames: Comma-separated LinkedIn usernames to scrape.

    Returns:
        Dictionary with "success" and optional "failed" lists containing
        processing results for each profile.

    Raises:
        HTTPException: If scraping fails or no valid usernames provided.

    Note:
        Duplicates are detected and skipped, reported in failed list.
    """
    try:
        usernames = [
            username.strip()
            for username in profile_usernames.split(",")
            if username.strip()
        ]
        if not usernames:
            raise HTTPException(
                status_code=400,
                detail="No valid usernames provided"
            )

        try:
            scraped_results = scrape_linkedin_profiles(usernames)
        except Exception as scraping_error:
            raise HTTPException(
                status_code=500,
                detail=f"Scraping failed: {str(scraping_error)}"
            )

        success = []
        failed = []

        for username, profile_data in zip(usernames, scraped_results):
            if not profile_data:
                failed.append({
                    "username": username,
                    "error": "No data scraped",
                    "status": "scraping_failed"
                })
                continue

            try:
                candidate = transform_scraped_profile(profile_data)
                candidate_dict = candidate.dict()

                database_result = insert_candidate(candidate_dict)

                if not database_result.data:
                    raise ValueError("Insert returned no data")

                record = database_result.data[0]
                success.append({
                    "id": record.get("id", ""),
                    "candidate_name": f"{candidate.first_name} {candidate.last_name}",
                    "current_company": candidate.current_company,
                    "status": "inserted"
                })

            except Exception as processing_error:
                error_message = str(processing_error)

                # Detect duplicate constraint violations
                is_duplicate = any(
                    indicator in error_message
                    for indicator in [
                        "23505",
                        "unique constraint",
                        "already exists",
                        "candidates_linkedin_url_key"
                    ]
                )

                if is_duplicate:
                    failed.append({
                        "username": username,
                        "error": "Duplicate profile (already exists)",
                        "candidate_name": f"{candidate.first_name} {candidate.last_name}",
                        "status": "skipped_duplicate"
                    })
                else:
                    failed.append({
                        "username": username,
                        "error": f"Processing failed: {error_message}",
                        "status": "failed"
                    })

        response = {"success": success}
        if failed:
            response["failed"] = failed

        return response

    except HTTPException:
        raise
    except Exception as batch_error:
        raise HTTPException(
            status_code=500,
            detail=f"Batch processing failed: {str(batch_error)}"
        )


@app.post("/linkedin-company-employees-scrape")
def scrape_company_employees(
    company_url: str,
    max_employees: Optional[int] = None,
    job_title: Optional[str] = None,
    batch_name: Optional[str] = None
):
    """Scrape employees from a LinkedIn company page and save to database.

    Args:
        company_url: LinkedIn company page URL.
        max_employees: Maximum number of employees to scrape.
        job_title: Filter employees by job title.
        batch_name: Optional name for this scraping batch.

    Returns:
        Same format as scrape_and_save_candidate_batch.

    Raises:
        HTTPException: If company scraping fails.
    """
    try:
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

        usernames_string = ", ".join(usernames)

        result = scrape_and_save_candidate_batch(usernames_string)

        return result

    except HTTPException:
        raise
    except Exception as company_error:
        raise HTTPException(
            status_code=500,
            detail=f"Company scraping failed: {str(company_error)}"
        )
