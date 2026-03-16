"""Configuration loading.

Loads configuration from the package defaults, then overlays user
configuration from ~/.tak/config.yaml.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

PACKAGE_CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "config"
USER_CONFIG_DIR = Path.home() / ".tak"


def load_config() -> dict[str, Any]:
    """Load tak configuration, overlaying user config on package defaults."""
    config = _load_yaml(PACKAGE_CONFIG_DIR / "default.yaml")
    user_config_path = USER_CONFIG_DIR / "config.yaml"

    if user_config_path.exists():
        user_config = _load_yaml(user_config_path)
        config = _deep_merge(config, user_config)

    return config


def load_agents_config() -> dict[str, Any]:
    """Load agent definitions, overlaying user config on package defaults."""
    config = _load_yaml(PACKAGE_CONFIG_DIR / "agents.yaml")
    user_agents_path = USER_CONFIG_DIR / "agents.yaml"

    if user_agents_path.exists():
        user_config = _load_yaml(user_agents_path)
        config = _deep_merge(config, user_config)

    return config


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
