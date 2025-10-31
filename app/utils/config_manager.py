"""Configuration manager for feeder configs with backup and update utilities.

This module provides utilities for managing feeder configuration files, including
saving, backing up, and updating feeder patterns.
"""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, Optional, Any
from pathlib import Path

from app.feeder_models import RoleFeederConfig, FeederScope
from app.constants import FEEDER_CONFIG_FILE


# Config file naming conventions
GENERAL_FEEDERS_FILE = "feeders_general.json"
FIRM_FEEDERS_TEMPLATE = "feeders_{firm}.json"


class ConfigManager:
    """Manages feeder configuration file operations."""

    @staticmethod
    def get_config_path(filename: str = FEEDER_CONFIG_FILE) -> str:
        """Gets the absolute path to the configuration file.

        Args:
            filename: The configuration filename (default: feeders.json).

        Returns:
            Absolute path to the configuration file.
        """
        app_dir = os.path.dirname(os.path.dirname(__file__))
        return os.path.join(app_dir, filename)

    @staticmethod
    def save_feeder_configs(
        configs: Dict[str, RoleFeederConfig],
        filepath: Optional[str] = None,
        create_backup: bool = True,
    ) -> str:
        """Saves feeder configurations to JSON file.

        Args:
            configs: Dictionary mapping role names to RoleFeederConfig objects.
            filepath: Optional custom path. If None, uses default FEEDER_CONFIG_FILE.
            create_backup: If True, creates a timestamped backup before saving.

        Returns:
            Path to the saved configuration file.

        Raises:
            ValueError: If configs is empty or invalid.
            IOError: If file operations fail.

        Example:
            >>> configs = get_feeder_configs()
            >>> ConfigManager.save_feeder_configs(configs)
            '/path/to/app/feeders.json'
        """
        if not configs:
            raise ValueError("Cannot save empty feeder configurations")

        if filepath is None:
            filepath = ConfigManager.get_config_path()

        # Create backup if requested and file exists
        if create_backup and os.path.exists(filepath):
            ConfigManager.backup_feeder_configs(filepath)

        # Convert Pydantic models to dict for JSON serialization
        data = {}
        for role_name, config in configs.items():
            data[role_name] = config.model_dump(exclude_none=True)

        # Write to file with pretty formatting
        try:
            with open(filepath, "w") as config_file:
                json.dump(data, config_file, indent=2, ensure_ascii=False)
        except Exception as error:
            raise IOError(f"Failed to save feeder configs to {filepath}: {str(error)}")

        return filepath

    @staticmethod
    def backup_feeder_configs(filepath: Optional[str] = None) -> str:
        """Creates a timestamped backup of the feeder configuration file.

        Args:
            filepath: Path to the config file to backup. If None, uses default.

        Returns:
            Path to the backup file.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            IOError: If backup operation fails.

        Example:
            >>> ConfigManager.backup_feeder_configs()
            '/path/to/app/feeders.json.backup.2025-10-31_143022'
        """
        if filepath is None:
            filepath = ConfigManager.get_config_path()

        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Config file not found: {filepath}")

        # Generate timestamped backup filename
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        backup_path = f"{filepath}.backup.{timestamp}"

        try:
            shutil.copy2(filepath, backup_path)
        except Exception as error:
            raise IOError(f"Failed to create backup: {str(error)}")

        return backup_path

    @staticmethod
    def update_feeder_metrics(
        role_name: str,
        feeder_company: str,
        updates: Dict[str, Any],
        filepath: Optional[str] = None,
    ) -> RoleFeederConfig:
        """Updates metrics for a specific feeder pattern.

        Args:
            role_name: The role to update (e.g., 'network_engineer').
            feeder_company: The feeder company name to update.
            updates: Dictionary of field updates (e.g., {'candidates_sourced': 10}).
            filepath: Optional custom config file path.

        Returns:
            The updated RoleFeederConfig object.

        Raises:
            ValueError: If role or feeder not found.
            IOError: If file operations fail.

        Example:
            >>> ConfigManager.update_feeder_metrics(
            ...     'network_engineer',
            ...     'Amazon',
            ...     {'candidates_placed': 5, 'conversion_rate': 0.25}
            ... )
        """
        if filepath is None:
            filepath = ConfigManager.get_config_path()

        # Load current configs
        from app.scoring import load_feeder_configs
        configs = load_feeder_configs(filepath)

        if role_name not in configs:
            raise ValueError(f"Role '{role_name}' not found in configuration")

        role_config = configs[role_name]

        # Find the feeder to update
        feeder_found = False
        for feeder in role_config.feeders:
            if feeder.company.lower() == feeder_company.lower():
                # Update feeder metrics
                for key, value in updates.items():
                    if hasattr(feeder, key):
                        setattr(feeder, key, value)
                feeder_found = True
                break

        if not feeder_found:
            raise ValueError(
                f"Feeder '{feeder_company}' not found in role '{role_name}'"
            )

        # Save updated configs
        ConfigManager.save_feeder_configs(configs, filepath, create_backup=True)

        return role_config

    @staticmethod
    def ensure_reports_directory(base_dir: Optional[str] = None) -> str:
        """Ensures the reports directory exists for saving analysis reports.

        Args:
            base_dir: Base directory containing the app. If None, uses parent of app dir.

        Returns:
            Path to the reports directory.

        Example:
            >>> ConfigManager.ensure_reports_directory()
            '/path/to/recruitment/reports'
        """
        if base_dir is None:
            app_dir = os.path.dirname(os.path.dirname(__file__))
            base_dir = os.path.dirname(app_dir)

        reports_dir = os.path.join(base_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)

        return reports_dir

    @staticmethod
    def save_analysis_report(report: Dict, report_name: Optional[str] = None) -> str:
        """Saves an analysis report to the reports directory.

        Args:
            report: The report data as a dictionary.
            report_name: Optional custom report name. If None, generates timestamped name.

        Returns:
            Path to the saved report file.

        Raises:
            IOError: If file operation fails.

        Example:
            >>> report = {'job_function': 'network_engineer', 'feeders': [...]}
            >>> ConfigManager.save_analysis_report(report)
            '/path/to/reports/feeder_analysis_2025-10-31_143022.json'
        """
        reports_dir = ConfigManager.ensure_reports_directory()

        if report_name is None:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            report_name = f"feeder_analysis_{timestamp}.json"

        report_path = os.path.join(reports_dir, report_name)

        try:
            with open(report_path, "w") as report_file:
                json.dump(report, report_file, indent=2, ensure_ascii=False)
        except Exception as error:
            raise IOError(f"Failed to save report to {report_path}: {str(error)}")

        return report_path

    @staticmethod
    def get_firm_config_path(firm_name: str) -> str:
        """Gets the path to a firm-specific feeder configuration file.

        Args:
            firm_name: Name of the firm (e.g., "citadel", "janestreet").

        Returns:
            Absolute path to the firm-specific configuration file.

        Example:
            >>> ConfigManager.get_firm_config_path("citadel")
            '/path/to/app/feeders_citadel.json'
        """
        # Normalize firm name (lowercase, replace spaces with underscores)
        normalized_name = firm_name.lower().replace(" ", "_")
        filename = FIRM_FEEDERS_TEMPLATE.format(firm=normalized_name)
        return ConfigManager.get_config_path(filename)

    @staticmethod
    def load_general_feeders() -> Dict[str, RoleFeederConfig]:
        """Loads general feeder configurations that work across all firms.

        Returns:
            Dictionary mapping role names to general RoleFeederConfig objects.

        Raises:
            FileNotFoundError: If general feeders file doesn't exist.
            json.JSONDecodeError: If the file contains invalid JSON.
            ValidationError: If the config doesn't match expected schema.

        Example:
            >>> configs = ConfigManager.load_general_feeders()
            >>> configs['network_engineer'].scope == FeederScope.GENERAL
            True
        """
        from app.scoring import load_feeder_configs

        general_path = ConfigManager.get_config_path(GENERAL_FEEDERS_FILE)

        if not os.path.exists(general_path):
            raise FileNotFoundError(
                f"General feeders file not found: {general_path}. "
                "Run optimization to generate it."
            )

        configs = load_feeder_configs(general_path)

        # Set scope to GENERAL for all loaded configs
        for config in configs.values():
            config.scope = FeederScope.GENERAL
            config.target_firm = None

        return configs

    @staticmethod
    def load_firm_feeders(firm_name: str) -> Dict[str, RoleFeederConfig]:
        """Loads firm-specific feeder configurations for a trading firm.

        Args:
            firm_name: Name of the firm (e.g., "Citadel", "Jane Street").

        Returns:
            Dictionary mapping role names to firm-specific RoleFeederConfig objects.

        Raises:
            FileNotFoundError: If firm-specific feeders file doesn't exist.
            json.JSONDecodeError: If the file contains invalid JSON.
            ValidationError: If the config doesn't match expected schema.

        Example:
            >>> configs = ConfigManager.load_firm_feeders("Citadel")
            >>> configs['network_engineer'].target_firm == "Citadel"
            True
        """
        from app.scoring import load_feeder_configs

        firm_path = ConfigManager.get_firm_config_path(firm_name)

        if not os.path.exists(firm_path):
            raise FileNotFoundError(
                f"Firm-specific feeders file not found: {firm_path}. "
                f"Run optimization for {firm_name} to generate it."
            )

        configs = load_feeder_configs(firm_path)

        # Set scope and target_firm for all loaded configs
        for config in configs.values():
            config.scope = FeederScope.FIRM_SPECIFIC
            config.target_firm = firm_name

        return configs

    @staticmethod
    def save_firm_feeders(
        firm_name: str,
        configs: Dict[str, RoleFeederConfig],
        create_backup: bool = True,
    ) -> str:
        """Saves firm-specific feeder configurations.

        Args:
            firm_name: Name of the firm (e.g., "Citadel", "Jane Street").
            configs: Dictionary mapping role names to RoleFeederConfig objects.
            create_backup: If True, creates a timestamped backup before saving.

        Returns:
            Path to the saved configuration file.

        Raises:
            ValueError: If configs is empty or invalid.
            IOError: If file operations fail.

        Example:
            >>> configs = load_firm_feeders("Citadel")
            >>> ConfigManager.save_firm_feeders("Citadel", configs)
            '/path/to/app/feeders_citadel.json'
        """
        if not configs:
            raise ValueError("Cannot save empty feeder configurations")

        # Set metadata on all configs
        for config in configs.values():
            config.scope = FeederScope.FIRM_SPECIFIC
            config.target_firm = firm_name

        firm_path = ConfigManager.get_firm_config_path(firm_name)

        return ConfigManager.save_feeder_configs(
            configs, filepath=firm_path, create_backup=create_backup
        )

    @staticmethod
    def load_combined_feeders(
        role: str, firm_name: Optional[str] = None
    ) -> tuple[Optional[RoleFeederConfig], Optional[RoleFeederConfig]]:
        """Loads both general and firm-specific feeders for a role.

        Args:
            role: Role name (e.g., "network_engineer").
            firm_name: Optional firm name for firm-specific feeders.

        Returns:
            Tuple of (general_config, firm_config). Either can be None if not found.

        Example:
            >>> general, firm = ConfigManager.load_combined_feeders("network_engineer", "Citadel")
            >>> general.scope == FeederScope.GENERAL
            True
            >>> firm.target_firm == "Citadel"
            True
        """
        # Load general feeders
        general_config = None
        try:
            general_configs = ConfigManager.load_general_feeders()
            general_config = general_configs.get(role)
        except FileNotFoundError:
            pass

        # Load firm-specific feeders if requested
        firm_config = None
        if firm_name:
            try:
                firm_configs = ConfigManager.load_firm_feeders(firm_name)
                firm_config = firm_configs.get(role)
            except FileNotFoundError:
                pass

        return general_config, firm_config
