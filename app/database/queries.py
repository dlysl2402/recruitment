import json
from typing import Dict, Optional, Set, Any
from app.database.client import supabase
from app.helper.scraper_to_database import db_row_to_candidate
from app.models import LinkedInCandidate


def insert_candidate(candidate_data: Dict[str, Any]):
  return supabase.table('candidates').insert(candidate_data).execute()

def get_all_candidates():
  return supabase.table('candidates').select("*").execute()

def get_candidate_with_id(candidate_id: str) -> Optional[LinkedInCandidate]:

  resp = (
    supabase.table('candidates')
      .select("*")
      .eq('id', candidate_id)
      .limit(1)
      .execute()
  )

  if not resp.data:
    return None

  raw = resp.data[0]
  return db_row_to_candidate(raw)

def get_candidates_with_filters(filters: Optional[Dict[str, str]] = None, skills: Optional[Set[str]] = None):
  query = supabase.table('candidates').select("*")

  # Apply regular filters
  if filters:
    for field, value in filters.items():
      query = query.ilike(field, f'%{value}%')

  # Apply JSONB array filters
  if skills:
    for skill in skills:
      # Check if skills array contains object with matching name
      query = query.filter('skills', 'cs', json.dumps([{"name": skill}]))

  return query.execute()