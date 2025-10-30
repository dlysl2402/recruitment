"""Backward compatibility module - imports from new location."""

from app.models.feeder import FeederPattern, RoleFeederConfig

__all__ = ["FeederPattern", "RoleFeederConfig"]
