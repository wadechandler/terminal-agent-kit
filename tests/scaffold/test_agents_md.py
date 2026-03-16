"""Tests for tak.scaffold.agents_md."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tak.scaffold.agents_md import _build_tech_stack_section, generate_agents_md
from tak.scaffold.detect import TechStack

if TYPE_CHECKING:
    from pathlib import Path


class TestBuildTechStackSection:
    def test_language_only(self) -> None:
        section = _build_tech_stack_section(TechStack(language="Python"))
        assert "- **Language**: Python" in section

    def test_with_framework(self) -> None:
        section = _build_tech_stack_section(
            TechStack(language="Python", framework="FastAPI")
        )
        assert "- **Framework**: FastAPI" in section

    def test_with_build_system(self) -> None:
        section = _build_tech_stack_section(
            TechStack(language="Python", build_system="hatchling")
        )
        assert "- **Build System**: hatchling" in section

    def test_with_test_framework(self) -> None:
        section = _build_tech_stack_section(
            TechStack(language="Python", test_framework="pytest")
        )
        assert "- **Testing**: pytest" in section

    def test_with_extra_languages(self) -> None:
        section = _build_tech_stack_section(
            TechStack(language="Python", extra_languages=["TypeScript"])
        )
        assert "- **Also**: TypeScript" in section

    def test_unknown_stack_minimal(self) -> None:
        section = _build_tech_stack_section(TechStack(language="unknown"))
        assert "- **Language**: unknown" in section
        assert "Framework" not in section


class TestGenerateAgentsMd:
    def test_creates_file(self, tmp_path: Path) -> None:
        output = tmp_path / "AGENTS.md"
        generate_agents_md(project_name="myapp", output=output)
        assert output.exists()

    def test_project_name_in_output(self, tmp_path: Path) -> None:
        output = tmp_path / "AGENTS.md"
        generate_agents_md(project_name="SuperProject", output=output)
        content = output.read_text(encoding="utf-8")
        assert "SuperProject" in content

    def test_description_in_output(self, tmp_path: Path) -> None:
        output = tmp_path / "AGENTS.md"
        generate_agents_md(
            project_name="myapp",
            output=output,
            project_description="A very cool project.",
        )
        content = output.read_text(encoding="utf-8")
        assert "A very cool project." in content

    def test_default_description_uses_name(self, tmp_path: Path) -> None:
        output = tmp_path / "AGENTS.md"
        generate_agents_md(project_name="myapp", output=output)
        content = output.read_text(encoding="utf-8")
        assert "myapp" in content

    def test_python_stack_detected(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname='x'\n", encoding="utf-8"
        )
        output = tmp_path / "AGENTS.md"
        generate_agents_md(project_name="x", output=output, project_path=tmp_path)
        content = output.read_text(encoding="utf-8")
        assert "Python" in content

    def test_rust_stack_detected(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text(
            "[package]\nname='mypkg'\n", encoding="utf-8"
        )
        output = tmp_path / "AGENTS.md"
        generate_agents_md(project_name="mypkg", output=output, project_path=tmp_path)
        content = output.read_text(encoding="utf-8")
        assert "Rust" in content

    def test_returns_tech_stack(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\nname='x'\n", encoding="utf-8"
        )
        output = tmp_path / "AGENTS.md"
        stack = generate_agents_md(project_name="x", output=output, project_path=tmp_path)
        assert isinstance(stack, TechStack)
        assert stack.language == "Python"

    def test_file_exists_raises_without_force(self, tmp_path: Path) -> None:
        output = tmp_path / "AGENTS.md"
        output.write_text("existing content", encoding="utf-8")
        with pytest.raises(FileExistsError):
            generate_agents_md(project_name="x", output=output)
        assert output.read_text(encoding="utf-8") == "existing content"

    def test_force_overwrites_existing(self, tmp_path: Path) -> None:
        output = tmp_path / "AGENTS.md"
        output.write_text("old content", encoding="utf-8")
        generate_agents_md(project_name="newapp", output=output, force=True)
        content = output.read_text(encoding="utf-8")
        assert "newapp" in content
        assert "old content" not in content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        output = tmp_path / "subdir" / "deep" / "AGENTS.md"
        generate_agents_md(project_name="x", output=output)
        assert output.exists()

    def test_output_is_valid_markdown(self, tmp_path: Path) -> None:
        output = tmp_path / "AGENTS.md"
        generate_agents_md(project_name="TestProj", output=output)
        content = output.read_text(encoding="utf-8")
        assert content.startswith("# AGENTS.md")
        assert "## " in content

    def test_stack_override_skips_detection(self, tmp_path: Path) -> None:
        output = tmp_path / "AGENTS.md"
        override = TechStack(language="Rust", build_system="cargo")
        generate_agents_md(project_name="myrust", output=output, stack=override)
        content = output.read_text(encoding="utf-8")
        assert "Rust" in content
        assert "cargo" in content

    def test_stack_override_ignores_project_path(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
        output = tmp_path / "AGENTS.md"
        override = TechStack(language="Go", build_system="go")
        stack = generate_agents_md(
            project_name="mygo", output=output, project_path=tmp_path, stack=override
        )
        assert stack.language == "Go"
        content = output.read_text(encoding="utf-8")
        assert "Go" in content
        assert "Python" not in content
