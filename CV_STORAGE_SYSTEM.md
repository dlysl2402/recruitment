# CV Storage System Documentation

## Overview

Hybrid system where LinkedIn profiles and CVs co-exist independently. CVs are stored as files with metadata, admin team manually reviews and updates candidate profiles.

**Status:** Not yet implemented
**Created:** 2025-10-30

---

## Architecture

### Two Parallel Data Tracks

1. **Structured Profile** (`candidates` table)
   - Source of truth for scoring, search, and matching
   - Updated via LinkedIn scraping OR manual admin input from CVs
   - Pydantic models with validation

2. **CV Archive** (`candidate_cvs` table + Supabase Storage)
   - Reference documents with full audit trail
   - Version history (multiple CVs per candidate)
   - Processing status tracking

### Data Flow

```
CV Upload → Supabase Storage → Metadata Record Created →
Admin Downloads & Reviews → Admin Updates Candidate Profile →
Admin Marks CV as Processed
```

---

## Database Schema

### New Table: `candidate_cvs`

```sql
CREATE TABLE candidate_cvs (
    -- Primary
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,

    -- File Info
    file_url TEXT NOT NULL,              -- Supabase Storage URL
    file_name TEXT NOT NULL,             -- "john_smith_cv_2024.pdf"
    file_type TEXT NOT NULL,             -- "pdf", "docx", "doc"
    file_size_bytes INTEGER,

    -- Upload Metadata
    uploaded_at TIMESTAMP DEFAULT NOW(),
    uploaded_by TEXT,                    -- Admin user who uploaded
    source TEXT,                         -- "candidate_submitted", "recruiter_uploaded", "email"

    -- Versioning
    version_label TEXT,                  -- "Current", "2024-10", "Initial"
    is_primary BOOLEAN DEFAULT FALSE,    -- Flag current/best version
    notes TEXT,                          -- Admin notes about this CV

    -- Processing Tracking
    processed BOOLEAN DEFAULT FALSE,     -- Admin reviewed and updated profile
    processed_at TIMESTAMP,
    processed_by TEXT,                   -- Admin who processed
    processing_notes TEXT,               -- What was updated from this CV

    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_candidate_cvs_candidate ON candidate_cvs(candidate_id);
CREATE INDEX idx_candidate_cvs_uploaded ON candidate_cvs(uploaded_at DESC);
CREATE INDEX idx_candidate_cvs_processed ON candidate_cvs(processed);
```

### Update `candidates` Table

```sql
-- Add CV tracking fields
ALTER TABLE candidates ADD COLUMN last_cv_update TIMESTAMP;
ALTER TABLE candidates ADD COLUMN last_cv_id UUID REFERENCES candidate_cvs(id);
ALTER TABLE candidates ADD COLUMN data_sources JSONB DEFAULT '{"linkedin": true, "cv": false}';
```

**`data_sources` example:**
```json
{
  "linkedin": true,
  "cv": true,
  "last_linkedin_sync": "2024-10-30T10:00:00Z",
  "last_cv_update": "2024-10-30T15:30:00Z"
}
```

---

## Supabase Storage

### Bucket Setup

**Bucket name:** `candidate-cvs`

**Structure:**
```
candidate-cvs/
  ├── {candidate_id}/
  │   ├── 20241030_123456_john_smith_cv.pdf
  │   ├── 20240115_091234_john_smith_cv.docx
  │   └── 20230620_152341_john_smith_cv_old.pdf
```

**File naming convention:**
```
{timestamp}_{original_filename}
Example: 20241030_123456_cv.pdf
```

**Storage policies:**
- Authenticated users can upload
- Only admins can download (implement RLS)
- Files never publicly accessible
- Max file size: 10MB
- Allowed types: PDF, DOCX, DOC

---

## Pydantic Models

### File: `app/models/cv.py`

```python
class CandidateCV(BaseModel):
    id: Optional[str] = None
    candidate_id: str
    file_url: str
    file_name: str
    file_type: str
    file_size_bytes: Optional[int] = None
    uploaded_at: Optional[datetime] = None
    uploaded_by: Optional[str] = None
    source: Optional[str] = None
    version_label: Optional[str] = None
    notes: Optional[str] = None
    is_primary: bool = False
    processed: bool = False
    processed_at: Optional[datetime] = None
    processed_by: Optional[str] = None
    processing_notes: Optional[str] = None

class CVUploadResponse(BaseModel):
    cv_id: str
    candidate_id: str
    file_name: str
    file_url: str
    message: str
```

---

## Repository Layer

### File: `app/repositories/cv_repository.py`

**Class:** `CVRepository`

