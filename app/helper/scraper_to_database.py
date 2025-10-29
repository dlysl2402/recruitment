from typing import Optional, Dict, Any
from app.models import (
  DateInfo,
  Location,
  Experience,
  Education,
  Project,
  Certification,
  Skills,
  LinkedInCandidate
)

def safe_date_info(date_dict) -> Optional[DateInfo]:
  """
    Safely create DateInfo from a date dictionary.
    Returns None if date_dict is empty, None, or missing year.
  """
  
  if not date_dict:
    return None

  year = date_dict.get('year')
  if year is None:
    return None
  
  return DateInfo(
    month=date_dict.get('month'),
    year=year
  )

def transform_scraped_experience(scraped_data):

  transformed_experience = []

  for raw_exp in scraped_data.get('experience', []): 
    transformed_experience.append(
      Experience(
        title=raw_exp.get('title', ''),
        company=raw_exp.get('company', ''),
        start_date=safe_date_info(raw_exp.get('start_date')),
        end_date=safe_date_info(raw_exp.get('end_date')),
        duration=raw_exp.get('duration', ''),
        description=raw_exp.get('description', ''),
        skills=raw_exp.get('skills', [])
      )
    )

  return transformed_experience

def transform_scraped_education(scraped_data):
  transformed_education = []

  for raw_edu in scraped_data.get('education', []):
    transformed_education.append(
      Education(
        school=raw_edu.get('school', ''),
        degree=raw_edu.get('degree', ''),
        start_year=raw_edu.get('start_date', {}).get('year'),
        end_year=raw_edu.get('end_date', {}).get('year')
      )
    )

  return transformed_education

def parse_projects(scraped_data):
  parsed_projects = []

  for project in scraped_data.get('projects', []):
    parsed_projects.append(
      Project(
        name=project.get('name', ''),
        start_date=project.get('start_date', None),
        end_date=project.get('end_date', None),
        description=project.get('description', ''),
        associated_company=project.get('associated_company', None),
        project_urls=project.get('project_urls', []),
        media_items=project.get('media_items', [])
      )
    )

  return parsed_projects

def transform_scraped_certifications(scraped_data):
  parsed_certs = []

  for cert in scraped_data.get('certifications', []):
    parsed_certs.append(
      Certification(
        name=cert.get('name', ''),
        organization=cert.get('organization', ''),
        organization_urn=cert.get('organization_urn', None),
        credential_id=cert.get('credential_id', None),
        issue_date=cert.get('issue_date', None),
        expiration_date=cert.get('expiration_date', None),
        credential_url=cert.get('credential_url', None)
      )
    )
  
  return parsed_certs

def transform_scraped_skills(scraped_data):
  transformed_skills = []

  for raw_skills in scraped_data.get('skills', []):
    transformed_skills.append(
      Skills(
        name=raw_skills.get('name', '').lower(),
        display_name=raw_skills.get('name', ''),
        endorsement_count=raw_skills.get('endorsement_count', 0)
      )
    )

  return transformed_skills

def transform_scraped_profile(scraped_data):

  basic_info = scraped_data.get('basic_info', {})
  location_data = basic_info.get('location', {})
  experiences = scraped_data.get('experience', [])
  current_exp = experiences[0] if experiences else {}

  profile = LinkedInCandidate(
    # Basic info 
    first_name=basic_info.get('first_name', ''),
    last_name=basic_info.get('last_name', ''),
    headline=basic_info.get('headline', ''),
    about=basic_info.get('about', ''),
    location=Location(
      city=location_data.get('city', ''),
      country=location_data.get('country', ''),
      country_code=location_data.get('country_code', '')
    ),
    linkedin_url=basic_info.get('profile_url', ''),

    # Current position
    current_title=current_exp.get('title', ''),
    current_company=current_exp.get('company', ''),
    current_description=current_exp.get('description', ''),
    current_start_date=safe_date_info(current_exp.get('start_date')),

    # Full history
    experience=transform_scraped_experience(scraped_data),
    education=transform_scraped_education(scraped_data),
    projects=parse_projects(scraped_data),
    skills=transform_scraped_skills(scraped_data),
    certifications=transform_scraped_certifications(scraped_data)
  )

  return profile

def db_row_to_candidate(row: Dict[str, Any]) -> LinkedInCandidate:
  """
    Convert a single row from Supabase (dict) → LinkedInCandidate model.
    Raises ValidationError if data is malformed.
  """
  
  return LinkedInCandidate(**row)