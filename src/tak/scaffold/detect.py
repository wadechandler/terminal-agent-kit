"""Tech stack detection for scaffold commands."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


@dataclass
class TechStack:
    """Detected tech stack for a project directory.

    Attributes:
        language: Primary programming language (e.g. "Python", "Rust", "unknown").
        framework: Optional detected framework (e.g. "React", "Django").
        build_system: Optional build/package tool (e.g. "hatchling", "cargo").
        test_framework: Optional testing framework (e.g. "pytest", "Jest").
        extra_languages: Additional languages detected alongside the primary one.
    """

    language: str
    framework: str | None = None
    build_system: str | None = None
    test_framework: str | None = None
    extra_languages: list[str] = field(default_factory=list)


def _file_contains(path: Path, text: str) -> bool:
    """Return True if *path* exists and its text content contains *text*.

    Args:
        path: File path to check.
        text: Substring to search for.

    Returns:
        True when the file exists and the substring is found; False otherwise.
    """
    try:
        return text in path.read_text(encoding="utf-8")
    except OSError:
        return False


def _detect_python(path: Path) -> TechStack:
    """Build a TechStack for a Python project rooted at *path*.

    Args:
        path: Project root directory.

    Returns:
        A TechStack populated with Python-specific metadata.
    """
    build: str | None = None
    pyproject = path / "pyproject.toml"
    pyproject_text = pyproject.read_text(encoding="utf-8") if pyproject.exists() else ""

    if pyproject_text:
        if "hatchling" in pyproject_text:
            build = "hatchling"
        elif "poetry" in pyproject_text:
            build = "poetry"
        elif "setuptools" in pyproject_text:
            build = "setuptools"
        elif "flit" in pyproject_text:
            build = "flit"

    test: str | None = None
    if "pytest" in pyproject_text or (path / "pytest.ini").exists():
        test = "pytest"

    framework: str | None = None
    req = path / "requirements.txt"
    if "fastapi" in pyproject_text or (req.exists() and _file_contains(req, "fastapi")):
        framework = "FastAPI"
    elif "django" in pyproject_text or _file_contains(req, "django"):
        framework = "Django"
    elif "flask" in pyproject_text or _file_contains(req, "flask"):
        framework = "Flask"

    return TechStack(
        language="Python",
        framework=framework,
        build_system=build,
        test_framework=test,
    )


def _detect_javascript(path: Path) -> TechStack:
    """Build a TechStack for a JavaScript/TypeScript project rooted at *path*.

    Args:
        path: Project root directory.

    Returns:
        A TechStack populated with JS/TS-specific metadata.
    """
    lang = "TypeScript" if (path / "tsconfig.json").exists() else "JavaScript"

    framework: str | None = None
    pkg = path / "package.json"
    if pkg.exists():
        content = pkg.read_text(encoding="utf-8")
        if '"next"' in content:
            framework = "Next.js"
        elif '"react"' in content or '"react-dom"' in content:
            framework = "React"
        elif '"vue"' in content:
            framework = "Vue"
        elif '"svelte"' in content:
            framework = "Svelte"

        test: str | None = None
        if '"jest"' in content:
            test = "Jest"
        elif '"vitest"' in content:
            test = "Vitest"

        build: str | None = "npm"
        if (path / "pnpm-lock.yaml").exists():
            build = "pnpm"
        elif (path / "yarn.lock").exists():
            build = "yarn"
    else:
        test = None
        build = None

    return TechStack(
        language=lang,
        framework=framework,
        build_system=build,
        test_framework=test,
    )


def detect_tech_stack(path: Path) -> TechStack:
    """Detect the tech stack of a project by scanning well-known marker files.

    Marker files checked (in priority order):

    - ``pyproject.toml`` or ``setup.py`` → Python
    - ``package.json`` → JavaScript or TypeScript (when tsconfig.json present)
    - ``Cargo.toml`` → Rust
    - ``go.mod`` → Go
    - ``pom.xml`` → Java (Maven)
    - ``build.gradle`` / ``build.gradle.kts`` → Java (Gradle)

    Args:
        path: The project root directory to scan.

    Returns:
        A TechStack dataclass with detected language, framework, build system,
        and test framework.  ``language`` is ``"unknown"`` when no markers are found.
    """
    if (path / "pyproject.toml").exists() or (path / "setup.py").exists():
        return _detect_python(path)

    if (path / "package.json").exists():
        return _detect_javascript(path)

    if (path / "Cargo.toml").exists():
        return TechStack(language="Rust", build_system="cargo")

    if (path / "go.mod").exists():
        return TechStack(language="Go", build_system="go")

    if (path / "pom.xml").exists():
        return TechStack(language="Java", build_system="Maven")

    if (path / "build.gradle").exists() or (path / "build.gradle.kts").exists():
        return TechStack(language="Java", build_system="Gradle")

    return TechStack(language="unknown")