**Methods:**
- `create(cv_data)` - Save CV metadata
- `get_by_id(cv_id)` - Get CV metadata by ID
- `get_by_candidate(candidate_id)` - Get all CVs for candidate (ordered by date)
- `get_primary(candidate_id)` - Get primary CV for candidate
- `set_primary(cv_id, candidate_id)` - Set CV as primary (unsets others)
- `mark_processed(cv_id, processed_by, notes)` - Mark CV as processed
- `delete(cv_id)` - Delete CV metadata

**Repository only handles metadata, not files.**

---

## Service Layer

### File: `app/services/cv_service.py`

**Class:** `CVService`

**Configuration:**
```python
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.doc'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
```

**Methods:**

**Upload:**
- `upload_cv(candidate_id, file_content, file_name, uploaded_by, source, version_label, notes, set_as_primary)`
  - Validates candidate exists
  - Validates file type and size
  - Uploads to Supabase Storage
  - Creates metadata record
  - Optionally sets as primary

**Retrieve:**
- `get_candidate_cvs(candidate_id)` - List all CVs
- `get_cv(cv_id)` - Get CV metadata
- `download_cv(cv_id)` - Download file content from storage

**Manage:**
- `mark_processed(cv_id, processed_by, processing_notes)` - Mark as processed
- `delete_cv(cv_id)` - Delete file + metadata

**Helpers:**
- `_get_content_type(file_ext)` - Get MIME type
- `_extract_storage_path(file_url)` - Parse storage path from URL

---

## API Endpoints

### Upload CV
```
POST /candidates/{candidate_id}/cvs/upload
Content-Type: multipart/form-data

Form Fields:
- file: File (required)
- uploaded_by: string (optional) - Admin username
- source: string (default: "recruiter_uploaded") - "candidate_submitted" | "recruiter_uploaded" | "email"
- version_label: string (optional) - e.g., "Current", "2024-10", "Initial"
- notes: string (optional) - Admin notes
- set_as_primary: boolean (default: false)

Response:
{
  "cv_id": "uuid",
  "candidate_id": "uuid",
  "file_name": "john_smith_cv.pdf",
  "file_url": "https://...",
  "message": "CV uploaded successfully"
}
```

### List Candidate CVs
```
GET /candidates/{candidate_id}/cvs

Response:
[
  {
    "id": "uuid",
    "file_name": "cv_2024.pdf",
    "uploaded_at": "2024-10-30T10:00:00Z",
    "is_primary": true,
    "processed": true,
    "version_label": "Current"
  },
  ...
]
```

### Get CV Metadata
```
GET /cvs/{cv_id}

Response:
{
  "id": "uuid",
  "candidate_id": "uuid",
  "file_name": "cv.pdf",
  "file_type": "pdf",
  "file_size_bytes": 245678,
  "uploaded_at": "2024-10-30T10:00:00Z",
  "uploaded_by": "admin@company.com",
  "source": "recruiter_uploaded",
  "version_label": "2024-10",
  "notes": "Latest version from candidate",
  "is_primary": true,
  "processed": true,
  "processed_at": "2024-10-30T11:00:00Z",
  "processed_by": "admin@company.com",
  "processing_notes": "Updated experience and skills"
}
```

### Download CV
```
GET /cvs/{cv_id}/download

Response:
Binary file content with headers:
- Content-Type: application/pdf (or appropriate MIME type)
- Content-Disposition: attachment; filename="cv.pdf"
```

### Mark CV as Processed
```
PUT /cvs/{cv_id}/mark-processed
Content-Type: application/x-www-form-urlencoded

Form Fields:
- processed_by: string (required)
- processing_notes: string (optional)

Response:
{
  "id": "uuid",
  "processed": true,
  "processed_at": "2024-10-30T11:00:00Z",
  "processed_by": "admin@company.com",
  "processing_notes": "Updated experience and skills from CV"
}
```

### Set Primary CV
```
PUT /cvs/{cv_id}/set-primary

Response:
{
  "message": "CV set as primary"
}
```

### Delete CV
```
DELETE /cvs/{cv_id}

Response:
{
  "message": "CV deleted successfully"
}
```

---

## Admin Workflow

### 1. Upload CV
- Admin receives CV from candidate (email, upload form, etc.)
- Admin uploads via API with metadata:
  - Who uploaded it
  - Source (candidate submitted vs recruiter found)
  - Version label for tracking
  - Notes
  - Set as primary if it's the current one

### 2. View CVs for Candidate
- Admin lists all CVs for candidate
- Sees which are processed vs pending
- Identifies primary CV

### 3. Download and Review
- Admin downloads CV file
- Reviews content (experience, skills, projects, certifications, etc.)
- Identifies what needs to be added/updated in profile

