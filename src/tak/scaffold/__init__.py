"""Scaffold generators for standards files and project creation.

Public API::

    from tak.scaffold import (
        TechStack,
        detect_tech_stack,
        generate_agents_md,
        generate_rules,
        generate_skill_md,
        create_project,
    )
"""

from tak.scaffold.agents_md import generate_agents_md
from tak.scaffold.detect import TechStack, detect_tech_stack
from tak.scaffold.new_project import create_project
from tak.scaffold.rules import generate_rules
from tak.scaffold.skills import generate_skill_md

__all__ = [
    "TechStack",
    "create_project",
    "detect_tech_stack",
    "generate_agents_md",
    "generate_rules",
    "generate_skill_md",
]
