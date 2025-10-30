# Recruitment ATS Project

## Project Overview

This is an Applicant Tracking System (ATS) for managing current and potential candidate profiles. The system includes a scoring algorithm to recommend the best candidates for specific job roles. Future plans include implementing machine learning models to improve candidate quality recommendations as the data infrastructure matures.

**Tech Stack:**
- FastAPI for REST API endpoints
- Supabase for database (PostgreSQL)
- Pydantic for data validation
- Python 3.12 (flexible on version)

## Development Commands

**Run Application:**
```bash
uvicorn app.main:app --reload
```

**Environment Setup:**
- Requires `.env` file with API keys (Supabase credentials, etc.)
- Uses `python-dotenv` to load environment variables

## Git Workflow

**Commit Messages:**
- Write clear, concise commit messages describing the changes
- Do NOT include AI-generated footers or traces
- Do NOT include "Co-Authored-By: Claude" or similar AI attribution
- Keep commits clean and professional

Example commit message:
```
Add claude.md with project guidelines and code style documentation

Documents the project architecture, Google-style Python conventions,
and development workflow for consistent code generation.
```

## Code Style Guidelines

Follow Google's Python Style Guide with the patterns established in this codebase.

### Indentation & Formatting
- Use 4-space indentation (never tabs)
- Use double quotes for strings
- Maximum line length: ~88-100 characters
- No automatic formatting tools - maintain style manually

### Naming Conventions
- `snake_case` for functions, variables, and module names
- `PascalCase` for class names
- `UPPER_SNAKE_CASE` for constants
- Private methods/attributes prefixed with single underscore: `_private_method`

### Type Hints
- Always include type hints for function parameters and return values
- Use `typing` module types: `List`, `Dict`, `Optional`, `Set`, `Any`
- Example:
  ```python
  def get_candidate(candidate_id: str) -> Optional[LinkedInCandidate]:
      """Retrieve a candidate by ID."""
      pass
  ```

### Import Organization
Organize imports into three groups with blank lines between:
1. Standard library imports
2. Third-party imports (FastAPI, Pydantic, Supabase, etc.)
3. Local application imports

Example:
```python
import json
from typing import Dict, Optional, List
from datetime import date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from supabase import Client

from app.models import LinkedInCandidate
from app.repositories.candidate_repository import CandidateRepository
```

### Documentation Standards

**Google-Style Docstrings Required:**
- All modules, classes, and functions must have docstrings
- Use Google-style format with sections: `Args:`, `Returns:`, `Raises:`, `Note:`
- Include clear descriptions of what the code does

Example function docstring:
```python
def filter_candidates(
    self,
    filters: Optional[Dict[str, str]] = None,
    skills: Optional[Set[str]] = None
) -> List[Dict[str, Any]]:
    """Retrieve candidates matching specified filters.

    Args:
        filters: Dictionary of field-value pairs for case-insensitive matching.
            Example: {"current_company": "Amazon"}
        skills: Set of skill names (lowercase) to filter by. Candidates must
            have all specified skills.

    Returns:
        List of candidate records matching the filters.

    Note:
        Multiple skills are combined with AND logic (all must match).
    """
```

Example class docstring:
```python
class CandidateRepository:
    """Repository for managing candidate data persistence.

    Encapsulates all database operations for candidates, providing
    a clean interface for data access without exposing database details.

    Attributes:
        db_client: Supabase client instance for database operations.
    """
```

### Pydantic Models
- Use Pydantic `BaseModel` for all data models
- Include comprehensive docstrings with `Attributes:` section
- Use `Optional` for nullable fields with default `None`
- Add `class Config` when needed (e.g., `extra = "ignore"`)

Example:
```python
class Experience(BaseModel):
    """Represents a work experience entry from a LinkedIn profile.

    Attributes:
        title: Job title.
        company: Company reference (name + optional ID).
        start_date: Employment start date.
        end_date: Employment end date (None if current position).
        skills: List of skills used in this role.
    """
    title: str
    company: CompanyReference
    start_date: DateInfo
    end_date: Optional[DateInfo] = None
    skills: List[str] = []
```

## Project Architecture

### Code Organization
Follow the established layered architecture pattern:

```
app/
├── models/              # Pydantic data models
├── repositories/        # Database access layer
├── services/           # Business logic layer
├── api/
│   └── schemas/        # Request/response schemas
├── database/           # Database client & queries
├── scrapers/           # LinkedIn scraping logic
└── main.py            # FastAPI application & endpoints
```

### Design Patterns

**Repository Pattern:**
- All database operations go through repository classes
- Repositories accept Supabase client in `__init__`
- Return Pydantic models or raw dicts as appropriate

**Service Layer:**
- Business logic lives in service classes
- Services coordinate between repositories
- Handle data transformation and validation

**API Layer:**
- FastAPI endpoints in `main.py`
- Use request/response schema classes from `api/schemas/`
- Handle HTTP exceptions with appropriate status codes
- Include comprehensive endpoint docstrings

### Database Conventions

**Supabase Client:**
- Initialized once in `app/database/client.py`
- Passed to repositories via dependency injection
- All queries use Supabase Python client methods

**Environment Variables:**
- Store all API keys and secrets in `.env` file
- Never commit `.env` to version control
- Use `python-dotenv` to load variables

**Error Handling:**
- Raise `ValueError` for business logic errors
- Catch in endpoints and convert to `HTTPException`
- Use appropriate HTTP status codes (400, 404, 409, 500)

## Testing

No testing framework currently implemented. Manual testing via API endpoints.

## Future Development

### Machine Learning Integration
- Planned once data infrastructure is mature
- Will improve candidate scoring and recommendations
- ML framework and architecture TBD based on data needs
