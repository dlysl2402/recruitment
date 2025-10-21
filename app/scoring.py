import yaml

def score_candidate(candidate: dict, benchmark_job: dict) -> float: 
  """ Score a candidate using benchmark job from database """
  score = 0.0

  # Skill scoring
  candidate_skills = [s.lower() for s in candidate.get("skills", [])]
  required_skills = [s.lower() for s in benchmark_job["required_skills"]]

  matched_skills = [s for s in candidate_skills if s in required_skills]

  if matched_skills:
    score += float(benchmark_job["skills_base_bonus"])
    extra = (len(matched_skills) - 1) * float(benchmark_job["skills_additional_bonus"])
    max_extra = float(benchmark_job["skills_max_bonus"]) - float(benchmark_job["skills_base_bonus"])
    score += min(extra, max_extra)

  # Company scoring
  company = candidate.get("company", "")
  company_weights = benchmark_job.get("company_weights", {})
  if company in company_weights: 
    score += float(company_weights[company])

  return round(score, 2)