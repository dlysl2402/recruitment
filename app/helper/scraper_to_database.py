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


def transform_scraped_experience(scraped_data):

  transformed_experience = []

  for raw_exp in scraped_data['experience']: 
    transformed_experience.append(
      Experience(
        title=raw_exp['title'],
        company=raw_exp['company'],
        start_date=DateInfo(
          month=raw_exp['start_date']['month'],
          year=raw_exp['start_date']['year']
        ),
        end_date=DateInfo(
          month=raw_exp['end_date']['month'],
          year=raw_exp['end_date']['year']
        ),
        duration=raw_exp['duration'],
        description=raw_exp['description'],
        skills=raw_exp['skills']
      )
    )
  
  return transformed_experience

def transform_scraped_education(scraped_data):
  transformed_education = []

  for raw_edu in scraped_data['education']:
    transformed_education.append(
      Education(
        school=raw_edu['school'],
        degree=raw_edu['degree'],
        start_year=raw_edu['start_date']['year'],
        end_year=raw_edu['end_date']['year']
      )
    )

  return transformed_education

def parse_projects(scraped_data):
  parsed_projects = []

  for project in scraped_data['projects']:
    parsed_projects.append(
      Project(
        name=project['name'],
        start_date=project['start_date'],
        end_date=project['end_date'],
        description=project['description'],
        associated_company=project['associated_company'],
        project_urls=project['project_urls'],
        media_items=project['media_items']
      )
    )

  return parsed_projects

def transform_scraped_certifications(scraped_data):
  parsed_certs = []

  for cert in scraped_data['certifications']:
    parsed_certs.append(
      Certification(
        name=cert['name'],
        organization=cert['organization'],
        organization_urn=cert['organization_urn'],
        credential_id=cert['credential_id'],
        issue_date=cert['issue_date'],
        expiration_date=cert['expiration_date'],
        credential_url=cert['credential_url']
      )
    )
  
  return parsed_certs

def transform_scraped_skills(scraped_data):
  transformed_skills = []

  for raw_skills in scraped_data['skills']:
    transformed_skills.append(
      Skills(
        name=raw_skills['name'],
        endorsement_count=raw_skills['endorsement_count']
      )
    )

  return transformed_skills


def transform_scraped_profile(scraped_data):
  profile = LinkedInCandidate(
    # Basic info 
    first_name=scraped_data['basic_info']['first_name'],
    last_name=scraped_data['basic_info']['last_name'],
    headline=scraped_data['basic_info']['headline'],
    about=scraped_data['basic_info']['about'],
    location=Location(
      city=scraped_data['basic_info']['location']['city'],
      country=scraped_data['basic_info']['location']['country'],
      country_code=scraped_data['basic_info']['location']['country_code']
    ),
    linkedin_url=scraped_data['basic_info']['profile_url'],

    # Current position
    current_title=scraped_data['experience'][0]['title'],
    current_company=scraped_data['experience'][0]['company'],
    current_description=scraped_data['experience'][0]['description'],
    current_start_date=DateInfo(
      month=scraped_data['experience'][0]['start_date']['month'],
      year=scraped_data['experience'][0]['start_date']['year']
    ),

    # Full history
    experience=transform_scraped_experience(scraped_data),
    education=transform_scraped_education(scraped_data),
    projects=parse_projects(scraped_data),
    skills=transform_scraped_skills(scraped_data),
    certifications=transform_scraped_certifications(scraped_data)
  )

  return profile