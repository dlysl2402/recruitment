"""Job function classifier for categorizing candidates based on job titles.

This module provides utilities to classify candidates into predefined job functions
(e.g., network engineers, linux engineers, trading system engineers) based on
title keyword matching patterns.
"""

import re
from typing import Dict, Optional, Tuple


# Job function classification configuration
JOB_FUNCTION_PATTERNS = {
    "network_engineer": {
        "keywords": [
            r"\bnetwork\s+engineer",
            r"\bnetwork\s+architect",
            r"\bnetwork\s+specialist",
            r"\bnetworking\s+engineer",
            r"\binfrastructure\s+engineer.*network",
            r"\bsite\s+reliability.*network",
        ],
        "display_name": "Network Engineer",
        "priority": 1,
    },
    "linux_engineer": {
        "keywords": [
            r"\blinux\s+engineer",
            r"\blinux\s+administrator",
            r"\blinux\s+system\s+admin",
            r"\bunix\s+engineer",
            r"\bsystems\s+engineer.*linux",
            r"\bdevops.*linux",
        ],
        "display_name": "Linux Engineer",
        "priority": 2,
    },
    "trading_system_engineer": {
        "keywords": [
            r"\btrading\s+system",
            r"\btrading\s+platform",
            r"\btrading\s+infrastructure",
            r"\bexecution\s+system",
            r"\border\s+management\s+system",
            r"\bmarket\s+data.*engineer",
            r"\blow\s+latency.*engineer",
            r"\bhft.*engineer",
        ],
        "display_name": "Trading System Engineer",
        "priority": 1,
    },
    "app_support_engineer": {
        "keywords": [
            r"\bapplication\s+support",
            r"\bapp\s+support",
            r"\bproduction\s+support",
            r"\btechnical\s+support.*engineer",
            r"\bsupport\s+engineer",
            r"\boperations\s+engineer",
        ],
        "display_name": "Application Support Engineer",
        "priority": 3,
    },
    "data_centre_engineer": {
        "keywords": [
            r"\bdata\s+cent(?:er|re)",
            r"\bdata\s+cent(?:er|re)\s+engineer",
            r"\bdc\s+engineer",
            r"\bfacility.*engineer",
            r"\binfrastructure.*data\s+cent(?:er|re)",
            r"\bcolocation.*engineer",
        ],
        "display_name": "Data Centre Engineer",
        "priority": 2,
    },
    "devops_engineer": {
        "keywords": [
            r"\bdevops\s+engineer",
            r"\bsite\s+reliability\s+engineer",
            r"\bsre\b",
            r"\bplatform\s+engineer",
            r"\binfrastructure\s+engineer",
            r"\bci/cd.*engineer",
        ],
        "display_name": "DevOps Engineer",
        "priority": 3,
    },
}


class JobFunctionClassifier:
    """Classifies job titles into predefined job functions."""

    @staticmethod
    def classify(title: str) -> Tuple[Optional[str], float]:
        """Classifies a job title into a job function.

        Uses keyword pattern matching with priority weighting. Returns the
        highest priority match if multiple patterns match.

        Args:
            title: The job title to classify.

        Returns:
            A tuple of (job_function_key, confidence_score).
            Returns (None, 0.0) if no match found.
            Confidence score ranges from 0.0 to 1.0 based on priority and match quality.

        Example:
            >>> JobFunctionClassifier.classify("Senior Network Engineer")
            ('network_engineer', 0.95)
            >>> JobFunctionClassifier.classify("Software Developer")
            (None, 0.0)
        """
        if not title:
            return None, 0.0

        title_lower = title.lower()
        matches = []

        for job_function, config in JOB_FUNCTION_PATTERNS.items():
            for pattern in config["keywords"]:
                if re.search(pattern, title_lower):
                    # Calculate confidence based on priority (1=highest, 3=lowest)
                    # Priority 1: 0.95, Priority 2: 0.85, Priority 3: 0.75
                    priority = config.get("priority", 3)
                    confidence = 1.0 - (priority - 1) * 0.1
                    matches.append((job_function, confidence, priority))
                    break  # One match per job function is sufficient

        if not matches:
            return None, 0.0

        # Return highest priority match (lowest priority number)
        matches.sort(key=lambda x: (x[2], -x[1]))  # Sort by priority, then confidence
        return matches[0][0], matches[0][1]

    @staticmethod
    def get_display_name(job_function: str) -> str:
        """Gets the human-readable display name for a job function.

        Args:
            job_function: The job function key (e.g., 'network_engineer').

        Returns:
            The display name (e.g., 'Network Engineer').
            Returns the input if not found in configuration.
        """
        if job_function in JOB_FUNCTION_PATTERNS:
            return JOB_FUNCTION_PATTERNS[job_function]["display_name"]
        return job_function

    @staticmethod
    def get_all_job_functions() -> Dict[str, str]:
        """Gets all available job functions with their display names.

        Returns:
            A dictionary mapping job function keys to display names.

        Example:
            >>> JobFunctionClassifier.get_all_job_functions()
            {'network_engineer': 'Network Engineer', 'linux_engineer': 'Linux Engineer', ...}
        """
        return {
            key: config["display_name"]
            for key, config in JOB_FUNCTION_PATTERNS.items()
        }

    @staticmethod
    def is_valid_job_function(job_function: str) -> bool:
        """Checks if a job function key is valid.

        Args:
            job_function: The job function key to validate.

        Returns:
            True if the job function exists in configuration, False otherwise.
        """
        return job_function in JOB_FUNCTION_PATTERNS
