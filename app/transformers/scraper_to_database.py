"""Transform scraped LinkedIn data into Pydantic models for database storage."""

from typing import Optional, Dict, Any, List

from app.models import (
    DateInfo,
    CompanyReference,
    Location,
    Experience,
    Education,
    MediaItem,
    Project,
    Certification,
    Skills,
    LinkedInCandidate
)


def safe_date_info(date_dict: Optional[Dict[str, Any]]) -> Optional[DateInfo]:
    """Safely create DateInfo from a dictionary, handling missing or invalid data.

    Args:
        date_dict: Dictionary containing "month" and "year" keys.

    Returns:
        DateInfo object if year exists, None otherwise.
    """
    if not date_dict:
        return None

    year = date_dict.get("year")
    if year is None:
        return None

    return DateInfo(
        month=date_dict.get("month"),
        year=year
    )


def transform_scraped_experience(scraped_data: Dict[str, Any]) -> List[Experience]:
    """Transform raw experience data from LinkedIn scraper to Experience models.

    Args:
        scraped_data: Raw scraped profile data containing "experience" key.

    Returns:
        List of Experience objects.
    """
    transformed_experiences = []

    for experience_entry in scraped_data.get("experience", []):
        # Create CompanyReference (ID will be matched later)
        company_name = experience_entry.get("company", "")
        company_ref = CompanyReference(name=company_name, id=None)

        transformed_experiences.append(
            Experience(
                title=experience_entry.get("title", ""),
                company=company_ref,
                start_date=safe_date_info(experience_entry.get("start_date")),
                end_date=safe_date_info(experience_entry.get("end_date")),
                duration=experience_entry.get("duration", ""),
                description=experience_entry.get("description", ""),
                skills=experience_entry.get("skills", [])
            )
        )

    return transformed_experiences


def transform_scraped_education(scraped_data: Dict[str, Any]) -> List[Education]:
    """Transform raw education data from LinkedIn scraper to Education models.

    Args:
        scraped_data: Raw scraped profile data containing "education" key.

    Returns:
        List of Education objects.
    """
    transformed_educations = []

    for education_entry in scraped_data.get("education", []):
        transformed_educations.append(
            Education(
                school=education_entry.get("school", ""),
                degree=education_entry.get("degree", ""),
                start_year=education_entry.get("start_date", {}).get("year"),
                end_year=education_entry.get("end_date", {}).get("year")
            )
        )

    return transformed_educations


def safe_media_items(media_data: Optional[List[Any]]) -> List[MediaItem]:
    """Safely parse media items from raw data.

    Handles both dictionary format (with title, url, thumbnail) and legacy string format.

    Args:
        media_data: List of media items (dicts or strings).

    Returns:
        List of MediaItem objects.
    """
    if not media_data:
        return []

    media_items = []
    for item in media_data:
        if isinstance(item, dict):
            # LinkedIn scraper returns dictionaries with title, url, thumbnail
            media_items.append(
                MediaItem(
                    title=item.get("title", ""),
                    url=item.get("url"),
                    thumbnail=item.get("thumbnail")
                )
            )
        elif isinstance(item, str):
            # Legacy format: just strings (URLs or titles)
            media_items.append(MediaItem(title=item))

    return media_items


def parse_projects(scraped_data: Dict[str, Any]) -> List[Project]:
    """Transform raw project data from LinkedIn scraper to Project models.

    Args:
        scraped_data: Raw scraped profile data containing "projects" key.

    Returns:
        List of Project objects.
    """
    transformed_projects = []

    for project_entry in scraped_data.get("projects", []):
        transformed_projects.append(
            Project(
                name=project_entry.get("name", ""),
                start_date=project_entry.get("start_date", None),
                end_date=project_entry.get("end_date", None),
                description=project_entry.get("description", ""),
                associated_company=project_entry.get("associated_company", None),
                project_urls=project_entry.get("project_urls", []),
                media_items=safe_media_items(project_entry.get("media_items"))
            )
        )

    return transformed_projects


def transform_scraped_certifications(scraped_data: Dict[str, Any]) -> List[Certification]:
    """Transform raw certification data from LinkedIn scraper to Certification models.

    Args:
        scraped_data: Raw scraped profile data containing "certifications" key.

    Returns:
        List of Certification objects.
    """
    transformed_certifications = []

    for certification_entry in scraped_data.get("certifications", []):
        transformed_certifications.append(
            Certification(
                name=certification_entry.get("name", ""),
                organization=certification_entry.get("organization", ""),
                organization_urn=certification_entry.get("organization_urn", None),
                credential_id=certification_entry.get("credential_id", None),
                issue_date=certification_entry.get("issue_date", None),
                expiration_date=certification_entry.get("expiration_date", None),
                credential_url=certification_entry.get("credential_url", None)
            )
        )

    return transformed_certifications


def transform_scraped_skills(scraped_data: Dict[str, Any]) -> List[Skills]:
    """Transform raw skills data from LinkedIn scraper to Skills models.

    Args:
        scraped_data: Raw scraped profile data containing "skills" key.

    Returns:
        List of Skills objects with normalized names.
    """
    transformed_skills = []

    for skill_entry in scraped_data.get("skills", []):
        transformed_skills.append(
            Skills(
                name=skill_entry.get("name", "").lower(),
                display_name=skill_entry.get("name", ""),
                endorsement_count=skill_entry.get("endorsement_count", 0)
            )
        )

    return transformed_skills


def transform_scraped_profile(scraped_data: Dict[str, Any]) -> LinkedInCandidate:
    """Transform complete LinkedIn profile data to LinkedInCandidate model.

    Args:
        scraped_data: Complete raw profile data from LinkedIn scraper.

    Returns:
        LinkedInCandidate object with all sections populated.

    Raises:
        ValidationError: If required fields are missing or invalid.
    """
    basic_info = scraped_data.get("basic_info", {})
    location_data = basic_info.get("location", {})
    experiences = scraped_data.get("experience", [])
    current_experience = experiences[0] if experiences else {}

    profile = LinkedInCandidate(
        # Basic info
        first_name=basic_info.get("first_name", ""),
        last_name=basic_info.get("last_name", ""),
        headline=basic_info.get("headline", ""),
        about=basic_info.get("about", ""),
        location=Location(
            city=location_data.get("city", ""),
            country=location_data.get("country", ""),
            country_code=location_data.get("country_code", "")
        ),
        linkedin_url=basic_info.get("profile_url", ""),

        # Current position
        current_title=current_experience.get("title", ""),
        current_company=CompanyReference(
            name=current_experience.get("company", ""),
            id=None
        ) if current_experience.get("company") else None,
        current_description=current_experience.get("description", ""),
        current_start_date=safe_date_info(current_experience.get("start_date")),

        # Full history
        experience=transform_scraped_experience(scraped_data),
        education=transform_scraped_education(scraped_data),
        projects=parse_projects(scraped_data),
        skills=transform_scraped_skills(scraped_data),
        certifications=transform_scraped_certifications(scraped_data)
    )

    return profile


def db_row_to_candidate(database_row: Dict[str, Any]) -> LinkedInCandidate:
    """Convert a database row to LinkedInCandidate model.

    Args:
        database_row: Dictionary from Supabase query result.

    Returns:
        LinkedInCandidate object.

    Raises:
        ValidationError: If database data doesn't match expected schema.
    """
    return LinkedInCandidate(**database_row)
