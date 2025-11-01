"""FastAPI application for recruitment candidate management and scoring."""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional

from app.models import LinkedInCandidate
from app.models.interview import InterviewProcess, InterviewStage, InterviewStatus
from app.models.job import Job, JobStatus
from app.models.optimization import OptimizationRequest, OptimizationResponse
from app.database.client import supabase
from app.repositories.candidate_repository import CandidateRepository
from app.repositories.interview_repository import InterviewRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.job_repository import JobRepository
from app.services.scoring_service import ScoringService
from app.services.scraping_service import ScrapingService
from app.services.candidate_service import CandidateService
from app.services.interview_service import InterviewService
from app.services.feedback_service import FeedbackService
from app.services.company_service import CompanyService
from app.services.job_service import JobService
from app.services.feeder_optimization_service import FeederOptimizationService
from app.api.schemas.responses import CandidateScoreResponse, CandidateFilterResponse
from app.api.schemas.requests import (
    CreateInterviewRequest,
    AddStageRequest,
    UpdateStageOutcomeRequest,
    CompleteInterviewRequest,
    ScrapeBatchRequest
)
from app.api.schemas.company_schemas import (
    CreateCompanyRequest,
    UpdateCompanyRequest
)
from app.api.schemas.job_schemas import (
    CreateJobRequest,
    UpdateJobRequest,
    CloseJobRequest
)


app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global exception handlers
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Convert ValueError to appropriate HTTP exception.

    Automatically handles common patterns:
    - "not found" → 404 Not Found
    - "duplicate" or "already exists" → 409 Conflict
    - Everything else → 400 Bad Request
    """
    error_msg = str(exc).lower()

    if "not found" in error_msg:
        status_code = 404
    elif "duplicate" in error_msg or "already exists" in error_msg:
        status_code = 409
    else:
        status_code = 400

    return JSONResponse(
        status_code=status_code,
        content={"detail": str(exc)}
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Convert generic exceptions to 500 Internal Server Error.

    This catches all unhandled exceptions and returns a clean error response.
    Prevents stack traces from being exposed to clients.
    """
    error_msg = str(exc).lower()

    # Check if it's actually a "not found" error from database
    if "not found" in error_msg or "invalid input syntax for type uuid" in error_msg:
        status_code = 404
        detail = "Resource not found"
    else:
        status_code = 500
        detail = f"Internal server error: {str(exc)}"

    return JSONResponse(
        status_code=status_code,
        content={"detail": detail}
    )


# Initialize repository and services
candidate_repository = CandidateRepository(supabase)
interview_repository = InterviewRepository(supabase)
company_repository = CompanyRepository(supabase)
job_repository = JobRepository(supabase)
company_service = CompanyService(company_repository)
job_service = JobService(job_repository)
candidate_service = CandidateService(candidate_repository, company_service)
scoring_service = ScoringService(candidate_repository)
scraping_service = ScrapingService(candidate_repository, company_service, candidate_service)

# Initialize feedback service and interview service with feedback loop
feedback_service = FeedbackService(interview_repository, candidate_service, company_service, job_service)
interview_service = InterviewService(interview_repository, company_service, job_service, feedback_service)

# Initialize feeder optimization service
feeder_optimization_service = FeederOptimizationService(candidate_repository, company_repository)


@app.get("/")
def root():
    """Health check endpoint.

    Returns:
        Dictionary with status indicator.
    """
    return {"status": "ok"}


# Scoring endpoints
@app.get("/score-candidate", response_model=CandidateScoreResponse)
def score_candidate_endpoint(
    candidate_id: str,
    target_role: str,
    target_firm: Optional[str] = None,
    general_weight: float = 0.6,
):
    """Score a single candidate for a target role.

    Supports both general scoring (feeders_general.json) and weighted scoring
    that combines general + firm-specific feeders when target_firm is provided.

    Args:
        candidate_id: Database ID of the candidate to score.
        target_role: Name of the role to score against.
        target_firm: Optional HFT firm for firm-specific scoring (e.g., "Citadel").
                    If provided, uses weighted average of general + firm-specific.
        general_weight: Weight for general score (0.0-1.0), default 0.6.
                       Only used when target_firm is provided.

    Returns:
        CandidateScoreResponse containing score and breakdown.

    Example:
        GET /score-candidate?candidate_id=123&target_role=network_engineer
        GET /score-candidate?candidate_id=123&target_role=network_engineer&target_firm=Citadel

    Note:
        ValueError exceptions are automatically converted to appropriate
        HTTP status codes by the global exception handler.
    """
    if target_firm:
        # Use weighted scoring with general + firm-specific feeders
        candidate, scoring_result = scoring_service.score_candidate_for_firm(
            candidate_id, target_role, target_firm, general_weight
        )
    else:
        # Use standard scoring with general feeders only
        candidate, scoring_result = scoring_service.score_single_candidate(
            candidate_id, target_role
        )

    return CandidateScoreResponse(
        first_name=candidate.first_name,
        last_name=candidate.last_name,
        linkedin_url=candidate.linkedin_url,
        score=scoring_result.score,
        breakdown=scoring_result.breakdown
    )


