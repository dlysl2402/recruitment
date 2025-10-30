"""Backward compatibility module - imports from new location."""

from app.models.feeder import WeightedSkill, FeederPattern, RoleFeederConfig

__all__ = ["WeightedSkill", "FeederPattern", "RoleFeederConfig"]
