"""FastAPI application for recruitment candidate management and scoring."""

from fastapi import FastAPI, HTTPException
from typing import List, Optional

from app.models import LinkedInCandidate
from app.database.client import supabase
from app.repositories.candidate_repository import CandidateRepository
from app.services.scoring_service import ScoringService
from app.services.scraping_service import ScrapingService
from app.services.candidate_service import CandidateService
from app.api.schemas.responses import CandidateScoreResponse, CandidateFilterResponse


app = FastAPI()

# Initialize repository and services
candidate_repository = CandidateRepository(supabase)
scoring_service = ScoringService(candidate_repository)
scraping_service = ScrapingService(candidate_repository)
candidate_service = CandidateService(candidate_repository)


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
    try:
        candidate, scoring_result = scoring_service.score_single_candidate(
            candidate_id, target_role
        )
    except ValueError as error:
        if "not found" in str(error):
            raise HTTPException(status_code=404, detail=str(error))
        else:
            raise HTTPException(status_code=400, detail=str(error))

    return CandidateScoreResponse(
        linkedin_url=candidate.linkedin_url,
        score=scoring_result.score,
        breakdown=scoring_result.breakdown
    )


@app.get("/get-top-candidates", response_model=List[CandidateScoreResponse])
def get_top_candidates(target_role: str, num_of_profiles: int):
    """Score all candidates and return the top N for a role.

    Args:
        target_role: Name of the role to score against.
        num_of_profiles: Number of top candidates to return.

    Returns:
        List of CandidateScoreResponse sorted by score (descending).

    Raises:
        HTTPException: If validation fails or role invalid.

    Note:
        This loads all candidates into memory. Consider pagination
        for large datasets.
    """
    try:
        top_candidates = scoring_service.get_top_candidates_for_role(
            target_role, num_of_profiles
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return [
        CandidateScoreResponse(
            linkedin_url=candidate.linkedin_url,
            score=scoring_result.score,
            breakdown=scoring_result.breakdown
        )
        for candidate, scoring_result in top_candidates
    ]


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
    try:
        return candidate_service.create_candidate(candidate)
    except ValueError as error:
        error_message = str(error)
        if "Failed to insert" in error_message:
            raise HTTPException(status_code=500, detail=error_message)
        # Duplicate or other validation errors
        raise HTTPException(status_code=409, detail=error_message)


@app.get("/candidates")
def list_candidates():
    """Get all candidates from database.

    Returns:
        List of all candidate records.

    Note:
        Returns raw database records. Consider pagination for production.
    """
    return candidate_service.get_all_candidates()


@app.get("/candidates/id")
def get_specific_candidate(candidate_id: str):
    """Retrieve a single candidate by ID.

    Args:
        candidate_id: Database ID of the candidate.

    Returns:
        LinkedInCandidate object if found.

    Raises:
        HTTPException: If candidate not found.
    """
    try:
        return candidate_service.get_candidate_by_id(candidate_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


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
    filtered_candidates = candidate_service.filter_candidates(
        current_company, skills
    )

    return [
        CandidateFilterResponse(
            first_name=candidate["first_name"],
            last_name=candidate["last_name"],
            linkedin_url=candidate["linkedin_url"],
            matched_skills=candidate["matched_skills"]
        )
        for candidate in filtered_candidates
    ]


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

        return scraping_service.scrape_and_save_profiles(usernames)

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Scraping failed: {str(error)}"
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
        return scraping_service.scrape_company_employees_and_save(
            company_url, max_employees, job_title, batch_name or "batch"
        )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Company scraping failed: {str(error)}"
        )
