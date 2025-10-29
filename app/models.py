from pydantic import BaseModel
from typing import List, Optional, Dict

class DateInfo(BaseModel):
  month: Optional[str]= None,
  year: Optional[int] = None

class Location(BaseModel):
  city: str 
  country: str
  country_code: str

class Experience(BaseModel):
  title: str
  company: str
  company_linkedin_url: Optional[str] = None
  start_date: DateInfo
  end_date: Optional[DateInfo] = None
  duration: Optional[str] = None
  description: Optional[str] = None
  skills: List[str] = []

class Education(BaseModel):
  school: str
  degree: Optional[str] = None
  start_year: Optional[int] = None
  end_year: Optional[int] = None

class Project(BaseModel):
  name: str
  start_date: Optional[str] = None
  end_date: Optional[str] = None
  description: Optional[str] = None
  associated_company: Optional[str] = None
  project_urls: Optional[List[str]] = []
  media_items: Optional[List[str]] = []
  
class Certification(BaseModel):
  name: str
  organization: str
  organization_urn: Optional[str] = None
  credential_id: Optional[str] = None
  issue_date: Optional[str] = None
  expiration_date: Optional[str] = None
  credential_url: Optional[str] = None

class Skills(BaseModel):
  name: str
  display_name: str
  endorsement_count: int

class LinkedInCandidate(BaseModel):
  # Basic info 
  first_name: str
  last_name: str
  headline: Optional[str] = None
  about: Optional[str] = None
  location: Location
  linkedin_url: str

  # Current position
  current_title: Optional[str] = None
  current_company: Optional[str] = None
  current_description: Optional[str] = None 
  current_start_date: DateInfo

  # Full history
  experience: List[Experience] = []
  education: List[Education] = []
  projects: List[Project] = []
  skills: List[Skills] = []
  certifications: List[Certification] = []
  
  # Scoring
  benchmark_scores: Dict[str, float] = {}

class Config:
  extra = "ignore"