### 4. Update Candidate Profile
- Admin manually updates candidate's structured profile
- Uses existing PUT /candidates/{id} endpoint
- Updates experience, skills, education, etc. based on CV

### 5. Mark as Processed
- Admin marks CV as processed
- Adds processing notes (e.g., "Updated experience and added 3 certifications")
- Tracks completion of review

---

## Use Cases

### Use Case 1: Initial CV Upload
**Scenario:** Candidate emails CV before LinkedIn profile scraped

1. Admin uploads CV with version_label="Initial", set_as_primary=true
2. Admin reviews CV and manually creates candidate profile
3. Admin marks CV as processed
4. Later: LinkedIn profile scraped and merged via duplicate detection

### Use Case 2: Profile Update
**Scenario:** Existing candidate sends updated CV with new job

1. Admin uploads new CV with version_label="2024-10", set_as_primary=true
2. Old CV automatically unset as primary
3. Admin reviews CV, sees new position
4. Admin updates candidate profile with new experience
5. Admin marks CV as processed with notes

### Use Case 3: Multiple CV Versions
**Scenario:** Track candidate progression over time

- 2021 CV: version_label="2021-06", processed=true
- 2023 CV: version_label="2023-03", processed=true
- 2024 CV: version_label="Current", is_primary=true, processed=true

Admin can review history and see career progression.

### Use Case 4: CV Audit Trail
**Scenario:** Need to verify what information came from where

- Check candidate.data_sources: `{"linkedin": true, "cv": true}`
- Check candidate.last_cv_id to see which CV was last used
- Review processing_notes on CV record
- Verify who processed and when

---

## Implementation Checklist

### Database Setup
- [ ] Create `candidate_cvs` table with indexes
- [ ] Add CV tracking fields to `candidates` table
- [ ] Create Supabase Storage bucket "candidate-cvs"
- [ ] Configure storage policies (authenticated upload, admin download)

### Backend Implementation
- [ ] Create `app/models/cv.py` with Pydantic models
- [ ] Create `app/repositories/cv_repository.py`
- [ ] Create `app/services/cv_service.py`
- [ ] Add CV service initialization in `app/main.py`
- [ ] Implement all API endpoints in `app/main.py`
- [ ] Add file upload dependency (FastAPI File, UploadFile)

### Storage Configuration
- [ ] Configure Supabase Storage bucket settings
- [ ] Set up RLS policies for bucket access
- [ ] Test file upload/download
- [ ] Configure max file size limits

### Testing
- [ ] Test CV upload (PDF, DOCX, DOC)
- [ ] Test file size validation
- [ ] Test file type validation
- [ ] Test listing CVs for candidate
- [ ] Test download CV
- [ ] Test mark as processed
- [ ] Test set primary (ensures only one primary)
- [ ] Test delete CV

### Documentation
- [ ] Add API documentation/examples
- [ ] Document admin workflow
- [ ] Create admin guide for CV processing

---

## Design Decisions

### Why Manual Processing?
- **Data Quality:** Human review ensures accuracy
- **Context:** Admin understands nuances between CV and LinkedIn
- **Flexibility:** Can selectively update profile (not all CV data needed)
- **Simpler:** No complex AI parsing, lower cost, fewer errors

### Why Store Multiple CVs?
- **Audit Trail:** Track candidate progression over time
- **Verification:** Compare versions if discrepancies arise
- **Historical Reference:** See how candidate presented themselves at different times
- **Compliance:** May need to retain all submitted documents

### Why Separate from Candidate Profile?
- **Independence:** CV storage doesn't interfere with LinkedIn scraping
- **Clean Architecture:** File storage separate from structured data
- **Flexibility:** Can have CVs without profiles, profiles without CVs
- **Performance:** Don't load large files when querying candidates

---

## Future Enhancements (Optional)

### AI-Assisted Parsing
- Use Claude API to extract structured data from PDF/DOCX
- Present suggestions to admin (still requires approval)
- Auto-populate fields with confidence scores

### CV Comparison
- Compare multiple CV versions
- Highlight differences between versions
- Flag potential discrepancies with LinkedIn

### Candidate Portal
- Let candidates upload their own CVs
- Candidates can see their CV history
- Email notifications when processed

### Advanced Search
- Full-text search within CVs (requires parsing/indexing)
- Filter candidates by CV upload date
- Search by CV processing status

---

## Notes

- CVs complement LinkedIn data, don't replace it
- Admin team has full control over data quality
- System prioritizes audit trail and version history
- No automatic merging of CV data into profiles
- Structured profile remains single source of truth for scoring

---

## Related Documentation

- Main project: `claude.md`
- Duplicate detection: See recent git commits
- Candidate model: `app/models/candidate.py`
- Interview system: `INTERVIEW_SYSTEM_IMPLEMENTATION.md`
