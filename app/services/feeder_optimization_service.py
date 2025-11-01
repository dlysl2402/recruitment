"""Service for optimizing feeder patterns based on HFT employee analysis.

This service analyzes current HFT employees, classifies them by job function,
and extracts common feeder patterns from their previous experience to optimize
recruitment targeting.
"""

from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
from collections import defaultdict, Counter

from app.repositories.candidate_repository import CandidateRepository
from app.repositories.company_repository import CompanyRepository
from app.models.candidate import LinkedInCandidate, Experience
from app.models.optimization import (
    DiscoveredFeeder,
    OptimizationMetrics,
    FeederComparison,
    FeederAnalysisReport,
)
from app.feeder_models import RoleFeederConfig, FeederPattern
from app.scoring import (
    load_feeder_configs,
    calculate_consecutive_company_tenure,
)
from app.utils.job_function_classifier import JobFunctionClassifier
from app.utils.company_matcher import CompanyMatcher
from app.utils.config_manager import ConfigManager
from app.utils.role_mapper import RoleMapper


# Default HFT companies to analyze
DEFAULT_HFT_COMPANIES = [
    "Citadel Securities",
    "Jane Street",
    "Jump Trading",
    "Hudson River Trading",
    "Tower Research Capital",
    "DRW",
    "Optiver",
    "IMC Trading",
    "Susquehanna International Group",
    "Flow Traders",
    "XTX Markets",
]


