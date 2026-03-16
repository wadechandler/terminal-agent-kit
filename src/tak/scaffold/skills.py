"""Generator for SKILL.md scaffold files."""

from __future__ import annotations

import string
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_skill_md(
    skill_name: str,
    description: str,
    output: Path,
    when_to_use: str = "perform this task",
    expected_output: str = "The task is completed successfully.",
    force: bool = False,
) -> None:
    """Generate a SKILL.md file from the built-in template.

    Args:
        skill_name: Human-readable skill name used as the document title.
        description: One-sentence description of what the skill does.
        output: Destination file path.
        when_to_use: Completion of the phrase "Use this skill when you want to …".
        expected_output: Description of what a successful run produces.
        force: When True, overwrite an existing file.

    Raises:
        FileExistsError: When *output* already exists and *force* is False.
    """
    if output.exists() and not force:
        raise FileExistsError(f"{output} already exists. Use --force to overwrite.")

    template = string.Template(
        (_TEMPLATE_DIR / "SKILL.md.tpl").read_text(encoding="utf-8")
    )
    content = template.safe_substitute(
        skill_name=skill_name,
        description=description,
        when_to_use=when_to_use,
        expected_output=expected_output,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
