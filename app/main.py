import json
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from app.feeder_models import RoleFeederConfig
from app.scoring import score_candidate, load_feeder_configs
from app.linkedin_scraper.profile_scraper import scrape_linkedin_profiles, extract_linkedin_username
from app.linkedin_scraper.company_scraper import scrape_linkedin_company
from app.helper.scraper_to_database import transform_scraped_profile, db_row_to_candidate

from app.models import (
  DateInfo,
  Experience,
  Education,
  LinkedInCandidate
)
from app.database.queries import (
  insert_candidate,
  get_candidate_with_id,
  get_all_candidates,
  get_candidates_with_filters
)


app = FastAPI()

# API Response Models
class CandidateScoreResponse(BaseModel):
  linkedin_url: str
  score: float
  breakdown: Dict

class CandidateFilterResponse(BaseModel):
  first_name: str
  last_name: str
  linkedin_url: str
  matched_skills: List[str]

@app.get("/")
def root():
  return {"status": "ok"}



@app.get("/score-candidate", response_model=CandidateScoreResponse)
def score_candidate_endpoint(
  candidate_id: str,
  target_role: str
):
  """ Score a candidate using feeder configuration """

  candidate = get_candidate_with_id(candidate_id)

  result = score_candidate(candidate, target_role)

  return CandidateScoreResponse(
    linkedin_url=candidate.linkedin_url,
    score=result.get('score', 0),
    breakdown=result.get('breakdown', {})
  )

@app.get("/get-top-candidates", response_model=List[CandidateScoreResponse])
def get_top_candidates(
  target_role: str,
  num_of_profiles: int
):
  """
  Scores all candidates in the database
  Returns the top X candidates for the role
  """

  profiles = get_all_candidates().data

  results = []

  for prof in profiles:
    candidate = db_row_to_candidate(prof)

    res = score_candidate(candidate, target_role)

    results.append(CandidateScoreResponse(
      linkedin_url=candidate.linkedin_url,
      score=res.get("score", 0),
      breakdown=res.get("breakdown", {})
    ))

  sorted_list = sorted(results, key=lambda x: x.score, reverse=True)[:num_of_profiles]

  return sorted_list

  

"""
========================================
========== Database Functions ==========
========================================
"""

@app.post("/candidates")
def create_candidate(candidate: LinkedInCandidate):
  """ Add a new candidate to the database"""
  result = insert_candidate(candidate.dict())
  return {"message": "Candidate added", "id": result.data[0]['id']}

@app.get("/candidates")
def list_candidates():
  """ Get all candidates from database"""
  result = get_all_candidates()
  return result.data

@app.get("/candidates/id")
def get_specific_candidate(candidate_id: str):
  return get_candidate_with_id(candidate_id)

@app.get("/candidates/filter", response_model=List[CandidateFilterResponse])
def filter_candiates(
  current_company: Optional[str] = None,
  skills: Optional[str] = None
):
  """ Filter candidates by company and/or skills """

  # Build filter dict
  filters = {}
  if current_company:
    filters['current_company'] = current_company
  # Add other filters here

  # Parse skills from comma-separated string
  requested_skills = None
  if skills:
    requested_skills = {s.strip().lower() for s in skills.split(',') if s.strip()}

  # Get filtered candidates
  result = get_candidates_with_filters(filters=filters, skills=requested_skills)

  list_of_candidates = []
  for candidate in result.data:

    candidate_skills = candidate.get('skills', [])

    # Extract skill names from JSONB array of objects: [{"name": "Python"}, ...]
    candidate_skill_names = {
      skill['name'].lower() for skill in candidate_skills
      if isinstance(skill, dict) and 'name' in skill
    }

    # Find intersection: which requested skills does this candidate have?
    matched_skills = [
      skill for skill in requested_skills
      if skill in candidate_skill_names
    ] if requested_skills else []

    list_of_candidates.append(CandidateFilterResponse(
      first_name=candidate.get('first_name', ''),
      last_name=candidate.get('last_name', ''),
      linkedin_url=candidate.get('linkedin_url', ''),
      matched_skills=matched_skills
    ))

  return list_of_candidates


"""
========================================
=========== Linkedin Scraper ===========
========================================
"""

@app.post("/linkedin-scrape-and-save-batch")
def scrape_and_save_candidate_batch(profile_usernames):
  """ 
  Scrape a list of LinkedIn profile and save it directly to the database
  separated by commas
  """

  try:
    # Split the urls delimited by ", "
    usernames = [username.strip() for username in profile_usernames.split(",") if username.strip()]
    if not usernames:
      raise HTTPException(status_code=400, detail="No valid usernames provided")


    # Scrape linkedin profiles using Apify API
    try:
      results = scrape_linkedin_profiles(usernames)
    except Exception as e:
      raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")

    # This will be used to store results summary
    success = []
    failed = []

    # For each profile in results, transform and store to database

    for username, profile_data in zip(usernames, results):
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

        # This may raise error 23505 on duplicate
        db_result = insert_candidate(candidate_dict)

        if not db_result.data:
          raise ValueError("Insert returned no data")

        record = db_result.data[0]
        success.append({
          "id": record.get("id", ""),
          "candidate_name": f"{candidate.first_name} {candidate.last_name}",
          "current_company": candidate.current_company,
          "status": "inserted"
        })

      except Exception as e:
        error_msg = str(e)

        # Detect duplicate
        is_duplicate = any(
          indicator in error_msg
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
            "error": f"Processing failed: {error_msg}",
            "status": "failed"
          })
  
    # Return both success and failed
    response = {"success": success}
    if failed:
      response["failed"] = failed

    return response
  
  except HTTPException:
    raise
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")
  

@app.post("/linkedin-company-employees-scrape")
def scrape_company_employees(
  company_url: str, 
  max_employees: Optional[int] = None, 
  job_title: Optional[str] = None, 
  batch_name: Optional[str] = None):

  try:
    # Fetch all employees in a company (within the parameters given)
    results = scrape_linkedin_company(company_url, max_employees, job_title, batch_name)

    #  With every person in the list, add their username to a list ["person1", "person2", ... "personx"]
    usernames = []
    for person in results:
      usernames.append(extract_linkedin_username(person.get("profile_url", "")))

    # Convering into a single string delimited by ", "
    usernames_str = ", ".join(usernames)

    result = scrape_and_save_candidate_batch(usernames_str)

    return result
  
  except HTTPException:
    raise
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"Company scraping failed: {str(e)}")