@app.get("/get-top-candidates", response_model=List[CandidateScoreResponse])
def get_top_candidates(
    target_role: str,
    num_of_profiles: int,
    country: Optional[str] = None
):
    """Score all candidates and return the top N for a role.

    Args:
        target_role: Name of the role to score against.
        num_of_profiles: Number of top candidates to return.
        country: Optional country filter (case-insensitive). Example: "Australia", "United States"

    Returns:
        List of CandidateScoreResponse sorted by score (descending).

    Note:
        This loads all candidates into memory. Consider pagination
        for large datasets.
    """
    top_candidates = scoring_service.get_top_candidates_for_role(
        target_role, num_of_profiles, country=country
    )

    return [
        CandidateScoreResponse(
            first_name=candidate.first_name,
            last_name=candidate.last_name,
            linkedin_url=candidate.linkedin_url,
            score=scoring_result.score,
            breakdown=scoring_result.breakdown
        )
        for candidate, scoring_result in top_candidates
    ]


# Database CRUD endpoints
@app.post("/candidates")
def create_candidate(candidate: LinkedInCandidate):
    """Add a new candidate to the database with duplicate detection.

    Checks for duplicates by name and previous experience. If exact match found
    (same name + matching previous experience), auto-updates existing record.
    If name matches but experience differs, returns 409 with manual review needed.

    Args:
        candidate: LinkedInCandidate object with profile information.

    Returns:
        Dictionary with success message and candidate ID.

    Raises:
        HTTPException: 409 if manual review needed, 500 if insertion fails.
    """
    try:
        # Check for potential duplicates
        auto_match_id, manual_review = candidate_service.find_potential_duplicates(candidate)

        # If exact match found, auto-merge
        if auto_match_id:
            result = candidate_service.merge_candidate(auto_match_id, candidate)
            result["auto_merged"] = True
            return result

        # If name matches but experience doesn't match, require manual review
        if manual_review:
            raise HTTPException(
                status_code=409,
                detail={
                    "status": "manual_review_required",
                    "message": f"Found {len(manual_review)} candidate(s) with same name",
                    "new_candidate": {
                        "name": f"{candidate.first_name} {candidate.last_name}",
                        "current_company": candidate.current_company.name if candidate.current_company else "Unknown",
                        "current_title": candidate.experience[0].title if candidate.experience else "Unknown",
                        "experience": [
                            {
                                "company": exp.company.name,
                                "title": exp.title,
                                "start_date": exp.start_date.model_dump() if exp.start_date else None,
                                "end_date": exp.end_date.model_dump() if exp.end_date else None
                            }
                            for exp in candidate.experience[:5]
                        ]
                    },
                    "potential_duplicates": manual_review
                }
            )

        # No duplicates, create new candidate
        return candidate_service.create_candidate(candidate)

    except HTTPException:
        raise
    except ValueError as error:
        error_message = str(error)
        if "Failed to insert" in error_message:
            raise HTTPException(status_code=500, detail=error_message)
        raise HTTPException(status_code=409, detail=error_message)


@app.put("/candidates/{candidate_id}/merge")
def merge_candidate(candidate_id: str, candidate: LinkedInCandidate):
    """Merge new candidate data into an existing candidate.

    Updates the existing candidate with new current position and experience.
    Use this after manual review to confirm a duplicate match.

    Args:
        candidate_id: Database ID of existing candidate to update.
        candidate: New LinkedInCandidate data to merge.

    Returns:
        Dictionary with success message and candidate ID.

    Raises:
        HTTPException: If candidate not found (404) or merge fails (500).
    """
    try:
        return candidate_service.merge_candidate(candidate_id, candidate)
    except ValueError as error:
        error_message = str(error)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        raise HTTPException(status_code=500, detail=error_message)


