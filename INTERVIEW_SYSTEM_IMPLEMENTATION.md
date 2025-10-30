# Interview Tracking System - Implementation Guide

## Overview
Complete system for tracking candidate interviews, stages, outcomes, and feeding data back into scoring algorithms.

**Status:** Phase 1 Complete (Data Models)

---

## Phase 1: Data Models ✅ COMPLETED
- [x] Created `InterviewProcess` model (main interview tracking)
- [x] Created `InterviewStage` model (individual stages)
- [x] Created `OfferDetails` model (offer information)
- [x] Created enums: `InterviewStatus`, `StageOutcome`
- [x] Exported models from `app/models/__init__.py`

**Files:** `app/models/interview.py`

---

## Phase 2: Database Setup 🔄 TODO

### 2.1 Create Supabase Tables

**interview_processes table:**
```sql
CREATE TABLE interview_processes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    candidate_id UUID NOT NULL REFERENCES candidates(id),
    company_name TEXT NOT NULL,
    role_title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'in_progress',
    feeder_source TEXT,
    recruiter_name TEXT,
    final_outcome TEXT,
    offer_details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_interview_processes_candidate_id ON interview_processes(candidate_id);
CREATE INDEX idx_interview_processes_company_name ON interview_processes(company_name);
CREATE INDEX idx_interview_processes_status ON interview_processes(status);
CREATE INDEX idx_interview_processes_feeder_source ON interview_processes(feeder_source);
```

**interview_stages table:**
```sql
CREATE TABLE interview_stages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    interview_process_id UUID NOT NULL REFERENCES interview_processes(id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL,
    stage_order INTEGER NOT NULL,
    scheduled_date DATE,
    completed_date DATE,
    outcome TEXT NOT NULL DEFAULT 'pending',
    overall_rating INTEGER CHECK (overall_rating >= 1 AND overall_rating <= 5),
    technical_rating INTEGER CHECK (technical_rating >= 1 AND technical_rating <= 5),
    culture_fit_rating INTEGER CHECK (culture_fit_rating >= 1 AND culture_fit_rating <= 5),
    communication_rating INTEGER CHECK (communication_rating >= 1 AND communication_rating <= 5),
    feedback_notes TEXT,
    interviewer_names TEXT[],
    next_steps TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_interview_stages_process_id ON interview_stages(interview_process_id);
CREATE INDEX idx_interview_stages_outcome ON interview_stages(outcome);
CREATE INDEX idx_interview_stages_stage_name ON interview_stages(stage_name);
```

### 2.2 Row Level Security (RLS)
```sql
-- Enable RLS
ALTER TABLE interview_processes ENABLE ROW LEVEL SECURITY;
ALTER TABLE interview_stages ENABLE ROW LEVEL SECURITY;

-- Create policies (adjust based on your auth setup)
CREATE POLICY "Enable read access for all users" ON interview_processes FOR SELECT USING (true);
CREATE POLICY "Enable insert for all users" ON interview_processes FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for all users" ON interview_processes FOR UPDATE USING (true);

CREATE POLICY "Enable read access for all users" ON interview_stages FOR SELECT USING (true);
CREATE POLICY "Enable insert for all users" ON interview_stages FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update for all users" ON interview_stages FOR UPDATE USING (true);
```

---

## Phase 3: Repository Layer 🔄 TODO

### 3.1 Create InterviewRepository
**File:** `app/repositories/interview_repository.py`

**Methods to implement:**
```python
class InterviewRepository:
    def create_interview_process(interview_data: dict) -> dict
    def get_interview_by_id(interview_id: str) -> dict
    def get_interviews_by_candidate(candidate_id: str) -> list[dict]
    def get_interviews_by_company(company_name: str) -> list[dict]
    def update_interview_status(interview_id: str, status: str) -> dict
    def update_interview(interview_id: str, updates: dict) -> dict

    def create_interview_stage(stage_data: dict) -> dict
    def get_stages_by_interview(interview_id: str) -> list[dict]
    def update_stage(stage_id: str, updates: dict) -> dict
    def get_stage_by_id(stage_id: str) -> dict
```

**Key features:**
- Use Supabase client for database operations
- Handle JSONB serialization for offer_details
- Handle PostgreSQL array types for interviewer_names
- Proper error handling and validation

---

## Phase 4: Service Layer 🔄 TODO

### 4.1 Create InterviewService
**File:** `app/services/interview_service.py`

**Methods to implement:**
```python
class InterviewService:
    def create_interview_process(
        candidate_id: str,
        company_name: str,
        role_title: str,
        feeder_source: str = None,
        recruiter_name: str = None
    ) -> InterviewProcess

    def add_interview_stage(
        interview_id: str,
        stage_name: str,
        stage_order: int,
        scheduled_date: date = None
    ) -> InterviewStage

    def update_stage_outcome(
        stage_id: str,
        outcome: StageOutcome,
        ratings: dict = None,
        feedback: str = None
    ) -> InterviewStage

    def complete_interview_process(
        interview_id: str,
        final_status: InterviewStatus,
        offer_details: OfferDetails = None
    ) -> InterviewProcess

    def get_candidate_interview_history(candidate_id: str) -> list[InterviewProcess]

    def get_company_interviews(company_name: str, status: str = None) -> list[InterviewProcess]

    def calculate_conversion_rates(feeder_source: str) -> dict
```

**Business logic to implement:**
- Auto-update interview_process.updated_at on any change
- Validate stage_order is sequential
- Automatically update interview status based on stage outcomes
- Calculate success rates per feeder
- Prevent invalid state transitions

---

## Phase 5: API Endpoints 🔄 TODO

### 5.1 Add Routes to main.py
**File:** `app/main.py`

**Endpoints to create:**

