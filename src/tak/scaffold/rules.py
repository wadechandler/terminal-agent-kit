"""Generator for .cursor/rules/ scaffold files."""

from __future__ import annotations

import string
from dataclasses import dataclass
from pathlib import Path

from tak.scaffold.detect import TechStack, detect_tech_stack

_TEMPLATE_DIR = Path(__file__).parent / "templates"


@dataclass
class RuleSpec:
    """Specification for a single .cursor/rules/ file.

    Attributes:
        filename: Output filename (e.g. ``"coding-style.mdc"``).
        description: Short description for the rule frontmatter.
        globs: Glob pattern for the ``globs`` frontmatter field.
        always_apply: Whether to set ``alwaysApply: true`` in frontmatter.
        title: Heading rendered inside the rule body.
        body: Markdown body content (may be multi-line).
    """

    filename: str
    description: str
    globs: str
    always_apply: bool
    title: str
    body: str


_PYTHON_RULES: list[RuleSpec] = [
    RuleSpec(
        filename="coding-style.mdc",
        description="Python coding style conventions",
        globs="**/*.py",
        always_apply=False,
        title="Python Coding Style",
        body=(
            "Follow the [Google Python Style Guide]"
            "(https://google.github.io/styleguide/pyguide.html).\n\n"
            "- Line length: 100 characters (project override of Google's 80-char default)\n"
            "- Type hints on all public functions and methods\n"
            "- Google-style docstrings on all public modules, classes, and functions\n"
            "- Run `ruff check` and `mypy` before considering code complete\n"
            "- No wildcard imports — explicit is better than implicit"
        ),
    ),
    RuleSpec(
        filename="testing.mdc",
        description="Testing conventions for pytest",
        globs="tests/**/*.py",
        always_apply=False,
        title="Testing Conventions",
        body=(
            "- Use pytest for all tests\n"
            "- Mirror source structure: `tests/core/test_foo.py` tests `src/pkg/core/foo.py`\n"
            "- Use `tmp_path` fixture for all temporary file operations\n"
            "- Async tests use `pytest-asyncio` with `asyncio_mode = 'auto'`\n"
            "- `S101` (assert) and `D` (docstring) rules are suppressed in test files"
        ),
    ),
]

_JAVASCRIPT_RULES: list[RuleSpec] = [
    RuleSpec(
        filename="coding-style.mdc",
        description="JavaScript/TypeScript coding style conventions",
        globs="**/*.{js,ts,jsx,tsx}",
        always_apply=False,
        title="JavaScript/TypeScript Coding Style",
        body=(
            "- Prefer TypeScript for type safety\n"
            "- JSDoc comments on all exported functions and classes\n"
            "- Prefer `const` over `let`; never use `var`\n"
            "- No default exports — use named exports\n"
            "- Run the linter (`eslint` or `biome`) before committing"
        ),
    ),
    RuleSpec(
        filename="testing.mdc",
        description="Testing conventions for Jest/Vitest",
        globs="**/*.{test,spec}.{js,ts,jsx,tsx}",
        always_apply=False,
        title="Testing Conventions",
        body=(
            "- Use Jest or Vitest for unit tests\n"
            "- Test files mirror source structure\n"
            "- Prefer unit tests; integration tests live in `tests/integration/`\n"
            "- Mock external HTTP calls — do not make real network requests in tests"
        ),
    ),
]

_GENERIC_RULES: list[RuleSpec] = [
    RuleSpec(
        filename="workspace-safety.mdc",
        description="Workspace safety constraints",
        globs="",
        always_apply=True,
        title="Workspace Safety",
        body=(
            "- Only create, modify, and delete files within the project directory\n"
            "- Never commit secrets, credentials, or API keys\n"
            "- Run the test suite before creating a pull request\n"
            "- Do not run destructive commands (rm -rf, git push --force)"
            " without explicit user request"
        ),
    ),
]


def _rules_for_stack(stack: TechStack) -> list[RuleSpec]:
    """Return the list of rule specs appropriate for *stack*.

    Args:
        stack: Detected tech stack.

    Returns:
        List of RuleSpec objects to generate.
    """
    rules: list[RuleSpec] = list(_GENERIC_RULES)
    if stack.language == "Python":
        rules = list(_PYTHON_RULES) + rules
    elif stack.language in ("JavaScript", "TypeScript"):
        rules = list(_JAVASCRIPT_RULES) + rules
    return rules


def _render_rule(spec: RuleSpec) -> str:
    """Render a single rule file's content from the cursor-rule template.

    Args:
        spec: The rule specification.

    Returns:
        Complete .mdc file content as a string.
    """
    template = string.Template(
        (_TEMPLATE_DIR / "cursor-rule.mdc.tpl").read_text(encoding="utf-8")
    )
    return template.safe_substitute(
        description=spec.description,
        globs=spec.globs,
        always_apply=str(spec.always_apply).lower(),
        title=spec.title,
        body=spec.body,
    )


def generate_rules(
    rules_dir: Path,
    project_path: Path | None = None,
    stack: TechStack | None = None,
) -> tuple[list[str], list[str]]:
    """Generate .cursor/rules/ files for the detected or supplied tech stack.

    Creates *rules_dir* if it does not exist.  Files that already exist are
    skipped (idempotent); files that are created are returned in *created*.

    Args:
        rules_dir: Directory to write rule files into (typically ``.cursor/rules/``).
        project_path: Project root for tech-stack detection; ignored when *stack*
            is provided.  Defaults to cwd when both are omitted.
        stack: Pre-detected tech stack; when provided, *project_path* is ignored.

    Returns:
        A two-tuple ``(created, skipped)`` where each element is a list of
        filenames that were written or skipped, respectively.
    """
    if stack is None:
        scan_path = project_path or Path.cwd()
        stack = detect_tech_stack(scan_path)

    rules_dir.mkdir(parents=True, exist_ok=True)

    created: list[str] = []
    skipped: list[str] = []

    for spec in _rules_for_stack(stack):
        dest = rules_dir / spec.filename
        if dest.exists():
            skipped.append(spec.filename)
            continue
        dest.write_text(_render_rule(spec), encoding="utf-8")
        created.append(spec.filename)

    return created, skipped
