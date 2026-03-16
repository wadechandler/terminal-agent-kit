"""Generator for AGENTS.md scaffold files."""

from __future__ import annotations

import string
from pathlib import Path

from tak.scaffold.detect import TechStack, detect_tech_stack

_TEMPLATE_DIR = Path(__file__).parent / "templates"


def _load_template(name: str) -> string.Template:
    """Load a named template from the templates directory.

    Args:
        name: Template filename (e.g. ``"AGENTS.md.tpl"``).

    Returns:
        A :class:`string.Template` ready for substitution.
    """
    return string.Template((_TEMPLATE_DIR / name).read_text(encoding="utf-8"))


def _build_tech_stack_section(stack: TechStack) -> str:
    """Render the tech-stack bullet list from a detected TechStack.

    Args:
        stack: The detected tech stack.

    Returns:
        A Markdown bullet-list string suitable for embedding in AGENTS.md.
    """
    items: list[str] = [f"- **Language**: {stack.language}"]
    if stack.framework:
        items.append(f"- **Framework**: {stack.framework}")
    if stack.build_system:
        items.append(f"- **Build System**: {stack.build_system}")
    if stack.test_framework:
        items.append(f"- **Testing**: {stack.test_framework}")
    for lang in stack.extra_languages:
        items.append(f"- **Also**: {lang}")
    return "\n".join(items)


def generate_agents_md(
    project_name: str,
    output: Path,
    project_path: Path | None = None,
    project_description: str = "",
    force: bool = False,
    stack: TechStack | None = None,
) -> TechStack:
    """Generate an AGENTS.md file from the built-in template.

    When *stack* is supplied it is used directly, skipping file-system
    detection.  Otherwise *project_path* (defaulting to cwd) is scanned.

    Args:
        project_name: Human-readable project name used as the document title.
        output: Destination file path.
        project_path: Project root for tech-stack detection; ignored when
            *stack* is provided.  Defaults to cwd when both are omitted.
        project_description: One-sentence project description.
        force: When True, overwrite an existing file.
        stack: Pre-built TechStack; when provided, skips detection entirely.

    Returns:
        The TechStack that was used (detected or supplied).

    Raises:
        FileExistsError: When *output* already exists and *force* is False.
    """
    if output.exists() and not force:
        raise FileExistsError(f"{output} already exists. Use --force to overwrite.")

    if stack is None:
        scan_path = project_path or Path.cwd()
        stack = detect_tech_stack(scan_path)
    tech_section = _build_tech_stack_section(stack)

    description = project_description or f"{project_name} project."
    template = _load_template("AGENTS.md.tpl")
    content = template.safe_substitute(
        project_name=project_name,
        project_description=description,
        tech_stack_section=tech_section,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return stack
