"""FastAPI application for recruitment candidate management and scoring."""

from fastapi import FastAPI, HTTPException
from typing import List, Optional

from app.models import LinkedInCandidate
from app.models.interview import InterviewProcess, InterviewStage, InterviewStatus
from app.models.job import Job, JobStatus
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
from app.api.schemas.responses import CandidateScoreResponse, CandidateFilterResponse
from app.api.schemas.requests import (
    CreateInterviewRequest,
    AddStageRequest,
    UpdateStageOutcomeRequest,
    CompleteInterviewRequest
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

# Initialize repository and services
candidate_repository = CandidateRepository(supabase)
interview_repository = InterviewRepository(supabase)
company_repository = CompanyRepository(supabase)
job_repository = JobRepository(supabase)
candidate_service = CandidateService(candidate_repository)
company_service = CompanyService(company_repository)
job_service = JobService(job_repository)
scoring_service = ScoringService(candidate_repository)
scraping_service = ScrapingService(candidate_repository)

# Initialize feedback service and interview service with feedback loop
feedback_service = FeedbackService(interview_repository, candidate_service, company_service, job_service)
interview_service = InterviewService(interview_repository, company_service, job_service, feedback_service)


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
        List of InterviewProcess objects.

    Note:
        If both candidate_id and company_name provided, candidate_id takes precedence.
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
            # Return all interviews (consider pagination for production)
            raise HTTPException(
                status_code=400,
                detail="Must provide either candidate_id or company_name filter"
            )
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

    Raises:
        HTTPException: If company not found.
    """
    try:
        return company_service.get_company(company_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


@app.get("/companies/search/{search_term}")
def search_companies(search_term: str):
    """Search companies by name or alias.

    Args:
        search_term: Term to search for (e.g., "SIG", "Citadel").

    Returns:
        List of matching company records.
    """
    try:
        return company_service.search_companies(search_term)
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


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
        updates = {k: v for k, v in request.dict().items() if v is not None}
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

    Raises:
        HTTPException: If company not found.
    """
    try:
        company_service.delete_company(company_id)
        return {"message": "Company deleted successfully"}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


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
    try:
        return job_service.get_job(job_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))


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
        updates = {k: v for k, v in request.dict().items() if v is not None}
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
    try:
        job_service.delete_job(job_id)
        return {"message": "Job deleted successfully"}
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error))