class FeederOptimizationService:
    """Service for analyzing and optimizing feeder patterns."""

    def __init__(
        self,
        candidate_repository: CandidateRepository,
        company_repository: CompanyRepository,
    ):
        """Initializes the service with required dependencies.

        Args:
            candidate_repository: Repository for candidate data access.
            company_repository: Repository for company data access.
        """
        self.candidate_repository = candidate_repository
        self.company_repository = company_repository

    def analyze_general_feeders(
        self,
        job_function: Optional[str] = None,
        min_sample_size: int = 15,
        hft_companies: Optional[List[str]] = None,
        update_feeders: bool = True,
        create_backup: bool = True,
    ) -> FeederAnalysisReport:
        """Analyzes ALL HFT employees to discover general feeder patterns.

        This method analyzes employees across all HFT firms to find universal
        feeder patterns that work regardless of target firm.

        Args:
            job_function: Optional filter for specific job function.
            min_sample_size: Minimum sample size to consider feeder valid.
            hft_companies: Optional list of HFT companies to analyze.
            update_feeders: Whether to update feeders_general.json.
            create_backup: Whether to backup before updating.

        Returns:
            FeederAnalysisReport with complete analysis and comparisons.

        Raises:
            ValueError: If job_function is invalid or no candidates found.
        """
        if job_function and not JobFunctionClassifier.is_valid_job_function(
            job_function
        ):
            raise ValueError(f"Invalid job function: {job_function}")

        # Use default HFT companies if not provided
        if hft_companies is None:
            hft_companies = DEFAULT_HFT_COMPANIES

        # Fetch HFT employees
        hft_candidates = self._fetch_hft_employees(hft_companies)
        if not hft_candidates:
            raise ValueError("No HFT employees found in database")

        # Run core optimization analysis
        from app.utils.config_manager import GENERAL_FEEDERS_FILE
        general_path = ConfigManager.get_config_path(GENERAL_FEEDERS_FILE)

        classified_candidates, job_function_metrics, feeder_comparisons = (
            self._run_optimization_analysis(
                candidates=hft_candidates,
                job_function_filter=job_function,
                min_sample_size=min_sample_size,
                config_filepath=general_path,
                comparison_context=None,
            )
        )

        # Update feeders_general.json if requested
        backup_path = None
        feeders_updated = False

        if update_feeders:
            backup_path = self._update_feeders_config(
                classified_candidates,
                job_function_metrics,
                create_backup,
                config_filepath=general_path,
            )
            feeders_updated = True

        # Generate report
        report = self._generate_report(
            timestamp=datetime.now().isoformat(),
            job_function_filter=job_function,
            min_sample_size=min_sample_size,
            hft_companies=hft_companies,
            total_candidates=len(hft_candidates),
            job_function_metrics=job_function_metrics,
            feeder_comparisons=feeder_comparisons,
            feeders_updated=feeders_updated,
            backup_path=backup_path,
        )

        # Save report to file
        report_path = ConfigManager.save_analysis_report(report.model_dump())
        report.report_path = report_path

        return report

    def analyze_firm_specific_feeders(
        self,
        firm_name: str,
        job_function: Optional[str] = None,
        min_sample_size: int = 15,
        update_feeders: bool = True,
        create_backup: bool = True,
    ) -> FeederAnalysisReport:
        """Analyzes ONE specific HFT firm's employees to discover firm-specific feeders.

        This method analyzes employees at a single firm to find feeders unique
        to that firm's hiring patterns.

        Args:
            firm_name: Name of the HFT firm to analyze (e.g., "Citadel").
            job_function: Optional filter for specific job function.
            min_sample_size: Minimum sample size to consider feeder valid.
            update_feeders: Whether to update feeders_{firm}.json.
            create_backup: Whether to backup before updating.

        Returns:
            FeederAnalysisReport with firm-specific analysis and comparisons.

        Raises:
            ValueError: If job_function invalid or no employees found at firm.
        """
        if job_function and not JobFunctionClassifier.is_valid_job_function(
            job_function
        ):
            raise ValueError(f"Invalid job function: {job_function}")

        # Fetch employees only from this specific firm
        firm_candidates = self._fetch_hft_employees([firm_name])
        if not firm_candidates:
            raise ValueError(f"No employees found at {firm_name} in database")

        # Run core optimization analysis
        firm_path = ConfigManager.get_firm_config_path(firm_name)

        classified_candidates, job_function_metrics, feeder_comparisons = (
            self._run_optimization_analysis(
                candidates=firm_candidates,
                job_function_filter=job_function,
                min_sample_size=min_sample_size,
                config_filepath=firm_path,
                comparison_context=firm_name,
            )
        )

        # Update feeders_{firm}.json if requested
        backup_path = None
        feeders_updated = False

        if update_feeders:
            backup_path = self._update_feeders_config(
                classified_candidates,
                job_function_metrics,
                create_backup,
                config_filepath=firm_path,
            )
            feeders_updated = True

        # Generate report
        report = self._generate_report(
            timestamp=datetime.now().isoformat(),
            job_function_filter=job_function,
            min_sample_size=min_sample_size,
            hft_companies=[firm_name],
            total_candidates=len(firm_candidates),
            job_function_metrics=job_function_metrics,
            feeder_comparisons=feeder_comparisons,
            feeders_updated=feeders_updated,
            backup_path=backup_path,
        )

        # Save report to file
        report_filename = f"feeder_analysis_{firm_name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.json"
        report_path = ConfigManager.save_analysis_report(report.model_dump(), report_filename)
        report.report_path = report_path

        return report

    def _run_optimization_analysis(
        self,
        candidates: List[LinkedInCandidate],
        job_function_filter: Optional[str],
        min_sample_size: int,
        config_filepath: str,
        comparison_context: Optional[str] = None,
    ) -> tuple[
        Dict[str, List[LinkedInCandidate]],
        List[OptimizationMetrics],
        Dict[str, List[FeederComparison]],
    ]:
        """Core optimization analysis logic shared by general and firm-specific methods.

        Args:
            candidates: List of HFT employees to analyze.
            job_function_filter: Optional filter for specific job function.
            min_sample_size: Minimum sample size for valid feeders.
            config_filepath: Path to config file for comparisons.
            comparison_context: Optional context label (e.g., firm name) for comparisons.

        Returns:
            Tuple of (classified_candidates, job_function_metrics, feeder_comparisons).
        """
        # Classify candidates by job function
        classified_candidates = self._classify_candidates(candidates)

        # Filter by job function if specified
        if job_function_filter:
            if job_function_filter not in classified_candidates:
                raise ValueError(
                    f"No candidates found for job function: {job_function_filter}"
                )
            classified_candidates = {
                job_function_filter: classified_candidates[job_function_filter]
            }

        # Analyze feeder patterns per job function
        job_function_metrics = []
        feeder_comparisons = {}

        for func, func_candidates in classified_candidates.items():
            # Extract feeder patterns
            discovered_feeders = self._extract_feeder_patterns(
                func_candidates, min_sample_size
            )

            # Calculate metrics
            metrics = self._calculate_metrics(
                func, func_candidates, discovered_feeders, len(candidates)
            )
            job_function_metrics.append(metrics)

            # Compare with existing feeders
            comparisons = self._compare_with_existing(
                func,
                discovered_feeders,
                config_path=config_filepath,
                context_label=comparison_context,
            )
            feeder_comparisons[func] = comparisons

        return classified_candidates, job_function_metrics, feeder_comparisons

    def _fetch_hft_employees(self, hft_companies: List[str]) -> List[LinkedInCandidate]:
        """Fetches candidates currently working at HFT companies.

        Args:
            hft_companies: List of HFT company names to search for.

        Returns:
            List of candidates currently employed at HFT companies.
        """
        all_candidates = []
        seen_ids = set()

        for company_name in hft_companies:
            # Use get_with_filters to find candidates by current company
            try:
                candidates_data = self.candidate_repository.get_with_filters(
                    filters={"current_company": company_name}
                )

                # Convert database rows to LinkedInCandidate objects
                from app.transformers.scraper_to_database import db_row_to_candidate

                for candidate_data in candidates_data:
                    # Avoid duplicates (in case company aliases match multiple searches)
                    if candidate_data["id"] not in seen_ids:
                        candidate = db_row_to_candidate(candidate_data)
                        all_candidates.append(candidate)
                        seen_ids.add(candidate_data["id"])

            except Exception:
                # Continue with other companies if one fails
                continue

        return all_candidates

    def _classify_candidates(
        self, candidates: List[LinkedInCandidate]
    ) -> Dict[str, List[LinkedInCandidate]]:
        """Classifies candidates by job function based on current title and company.

        Uses RoleMapper for company-specific role equivalence, then falls back to
        generic JobFunctionClassifier if no mapping exists.

        Args:
            candidates: List of candidates to classify.

        Returns:
            Dictionary mapping job function to list of candidates.
        """
        classified = defaultdict(list)

        for candidate in candidates:
            if candidate.current_title:
                job_function = None

                # Try RoleMapper first (company-aware classification)
                if candidate.current_company:
                    company_name = candidate.current_company.name if hasattr(candidate.current_company, 'name') else str(candidate.current_company)
                    if company_name:
                        job_function = RoleMapper.get_job_function(
                            company_name, candidate.current_title
                        )

                # Fall back to generic JobFunctionClassifier
                if not job_function:
                    job_function, confidence = JobFunctionClassifier.classify(
                        candidate.current_title
                    )

                if job_function:
                    classified[job_function].append(candidate)

        return dict(classified)

    def _extract_feeder_patterns(
        self, candidates: List[LinkedInCandidate], min_sample_size: int
    ) -> List[DiscoveredFeeder]:
        """Extracts feeder patterns from candidates' previous experience.

        Analyzes all non-current positions to find common feeder companies.
        Only looks at company, title, and tenure to avoid bias.

        Args:
            candidates: List of candidates in this job function.
            min_sample_size: Minimum candidates from a company to qualify.

        Returns:
            List of discovered feeder patterns sorted by frequency.
        """
        # Track feeder data by company
        feeder_data = defaultdict(lambda: {
            "candidates": set(),
            "tenures": [],
            "titles": [],
        })

        for candidate in candidates:
            if not candidate.experience:
                continue

            # Skip current position, analyze previous experience only
            for experience in candidate.experience[1:]:
                company_name = self._extract_company_name(experience)
                if not company_name:
                    continue

                # Calculate tenure for this position
                tenure = self._calculate_experience_tenure(experience)
                if tenure == 0:
                    continue

                # Track this feeder occurrence
                feeder_data[company_name]["candidates"].add(candidate.id)
                feeder_data[company_name]["tenures"].append(tenure)
                if experience.title:
                    feeder_data[company_name]["titles"].append(experience.title)

        # Convert to DiscoveredFeeder objects
        discovered_feeders = []
        total_candidates = len(candidates)

        for company, data in feeder_data.items():
            sample_size = len(data["candidates"])

            # Filter by minimum sample size
            if sample_size < min_sample_size:
                continue

            tenures = data["tenures"]
            avg_tenure = sum(tenures) / len(tenures)
            min_tenure = min(tenures)
            max_tenure = max(tenures)

            # Get most common titles (top 3)
            title_counts = Counter(data["titles"])
            common_titles = [title for title, _ in title_counts.most_common(3)]

            # Calculate frequency and confidence
            frequency = sample_size / total_candidates
            confidence = self._calculate_confidence_score(sample_size)

            discovered_feeders.append(
                DiscoveredFeeder(
                    company=company,
                    sample_size=sample_size,
                    avg_tenure_years=round(avg_tenure, 2),
                    min_tenure_years=round(min_tenure, 2),
                    max_tenure_years=round(max_tenure, 2),
                    common_titles=common_titles,
                    frequency=round(frequency, 3),
                    confidence_score=round(confidence, 2),
                )
            )

        # Sort by frequency (descending)
        discovered_feeders.sort(key=lambda f: f.frequency, reverse=True)

        return discovered_feeders

    def _extract_company_name(self, experience: Experience) -> Optional[str]:
        """Extracts company name from experience.

        Args:
            experience: Experience object.

        Returns:
            Company name string, or None if not available.
        """
        if hasattr(experience.company, "name"):
            return experience.company.name
        elif isinstance(experience.company, str):
            return experience.company
        return None

    def _calculate_experience_tenure(self, experience: Experience) -> float:
        """Calculates tenure in years for an experience.

        Args:
            experience: Experience object with start_date and end_date.

        Returns:
            Tenure in years, or 0 if cannot be calculated.
        """
        if not experience.start_date:
            return 0.0

        # If there's an end_date, calculate between start and end
        if experience.end_date:
            start_year = experience.start_date.year
            end_year = experience.end_date.year

            start_month = experience.start_date.month or 1
            end_month = experience.end_date.month or 12

            years = end_year - start_year
            months = end_month - start_month

            return max(0.0, years + (months / 12.0))

        # If no end_date (current position), calculate from start to now
        # But we're only analyzing previous positions, so this shouldn't happen
        return 0.0

    def _calculate_confidence_score(self, sample_size: int) -> float:
        """Calculates confidence score based on sample size.

        Uses a logarithmic scale to reward larger sample sizes.

        Args:
            sample_size: Number of candidates in the sample.

        Returns:
            Confidence score between 0.0 and 1.0.
        """
        if sample_size < 5:
            return 0.3
        elif sample_size < 15:
            return 0.5 + (sample_size - 5) * 0.03  # 0.5 to 0.8
        elif sample_size < 30:
            return 0.8 + (sample_size - 15) * 0.01  # 0.8 to 0.95
        else:
            return min(0.95 + (sample_size - 30) * 0.001, 1.0)  # Cap at 1.0

    def _calculate_metrics(
        self,
        job_function: str,
        candidates: List[LinkedInCandidate],
        discovered_feeders: List[DiscoveredFeeder],
        total_hft_candidates: int,
    ) -> OptimizationMetrics:
        """Calculates optimization metrics for a job function.

        Args:
            job_function: Job function key.
            candidates: Candidates in this function.
            discovered_feeders: Discovered feeder patterns.
            total_hft_candidates: Total HFT candidates analyzed.

        Returns:
            OptimizationMetrics object.
        """
        unique_companies = len(discovered_feeders)
        avg_confidence = (
            sum(f.confidence_score for f in discovered_feeders) / unique_companies
            if unique_companies > 0
            else 0.0
        )

        return OptimizationMetrics(
            job_function=job_function,
            display_name=JobFunctionClassifier.get_display_name(job_function),
            total_candidates=total_hft_candidates,
            classified_candidates=len(candidates),
            unique_companies=unique_companies,
            avg_confidence=round(avg_confidence, 2),
            top_feeders=discovered_feeders[:10],  # Top 10 feeders
        )

    def _compare_with_existing(
        self,
        job_function: str,
        discovered_feeders: List[DiscoveredFeeder],
        config_path: Optional[str] = None,
        context_label: Optional[str] = None,
    ) -> List[FeederComparison]:
        """Compares discovered feeders with existing feeder configuration.

        Args:
            job_function: Job function to compare.
            discovered_feeders: Newly discovered feeder patterns.
            config_path: Optional path to config file. If None, uses default feeders.json.
            context_label: Optional label for "new" feeder messages (e.g., firm name).

        Returns:
            List of FeederComparison objects.
        """
        comparisons = []

        # Load existing feeders
        try:
            if config_path is None:
                config_path = ConfigManager.get_config_path()
            existing_configs = load_feeder_configs(config_path)
            existing_config = existing_configs.get(job_function)
        except Exception:
            existing_config = None

        # Create comparison for each discovered feeder
        discovered_companies = {f.company.lower(): f for f in discovered_feeders}

        # Check existing feeders
        if existing_config:
            for feeder in existing_config.feeders:
                company_lower = feeder.company.lower()

                if company_lower in discovered_companies:
                    # Existing feeder still valid
                    discovered = discovered_companies[company_lower]
                    changes = self._detect_changes(feeder, discovered)

                    comparisons.append(
                        FeederComparison(
                            company=feeder.company,
                            status="updated" if changes else "existing",
                            existing_metrics={
                                "min_tenure": feeder.min_tenure_years,
                                "max_tenure": feeder.max_tenure_years,
                                "sample_size": feeder.sample_size,
                            },
                            discovered_metrics={
                                "avg_tenure": discovered.avg_tenure_years,
                                "sample_size": discovered.sample_size,
                                "frequency": discovered.frequency,
                            },
                            changes=changes,
                        )
                    )

                    # Remove from discovered to track processed
                    del discovered_companies[company_lower]
                else:
                    # Existing feeder not found in new analysis
                    comparisons.append(
                        FeederComparison(
                            company=feeder.company,
                            status="removed",
                            existing_metrics={
                                "min_tenure": feeder.min_tenure_years,
                                "max_tenure": feeder.max_tenure_years,
                            },
                            discovered_metrics=None,
                            changes=["No longer meets minimum sample size threshold"],
                        )
                    )

        # Remaining discovered feeders are new
        new_message = f"New feeder pattern discovered for {context_label}" if context_label else "New feeder pattern discovered"

        for discovered in discovered_companies.values():
            comparisons.append(
                FeederComparison(
                    company=discovered.company,
                    status="new",
                    existing_metrics=None,
                    discovered_metrics={
                        "avg_tenure": discovered.avg_tenure_years,
                        "sample_size": discovered.sample_size,
                        "frequency": discovered.frequency,
                    },
                    changes=[new_message],
                )
            )

        return comparisons

    def _detect_changes(
        self, existing: FeederPattern, discovered: DiscoveredFeeder
    ) -> List[str]:
        """Detects changes between existing and discovered feeder.

        Args:
            existing: Existing feeder pattern from feeders.json.
            discovered: Newly discovered feeder pattern.

        Returns:
            List of detected changes.
        """
        changes = []

        # Check sample size change
        if existing.sample_size:
            sample_change = discovered.sample_size - existing.sample_size
            if abs(sample_change) > 5:
                changes.append(f"Sample size changed by {sample_change:+d}")

        # Check if tenure range needs adjustment
        if discovered.min_tenure_years < existing.min_tenure_years:
            changes.append(
                f"Min tenure decreased: {existing.min_tenure_years} → {discovered.min_tenure_years}"
            )
        if discovered.max_tenure_years > existing.max_tenure_years:
            changes.append(
                f"Max tenure increased: {existing.max_tenure_years} → {discovered.max_tenure_years}"
            )

        return changes

    def _update_feeders_config(
        self,
        classified_candidates: Dict[str, List[LinkedInCandidate]],
        job_function_metrics: List[OptimizationMetrics],
        create_backup: bool,
        config_filepath: Optional[str] = None,
    ) -> Optional[str]:
        """Updates feeder config file with optimization results.

        Args:
            classified_candidates: Classified candidates by job function.
            job_function_metrics: Metrics for each job function.
            create_backup: Whether to create backup.
            config_filepath: Optional custom config file path (default: feeders.json).

        Returns:
            Path to backup file if created, None otherwise.
        """
        if config_filepath is None:
            config_path = ConfigManager.get_config_path()
        else:
            config_path = config_filepath

        # Backup existing config
        backup_path = None
        if create_backup:
            backup_path = ConfigManager.backup_feeder_configs(config_path)

        # Load existing configs
        try:
            configs = load_feeder_configs(config_path)
        except Exception:
            configs = {}

        # Update each job function with optimization metadata
        timestamp = datetime.now().isoformat()

        for metrics in job_function_metrics:
            job_function = metrics.job_function

            if job_function in configs:
                # Update last_optimized timestamp
                configs[job_function].last_optimized = timestamp

                # Update feeder metadata
                for discovered in metrics.top_feeders:
                    for feeder in configs[job_function].feeders:
                        if feeder.company.lower() == discovered.company.lower():
                            feeder.sample_size = discovered.sample_size
                            feeder.confidence_score = discovered.confidence_score
                            feeder.last_updated = timestamp[:10]  # YYYY-MM-DD
                            break

        # Save updated configs
        ConfigManager.save_feeder_configs(configs, config_path, create_backup=False)

        return backup_path

    def _generate_report(
        self,
        timestamp: str,
        job_function_filter: Optional[str],
        min_sample_size: int,
        hft_companies: List[str],
        total_candidates: int,
        job_function_metrics: List[OptimizationMetrics],
        feeder_comparisons: Dict[str, List[FeederComparison]],
        feeders_updated: bool,
        backup_path: Optional[str],
    ) -> FeederAnalysisReport:
        """Generates final analysis report.

        Args:
            timestamp: Report generation timestamp.
            job_function_filter: Job function filter (if any).
            min_sample_size: Minimum sample size threshold.
            hft_companies: HFT companies analyzed.
            total_candidates: Total candidates analyzed.
            job_function_metrics: Metrics per job function.
            feeder_comparisons: Comparisons per job function.
            feeders_updated: Whether feeders were updated.
            backup_path: Path to backup file.

        Returns:
            FeederAnalysisReport object.
        """
        # Calculate summary statistics
        total_feeders = sum(m.unique_companies for m in job_function_metrics)
        new_feeders = sum(
            len([c for c in comparisons if c.status == "new"])
            for comparisons in feeder_comparisons.values()
        )
        updated_feeders = sum(
            len([c for c in comparisons if c.status == "updated"])
            for comparisons in feeder_comparisons.values()
        )

        summary = {
            "total_job_functions_analyzed": len(job_function_metrics),
            "total_feeders_discovered": total_feeders,
            "new_feeders": new_feeders,
            "updated_feeders": updated_feeders,
            "average_feeders_per_function": round(
                total_feeders / len(job_function_metrics), 1
            )
            if job_function_metrics
            else 0,
        }

        return FeederAnalysisReport(
            timestamp=timestamp,
            analysis_type="feeder_optimization",
            job_function_filter=job_function_filter,
            min_sample_size=min_sample_size,
            hft_companies_analyzed=hft_companies,
            total_candidates_analyzed=total_candidates,
            job_function_metrics=job_function_metrics,
            feeder_comparisons=feeder_comparisons,
            feeders_updated=feeders_updated,
            backup_path=backup_path,
            summary=summary,
        )