@app.post("/candidates/force-create")
def force_create_candidate(candidate: LinkedInCandidate):
    """Create a new candidate without duplicate checking.

    Bypasses duplicate detection. Use after manual review confirms
    this is a different person despite name match.

    Args:
        candidate: LinkedInCandidate object with profile information.

    Returns:
        Dictionary with success message and inserted candidate ID.

    Raises:
        HTTPException: If insertion fails (500).
    """
    try:
        return candidate_service.create_candidate(candidate)
    except ValueError as error:
        raise HTTPException(status_code=500, detail=str(error))


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
    """
    return candidate_service.get_candidate_by_id(candidate_id)


@app.get("/candidates/by-name")
def get_candidates_by_name(first_name: str, last_name: str):
    """Retrieve candidates by full name.

    Args:
        first_name: Candidate's first name (case-insensitive).
        last_name: Candidate's last name (case-insensitive).

    Returns:
        List of LinkedInCandidate objects matching the name.
    """
    return candidate_service.get_candidates_by_name(first_name, last_name)


@app.delete("/candidates/{candidate_id}")
def delete_candidate(candidate_id: str):
    """Delete a candidate by ID.

    Args:
        candidate_id: UUID of the candidate to delete.

    Returns:
        Dictionary with success message.
    """
    return candidate_service.delete_candidate(candidate_id)


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
            id=candidate["id"],
            first_name=candidate["first_name"],
            last_name=candidate["last_name"],
            linkedin_url=candidate["linkedin_url"],
            current_company=candidate.get("current_company"),
            current_title=candidate.get("current_title"),
            location=candidate.get("location"),
            matched_skills=candidate["matched_skills"]
        )
        for candidate in filtered_candidates
    ]


# LinkedIn scraping endpoints
@app.post("/linkedin-scrape-and-save-batch")
def scrape_and_save_candidate_batch(request: ScrapeBatchRequest):
    """Scrape LinkedIn profiles and save to database with duplicate detection.

    Args:
        request: ScrapeBatchRequest with comma-separated LinkedIn usernames.

    Returns:
        Dictionary with categorized results:
            - created: New candidates created
            - auto_merged: Existing candidates auto-updated (exact match)
            - manual_review: Candidates requiring manual review (name match only)
            - failed: Scraping/processing failures
            - summary: Counts for each category

    Raises:
        HTTPException: If scraping fails or no valid usernames provided.

    Note:
        Exact duplicates (name + previous experience match) are auto-merged.
        Name matches with different experience require manual review.
    """
    try:
        usernames = [
            username.strip()
            for username in request.profile_usernames.split(",")
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


# Interview Management endpoints

@app.post("/interviews", response_model=InterviewProcess)
def create_interview(request: CreateInterviewRequest):
    """Create a new interview process for a candidate.

    Args:
        request: CreateInterviewRequest with candidate_id, company_name, role_title, etc.

    Returns:
        Created InterviewProcess object.

    Raises:
        HTTPException: If creation fails or validation errors.
    """
    try:
        return interview_service.create_interview_process(
            candidate_id=request.candidate_id,
            company_name=request.company_name,
            role_title=request.role_title,
            feeder_source=request.feeder_source,
            recruiter_name=request.recruiter_name
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Failed to create interview: {str(error)}")


@app.get("/interviews/{interview_id}", response_model=InterviewProcess)
def get_interview(interview_id: str):
    """Get a specific interview process with all its stages.

    Args:
        interview_id: UUID of the interview process.

    Returns:
        InterviewProcess object with stages.

    Raises:
        HTTPException: If interview not found.
    """
    try:
        interview = interview_service.get_interview_with_stages(interview_id)
        if not interview:
            raise HTTPException(status_code=404, detail=f"Interview {interview_id} not found")
        return interview
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/interviews", response_model=List[InterviewProcess])
def list_interviews(
    candidate_id: Optional[str] = None,
    company_name: Optional[str] = None,
    status: Optional[InterviewStatus] = None
):
    """List all interviews with optional filters.

    Args:
        candidate_id: Filter by candidate ID.
        company_name: Filter by company name.
        status: Filter by interview status.

    Returns:
        List of InterviewProcess objects sorted by creation date (newest first).

    Note:
        If both candidate_id and company_name provided, candidate_id takes precedence.
        If no filters provided, returns all interviews.
    """
    try:
        if candidate_id:
            return interview_service.get_candidate_interview_history(
                candidate_id, include_stages=False
            )
        elif company_name:
            return interview_service.get_company_interviews(
                company_name, status_filter=status
            )
        else:
            # Return all interviews sorted by creation date
            return interview_service.get_all_interviews(status_filter=status)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/interviews/candidate/{candidate_id}", response_model=List[InterviewProcess])
def get_candidate_interviews(candidate_id: str, include_stages: bool = True):
    """Get all interviews for a specific candidate.

    Args:
        candidate_id: UUID of the candidate.
        include_stages: If True, includes all stages for each interview.

    Returns:
        List of InterviewProcess objects for the candidate.
    """
    try:
        return interview_service.get_candidate_interview_history(
            candidate_id, include_stages=include_stages
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/interviews/company/{company_name}", response_model=List[InterviewProcess])
def get_company_interviews_endpoint(
    company_name: str,
    status: Optional[InterviewStatus] = None
):
    """Get all interviews for a specific company.

    Args:
        company_name: Name of the company.
        status: Optional status filter.

    Returns:
        List of InterviewProcess objects for the company.
    """
    try:
        return interview_service.get_company_interviews(
            company_name, status_filter=status
        )
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.put("/interviews/{interview_id}", response_model=InterviewProcess)
def complete_interview(interview_id: str, request: CompleteInterviewRequest):
    """Complete an interview process and set final status.

    Args:
        interview_id: UUID of the interview process.
        request: CompleteInterviewRequest with final_status, offer_details, etc.

    Returns:
        Updated InterviewProcess object.

    Raises:
        HTTPException: If interview not found or invalid status.
    """
    try:
        return interview_service.complete_interview_process(
            interview_id=interview_id,
            final_status=request.final_status,
            offer_details=request.offer_details,
            final_outcome=request.final_outcome
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


# Interview Stage endpoints

@app.post("/interviews/{interview_id}/stages", response_model=InterviewStage)
def add_stage(interview_id: str, request: AddStageRequest):
    """Add a new stage to an interview process.

    Args:
        interview_id: UUID of the interview process.
        request: AddStageRequest with stage_name, stage_order, etc.

    Returns:
        Created InterviewStage object.

    Raises:
        HTTPException: If interview not found or stage_order invalid.
    """
    try:
        return interview_service.add_interview_stage(
            interview_id=interview_id,
            stage_name=request.stage_name,
            stage_order=request.stage_order,
            scheduled_date=request.scheduled_date
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/interviews/{interview_id}/stages", response_model=List[InterviewStage])
def get_interview_stages(interview_id: str):
    """Get all stages for an interview process.

    Args:
        interview_id: UUID of the interview process.

    Returns:
        List of InterviewStage objects ordered by stage_order.
    """
    try:
        interview = interview_service.get_interview_with_stages(interview_id)
        if not interview:
            raise HTTPException(status_code=404, detail=f"Interview {interview_id} not found")
        return interview.stages
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.put("/interviews/stages/{stage_id}", response_model=InterviewStage)
def update_stage_outcome(stage_id: str, request: UpdateStageOutcomeRequest):
    """Update the outcome and feedback for an interview stage.

    Args:
        stage_id: UUID of the stage.
        request: UpdateStageOutcomeRequest with outcome, ratings, feedback, etc.

    Returns:
        Updated InterviewStage object.

    Raises:
        HTTPException: If stage not found or ratings invalid.
    """
    try:
        ratings = {
            "overall_rating": request.overall_rating,
            "technical_rating": request.technical_rating,
            "culture_fit_rating": request.culture_fit_rating,
            "communication_rating": request.communication_rating
        }

        return interview_service.update_stage_outcome(
            stage_id=stage_id,
            outcome=request.outcome,
            ratings=ratings,
            feedback=request.feedback_notes,
            interviewer_names=request.interviewer_names,
            next_steps=request.next_steps
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


# Analytics & Feedback Loop endpoints

@app.get("/analytics/feeder/{feeder_source}")
def get_feeder_performance(feeder_source: str):
    """Get comprehensive performance report for a feeder pattern.

    Args:
        feeder_source: Name of the feeder pattern (e.g., "Amazon", "Google").

    Returns:
        Dictionary with performance metrics including:
        - Total candidates sourced
        - Placement rate
        - Outcome breakdown
        - Stage-by-stage performance

    Raises:
        HTTPException: If feeder not found or query fails.
    """
    try:
        return feedback_service.get_feeder_performance_report(feeder_source)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.post("/feedback/process-interview/{interview_id}")
def trigger_feedback_loop(interview_id: str):
    """Manually trigger feedback loop for an interview.

    This endpoint allows manual triggering of the feedback loop,
    which updates feeder conversion rates and placement history.

    Args:
        interview_id: UUID of the interview process.

    Returns:
        Dictionary with processing results and updated metrics.

    Raises:
        HTTPException: If interview not found or processing fails.
    """
    try:
        result = feedback_service.process_interview_outcome(interview_id)
        return result
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.post("/analytics/optimize-feeders", response_model=OptimizationResponse)
def optimize_general_feeders(request: OptimizationRequest):
    """Analyzes ALL HFT employees to discover general feeder patterns.

    This endpoint performs lookback analysis across ALL HFT firms to find
    universal feeder patterns. Analyzes employees at HFT firms, classifies
    them by job function, and extracts common previous companies. Results
    are saved to feeders_general.json.

    Args:
        request: OptimizationRequest with analysis parameters:
            - job_function: Optional filter for specific function
            - min_sample_size: Minimum candidates to qualify feeder (default: 15)
            - hft_companies: Optional list of HFT companies to analyze
            - update_feeders: Whether to update feeders_general.json (default: True)
            - create_backup: Whether to backup before updating (default: True)

    Returns:
        OptimizationResponse with:
        - success: Whether analysis completed
        - message: Status message
        - report: Detailed FeederAnalysisReport with metrics and comparisons
        - errors: List of errors (if any)

    Raises:
        HTTPException: If analysis fails, no candidates found, or invalid parameters.

    Example:
        POST /analytics/optimize-feeders
        {
            "job_function": "network_engineer",
            "min_sample_size": 15,
            "update_feeders": true
        }
    """
    try:
        report = feeder_optimization_service.analyze_general_feeders(
            job_function=request.job_function,
            min_sample_size=request.min_sample_size,
            hft_companies=request.hft_companies,
            update_feeders=request.update_feeders,
            create_backup=request.create_backup,
        )

        return OptimizationResponse(
            success=True,
            message=f"General feeder optimization completed. Analyzed {report.total_candidates_analyzed} HFT employees across {len(report.job_function_metrics)} job functions.",
            report=report,
            errors=[],
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"General feeder optimization failed: {str(error)}"
        )


@app.post("/analytics/optimize-firm-feeders/{firm_name}", response_model=OptimizationResponse)
def optimize_firm_feeders(firm_name: str, request: OptimizationRequest):
    """Analyzes ONE specific HFT firm's employees to discover firm-specific feeders.

    This endpoint performs lookback analysis on employees at a single firm to find
    feeders unique to that firm's hiring patterns. Results are saved to
    feeders_{firm}.json for firm-specific targeting.

    Args:
        firm_name: Name of the HFT firm to analyze (e.g., "Citadel", "Jane Street").
        request: OptimizationRequest with analysis parameters:
            - job_function: Optional filter for specific function
            - min_sample_size: Minimum candidates to qualify feeder (default: 15)
            - update_feeders: Whether to update feeders_{firm}.json (default: True)
            - create_backup: Whether to backup before updating (default: True)

    Returns:
        OptimizationResponse with:
        - success: Whether analysis completed
        - message: Status message
        - report: Detailed FeederAnalysisReport with firm-specific metrics
        - errors: List of errors (if any)

    Raises:
        HTTPException: If analysis fails, no employees found at firm, or invalid parameters.

    Example:
        POST /analytics/optimize-firm-feeders/Citadel
        {
            "job_function": "network_engineer",
            "min_sample_size": 15,
            "update_feeders": true
        }
    """
    try:
        report = feeder_optimization_service.analyze_firm_specific_feeders(
            firm_name=firm_name,
            job_function=request.job_function,
            min_sample_size=request.min_sample_size,
            update_feeders=request.update_feeders,
            create_backup=request.create_backup,
        )

        return OptimizationResponse(
            success=True,
            message=f"Firm-specific feeder optimization for {firm_name} completed. Analyzed {report.total_candidates_analyzed} employees across {len(report.job_function_metrics)} job functions.",
            report=report,
            errors=[],
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Firm-specific feeder optimization failed: {str(error)}"
        )


# Company Management endpoints

@app.post("/companies")
def create_company(request: CreateCompanyRequest):
    """Create a new company.

    Args:
        request: CreateCompanyRequest with company details.

    Returns:
        Created company record.

    Raises:
        HTTPException: If creation fails or company already exists.
    """
    try:
        return company_service.create_company(
            name=request.name,
            aliases=request.aliases,
            industry=request.industry,
            headquarters_city=request.headquarters_city,
            headquarters_country=request.headquarters_country,
            internal_notes=request.internal_notes
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/companies")
def list_companies():
    """Get all companies.

    Returns:
        List of all company records.
    """
    try:
        return company_service.list_companies()
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/companies/{company_id}")
def get_company(company_id: str):
    """Get a specific company by ID.

    Args:
        company_id: UUID of the company.

    Returns:
        Company record.
    """
    return company_service.get_company(company_id)


@app.get("/companies/search/{search_term}")
def search_companies(search_term: str):
    """Search companies by name or alias.

    Args:
        search_term: Term to search for (e.g., "SIG", "Citadel").

    Returns:
        List of matching company records.
    """
    return company_service.search_companies(search_term)


@app.put("/companies/{company_id}")
def update_company(company_id: str, request: UpdateCompanyRequest):
    """Update a company.

    Args:
        company_id: UUID of the company.
        request: UpdateCompanyRequest with fields to update.

    Returns:
        Updated company record.

    Raises:
        HTTPException: If company not found or invalid data.
    """
    try:
        # Convert request to dict, excluding None values
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        return company_service.update_company(company_id, updates)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.delete("/companies/{company_id}")
def delete_company(company_id: str):
    """Delete a company.

    Args:
        company_id: UUID of the company.

    Returns:
        Success message.
    """
    company_service.delete_company(company_id)
    return {"message": "Company deleted successfully"}


# Job Management endpoints

@app.post("/jobs")
def create_job(request: CreateJobRequest):
    """Create a new job.

    Args:
        request: CreateJobRequest with job details.

    Returns:
        Created job record.
    """
    try:
        return job_service.create_job(
            company_id=request.company_id,
            role_title=request.role_title,
            department=request.department,
            location=request.location,
            internal_notes=request.internal_notes
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/jobs")
def list_jobs(company_id: Optional[str] = None, status: Optional[JobStatus] = None):
    """List all jobs with optional filters.

    Args:
        company_id: Filter by company.
        status: Filter by status.

    Returns:
        List of job records.
    """
    try:
        return job_service.list_jobs(company_id, status)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/jobs/{job_id}")
def get_job(job_id: str):
    """Get a specific job by ID.

    Args:
        job_id: UUID of the job.

    Returns:
        Job record.
    """
    return job_service.get_job(job_id)


@app.put("/jobs/{job_id}")
def update_job(job_id: str, request: UpdateJobRequest):
    """Update a job.

    Args:
        job_id: UUID of the job.
        request: UpdateJobRequest with fields to update.

    Returns:
        Updated job record.
    """
    try:
        updates = {k: v for k, v in request.model_dump().items() if v is not None}
        return job_service.update_job(job_id, updates)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.post("/jobs/{job_id}/close")
def close_job(job_id: str, request: CloseJobRequest):
    """Close a job (mark as filled or closed).

    Args:
        job_id: UUID of the job.
        request: CloseJobRequest with optional filled_by_candidate_id.

    Returns:
        Updated job record.
    """
    try:
        return job_service.close_job(job_id, request.filled_by_candidate_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.post("/jobs/{job_id}/reopen")
def reopen_job(job_id: str):
    """Reopen a closed job.

    Args:
        job_id: UUID of the job.

    Returns:
        Updated job record.
    """
    try:
        return job_service.reopen_job(job_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.delete("/jobs/{job_id}")
def delete_job(job_id: str):
    """Delete a job.

    Args:
        job_id: UUID of the job.

    Returns:
        Success message.
    """
    job_service.delete_job(job_id)
    return {"message": "Job deleted successfully"}
