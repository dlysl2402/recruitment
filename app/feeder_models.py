"""Backward compatibility module - imports from new location."""

from app.models.feeder import WeightedSkill, PedigreeCompany, FeederPattern, RoleFeederConfig

__all__ = ["WeightedSkill", "PedigreeCompany", "FeederPattern", "RoleFeederConfig"]
