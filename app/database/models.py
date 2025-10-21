from typing import List, Dict, Optional
from pydantic import BaseModel

class Candidate(BaseModel):
  name: str
  current_role: str
  current_company: Optional[str]
  skills: List[str]
  linkedin_url: str
  benchmark_scores: Dict[str, float] = {}