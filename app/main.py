from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from app.scoring import score_candidate
from app.linkedin_scraper.scraper import scrape_linkedin_profiles
from app.helper.scraper_to_database import transform_scraped_profile

from app.models import (
  DateInfo,
  Experience,
  Education,
  LinkedInCandidate
)
from app.database.queries import (
  insert_candidate, 
  get_all_candidates, 
  insert_benchmark_job, 
  get_all_benchmark_jobs, 
  get_benchmark_job_by_title
)


app = FastAPI()

"""
START OF CANDIDATE CLASS
"""

"""
END OF CANDIDATE CLASS
"""

class BenchmarkJob(BaseModel):
  title: str
  required_skills: Optional[List[str]] = []
  skills_base_bonus: Optional[float] = 0.0
  skills_additional_bonus: Optional[float] = 0.0
  skills_max_bonus: Optional[float] = 0.0
  target_companies: Optional[List[str]] = []
  company_weights: Optional[Dict[str, float]] = {}



@app.get("/")
def root():
  return {"status": "ok"}



@app.post("/score")
def score(candidate: LinkedInCandidate, role: str):
  score_value = (candidate.dict(), role)
  return {"score": score_value}

@app.post("/score/{job_title}")
def score_with_benchmark(candidate: LinkedInCandidate, job_title: str):
  """ Score candidate using database benchmark """
  benchmark = get_benchmark_job_by_title(job_title)

  if not benchmark.data:
    raise HTTPException(status_code=404, detail="Benchmark job not found")

  job = benchmark.data[0]
  score = score_candidate(candidate.dict(), job)

  return {
    "candidate": candidate.name,
    "job": job_title,
    "score": score,
    "current_company": candidate.name,
    "matched_skills": [s for s in candidate.skills if s.lower() in [r.lower() for r in job["required_skills"]]]
  }



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




@app.post("/benchmark-jobs")
def create_benchmark_jobs(job: BenchmarkJob):
  """ Create a benchmark job """
  result = insert_benchmark_job(job.dict())
  return {"message": "Benchmark job created", "id": result.data[0]['id']}

@app.get("/benchmark-jobs")
def list_benchmark_jobs():
  """ Get all benchmark jobs """
  result = get_all_benchmark_jobs()
  return result.data





"""
========================================
=========== Linkedin Scraper ===========
========================================
"""


# Later transform this onto import-linkedin-profile-to-database(linkedin_profiles)
@app.post("/scrape-linkedin-profile")
def scrape_linkedin_profile(profile_url: str):
  """ Scrape a LinkedIn profile and return candidate data """

  try: 
    results = scrape_linkedin_profiles([profile_url])

    if not results: 
      raise HTTPException(status_code=404, details="No profile data found")
    
    profile = results[0]

    # initial stages of building this function
    transformed_profile = transform_scraped_profile(profile)

    return transformed_profile

  except HTTPException:
    raise
  except Exception as e: 
    raise HTTPException(status_code=500, detail=f"Scraping error: {str(e)}")


@app.post("/transform-scraped-data")
def transform_scraped_data(scraped_data):
  
  validated_experiences = transform_scraped_experience(scraped_data)
  
  return validated_experiences