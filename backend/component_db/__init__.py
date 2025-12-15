"""
Component database module for PlanMod.

Provides catalog of components, materials, and substitution rules.
"""

from backend.component_db.catalog import ComponentCatalog
from backend.component_db.materials import MaterialDatabase

__all__ = [
    "ComponentCatalog",
    "MaterialDatabase",
]


