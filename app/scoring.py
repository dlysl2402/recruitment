import os
import json
from datetime import datetime
from typing import Dict, Optional
from app.models import LinkedInCandidate, DateInfo
from app.feeder_models import RoleFeederConfig, FeederPattern

# Constants
FEEDER_CONFIG_FILE = "feeders.json"

# Cache for feeder configs
_FEEDER_CONFIGS = None

def load_feeder_configs(filepath: str = FEEDER_CONFIG_FILE) -> Dict[str, RoleFeederConfig]:
  """ Load and validate feeder configs from JSON """
  with open(filepath, 'r') as f:
    data = json.load(f)

  # Validate with Pydantic
  configs = {}
  for role_name, config_data in data.items():
    configs[role_name] = RoleFeederConfig(**config_data)

  return configs

def get_feeder_configs() -> Dict[str, RoleFeederConfig]:
  """Lazy-load and cache feeder configs"""
  global _FEEDER_CONFIGS

  if _FEEDER_CONFIGS is None:
    config_path = os.path.join(os.path.dirname(__file__), FEEDER_CONFIG_FILE)
    _FEEDER_CONFIGS = load_feeder_configs(config_path)

  return _FEEDER_CONFIGS

def score_candidate(
    candidate: LinkedInCandidate,
    target_role: str
)->Dict:
  """
  Score a candidate against a target role using feeder patterns
  Returns dict with score and breakdown
  """

  feeder_configs = get_feeder_configs()

  if target_role not in feeder_configs:
    raise ValueError(f"Unknown target role: '{target_role}'. Available roles: {list(feeder_configs.keys())}")

  config = feeder_configs[target_role]
  score = 0
  breakdown = {}

  # 1.) Company & Tenure match (biggest factor)
  for feeder in config.feeders: 
    if company_matches(candidate.current_company, feeder):
      tenure = calculate_tenure(candidate.current_start_date)

      if feeder.min_tenure_years <= tenure <= feeder.max_tenure_years:
        score += feeder.score_boost
        breakdown['feeder_match'] = f'{feeder.company} ({tenure:.1f}y)'

        # 2.) Title match bonus
        if feeder.required_titles and candidate.current_title:
          if any(title.lower() in candidate.current_title.lower()
                  for title in feeder.required_titles):
            score += 10
            breakdown['title_match'] = True

        # 3.) Keyword boost
        description = (candidate.current_description or "").lower()
        matched_keywords = [kw for kw in feeder.boost_keywords
                            if kw.lower() in description]
        if matched_keywords:
          keyword_score = min(len(matched_keywords) * 5, 15)
          score += keyword_score
          breakdown['keywords_matched'] = matched_keywords

        break # Only match one feeder
  
  # 4.) Required skills (critical)
  candidate_skills = {s.name.lower() for s in candidate.skills}
  required_match = [skill for skill in config.required_skills
                    if skill.lower() in candidate_skills]
  
  if len(required_match) == len(config.required_skills):
    score += 20
    breakdown['all_required_skills'] = True
  else:
    # Partial penalty
    missing = len(config.required_skills) - len(required_match)
    score -= missing * 5
    breakdown['missing_required_skills'] = missing
  
  # 5.) Nice-to-have skills (bonus)
  nice_matched = [skill for skill in config.nice_to_have_skills
                  if skill.lower() in candidate_skills]
  if nice_matched:
    score += len(nice_matched) * 3
    breakdown['nice_to_have_matched'] = nice_matched

  # 6.) Negative signals 
  if candidate.current_company in config.avoid_companies:
    score -= 20
    breakdown['avoid_company'] = True

  # 7.) Job hopping penalty
  if len(candidate.experience) >= 3:
    avg_tenure = calculate_average_tenure(candidate.experience)
    if avg_tenure < 1.5:
      score -= 15
      breakdown['job_hopper'] = avg_tenure

  return {
    'score': max(0, score), # Floor to 0
    'breakdown': breakdown
  }

def company_matches(candidate_company: str, feeder: FeederPattern)->bool:
  candidate_lower = candidate_company.lower().strip()

  # Check main company + all aliases
  all_companies = [feeder.company] + feeder.company_aliases

  for comp in all_companies: 
    comp_lower = comp.lower().strip()
    if candidate_lower == comp_lower or comp_lower in candidate_lower:
      return True
    
  return False

def calculate_tenure(start_date: DateInfo) -> float:
    """ Calculate years from start_date to now """
    if not start_date.year:
        return 0.0
    
    month_map = {
        'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
        'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
    }
    
    month_num = month_map.get(start_date.month, 1) if start_date.month else 1
    
    current = datetime.now()
    start = datetime(start_date.year, month_num, 1)
    
    days = (current - start).days
    return days / 365.25

def calculate_average_tenure(experiences) -> float:
  """ Calculate average tenure across all positions """
  tenures = []
  for exp in experiences:
    if exp.duration:
      years = parse_duration_to_years(exp.duration)
      tenures.append(years)

  return sum(tenures) / len(tenures) if tenures else 0

def parse_duration_to_years(duration: str) -> float:
  """ Parse '2 yrs 3 mos' to 2.25 """
  years = 0
  if 'yr' in duration:
    years += int(duration.split('yr')[0].strip().split()[-1])
  if 'mo' in duration:
    months = int(duration.split('mo')[0].strip().split()[-1])
    years += months / 12
  
  return years
