from pydantic import BaseModel
from typing import List, Optional, Dict 

class FeederPattern(BaseModel):
  company: str
  company_aliases: List[str]
  priority: int   # 1=primary, 2=secondary, etc.
  min_tenure_years: float
  max_tenure_years: float
  required_titles: List[str] = [] # ["SRE", "Site Reliability Engineer"]
  boost_keywords: List[str] = [] # ["low-latency", "kernel"]
  score_boost: int # How many points to add

  # Track performance
  candidates_sourced: int = 0
  candidates_placed: int = 0
  conversion_rate: float = 0.0
  last_updated: str

class RoleFeederConfig(BaseModel):
  role_name: str # "network_engineer"
  display_name: str # "Network Engineer"

  feeders: List[FeederPattern]

  # Role-specific requirements
  required_skills: List[str] = [] # ["TCP/IP", "BGP"]
  nice_to_have_skills: List[str] = []

  # Negative signals
  avoid_companies: List[str] = []
  red_flags: List[str] = [] # ["less than 1 year tenure"]

  # Metadata
  typical_salary_range: Optional[Dict] = None
  notes: str = ""