#### Interview Process Management
```python
POST   /interviews                  # Create new interview process
GET    /interviews/{id}             # Get interview by ID
GET    /interviews                  # List all interviews (with filters)
PUT    /interviews/{id}             # Update interview
GET    /interviews/candidate/{id}  # Get all interviews for a candidate
GET    /interviews/company/{name}  # Get all interviews for a company
```

#### Interview Stage Management
```python
POST   /interviews/{id}/stages              # Add stage to interview
GET    /interviews/{id}/stages              # Get all stages for interview
PUT    /interviews/stages/{stage_id}        # Update stage
PUT    /interviews/stages/{stage_id}/outcome # Update stage outcome
```

#### Analytics & Reports
```python
GET    /interviews/analytics/conversion-rates          # Get conversion rates by feeder
GET    /interviews/analytics/stage-success-rates       # Success rates per stage type
GET    /interviews/analytics/company-stats/{company}   # Stats for specific company
```

**Request/Response schemas:**
- Use Pydantic models for validation
- Return proper HTTP status codes
- Include error handling

---

## Phase 6: Feedback Loop Integration 🔄 TODO

### 6.1 Update Feeder Conversion Rates
**File:** `app/services/interview_service.py` (add method)

```python
def update_feeder_conversion_rates(feeder_source: str):
    """
    Calculate and update conversion rates for a feeder pattern.

    Logic:
    1. Query all interviews with this feeder_source
    2. Count total interviews started (candidates_sourced)
    3. Count successful placements (status = offer_accepted)
    4. Calculate conversion_rate = placements / sourced
    5. Update feeders.json with new metrics
    """
```

**When to trigger:**
- When interview status changes to `offer_accepted`
- When interview status changes to `rejected_by_company` or `candidate_withdrew`
- On-demand via API endpoint

### 6.2 Add Placement History to Candidates
**File:** `app/models/candidate.py`

Add field to LinkedInCandidate:
```python
placement_history: List[PlacementRecord] = []

class PlacementRecord(BaseModel):
    company: str
    role: str
    placement_date: date
    offer_details: Optional[OfferDetails]
```

Update when interview reaches `offer_accepted` status.

### 6.3 Create Feedback Loop Service
**File:** `app/services/feedback_service.py`

```python
class FeedbackService:
    def process_interview_outcome(interview_id: str):
        """
        Process interview outcome and update all relevant data:
        1. Update feeder conversion rates
        2. Update candidate placement history
        3. Log metrics for analysis
        """

    def get_feeder_performance_report(feeder_source: str) -> dict:
        """
        Generate performance report for a feeder:
        - Total candidates sourced
        - Success rate by stage
        - Average time to hire
        - Common rejection reasons
        """
```

---

## Phase 7: Analytics & Reporting 🔄 TODO

### 7.1 Analytics Queries to Implement

**Conversion Funnel Analysis:**
```python
def get_conversion_funnel(feeder_source: str = None, company: str = None):
    """
    Returns:
    {
        "total_started": 100,
        "phone_screen_pass_rate": 0.80,
        "technical_pass_rate": 0.60,
        "onsite_pass_rate": 0.70,
        "offer_extended_rate": 0.50,
        "offer_accepted_rate": 0.40
    }
    """
```

**Stage Performance:**
```python
def get_stage_performance(stage_name: str):
    """
    Analyze performance for specific stage type:
    - Pass/fail rates
    - Average ratings
    - Common feedback themes
    """
```

**Company Insights:**
```python
def get_company_hiring_insights(company_name: str):
    """
    Returns:
    {
        "total_candidates_sent": 50,
        "interview_rate": 0.80,
        "offer_rate": 0.30,
        "avg_time_to_decision": "14 days",
        "preferred_feeders": ["Amazon", "Google"],
        "rejection_reasons": {...}
    }
    """
```

---

## Phase 8: Testing & Validation 🔄 TODO

### 8.1 Unit Tests
- Test each repository method
- Test service layer business logic
- Test feedback loop calculations

### 8.2 Integration Tests
- Test full interview flow end-to-end
- Test conversion rate updates
- Test API endpoints

### 8.3 Data Validation
- Ensure rating constraints (1-5)
- Validate status transitions
- Check foreign key relationships

---

## Phase 9: UI/Documentation 🔄 TODO

### 9.1 API Documentation
- Add OpenAPI/Swagger docs for all endpoints
- Include example requests/responses
- Document status flow diagrams

### 9.2 Usage Examples
Create example scripts:
- `examples/create_interview.py`
- `examples/update_stage_outcome.py`
- `examples/generate_conversion_report.py`

---

## Implementation Checklist

### Immediate Next Steps
1. [ ] Create Supabase tables (Phase 2)
2. [ ] Implement InterviewRepository (Phase 3)
3. [ ] Implement InterviewService (Phase 4)
4. [ ] Add API endpoints (Phase 5)
5. [ ] Implement feedback loop (Phase 6)
6. [ ] Build analytics queries (Phase 7)
7. [ ] Write tests (Phase 8)

### Priority Order
1. **High Priority:** Phases 2-5 (Core CRUD functionality)
2. **Medium Priority:** Phase 6 (Feedback loop)
3. **Low Priority:** Phases 7-9 (Analytics & polish)

---

## Success Metrics

Once fully implemented, you should be able to:
- ✅ Track every candidate interview from start to finish
- ✅ Record detailed feedback for each stage
- ✅ See conversion rates per feeder pattern
- ✅ Identify which companies prefer which candidate types
- ✅ Optimize sourcing strategy based on real data
- ✅ Automatically improve scoring over time

---

## Notes

- All database operations should use transactions for data consistency
- Consider adding automated backups for interview data
- May want to add attachment support (resumes, feedback docs) in future
- Consider notification system for interview updates
