"""Pydantic models for feeder optimization and analysis reports.

This module defines data models for representing discovered feeder patterns,
optimization metrics, and analysis reports.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DiscoveredFeeder(BaseModel):
    """Represents a feeder pattern discovered through analysis."""

    company: str = Field(..., description="Company name")
    sample_size: int = Field(..., description="Number of candidates from this company")
    avg_tenure_years: float = Field(..., description="Average tenure at this company")
    min_tenure_years: float = Field(..., description="Minimum tenure observed")
    max_tenure_years: float = Field(..., description="Maximum tenure observed")
    common_titles: List[str] = Field(
        default_factory=list,
        description="Most common job titles at this company",
    )
    frequency: float = Field(
        ...,
        description="Percentage of candidates from this company (0.0-1.0)",
    )
    confidence_score: float = Field(
        ...,
        description="Confidence score based on sample size (0.0-1.0)",
    )


class OptimizationMetrics(BaseModel):
    """Statistics for a job function optimization analysis."""

    job_function: str = Field(..., description="Job function key (e.g., 'network_engineer')")
    display_name: str = Field(..., description="Human-readable job function name")
    total_candidates: int = Field(..., description="Total HFT candidates analyzed")
    classified_candidates: int = Field(..., description="Candidates classified to this function")
    unique_companies: int = Field(..., description="Number of unique feeder companies found")
    avg_confidence: float = Field(..., description="Average confidence score of discovered feeders")
    top_feeders: List[DiscoveredFeeder] = Field(
        default_factory=list,
        description="Discovered feeder patterns ranked by frequency",
    )


class FeederComparison(BaseModel):
    """Comparison between existing and discovered feeder patterns."""

    company: str = Field(..., description="Company name")
    status: str = Field(
        ...,
        description="Status: 'existing', 'new', 'updated', 'removed'",
    )
    existing_metrics: Optional[Dict] = Field(
        None,
        description="Metrics from current feeders.json (if exists)",
    )
    discovered_metrics: Optional[Dict] = Field(
        None,
        description="Metrics from analysis (if discovered)",
    )
    changes: List[str] = Field(
        default_factory=list,
        description="List of detected changes",
    )


class FeederAnalysisReport(BaseModel):
    """Complete analysis report for feeder optimization."""

    timestamp: str = Field(..., description="Report generation timestamp (ISO format)")
    analysis_type: str = Field(
        default="feeder_optimization",
        description="Type of analysis performed",
    )
    job_function_filter: Optional[str] = Field(
        None,
        description="Job function filter applied (if any)",
    )
    min_sample_size: int = Field(
        default=15,
        description="Minimum sample size threshold used",
    )
    hft_companies_analyzed: List[str] = Field(
        default_factory=list,
        description="List of HFT companies included in analysis",
    )
    total_candidates_analyzed: int = Field(
        ...,
        description="Total number of candidates analyzed",
    )
    job_function_metrics: List[OptimizationMetrics] = Field(
        default_factory=list,
        description="Metrics per job function",
    )
    feeder_comparisons: Dict[str, List[FeederComparison]] = Field(
        default_factory=dict,
        description="Comparison per job function: {job_function: [comparisons]}",
    )
    feeders_updated: bool = Field(
        ...,
        description="Whether feeders.json was updated",
    )
    backup_path: Optional[str] = Field(
        None,
        description="Path to backup file (if created)",
    )
    report_path: Optional[str] = Field(
        None,
        description="Path to this report file",
    )
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Summary statistics and key findings",
    )


class OptimizationRequest(BaseModel):
    """Request model for feeder optimization API endpoint."""

    job_function: Optional[str] = Field(
        None,
        description="Optional filter for specific job function",
    )
    min_sample_size: int = Field(
        default=15,
        ge=0,
        description="Minimum sample size to consider a feeder pattern valid",
    )
    hft_companies: Optional[List[str]] = Field(
        None,
        description="Optional list of HFT companies to analyze (if None, uses defaults)",
    )
    update_feeders: bool = Field(
        default=True,
        description="Whether to update feeders.json with discovered patterns",
    )
    create_backup: bool = Field(
        default=True,
        description="Whether to backup feeders.json before updating",
    )


class OptimizationResponse(BaseModel):
    """Response model for feeder optimization API endpoint."""

    success: bool = Field(..., description="Whether optimization completed successfully")
    message: str = Field(..., description="Human-readable status message")
    report: FeederAnalysisReport = Field(..., description="Detailed analysis report")
    errors: List[str] = Field(
        default_factory=list,
        description="List of errors encountered (if any)",
    )
