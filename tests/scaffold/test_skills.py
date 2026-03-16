"""Tests for tak.scaffold.skills."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tak.scaffold.skills import generate_skill_md

if TYPE_CHECKING:
    from pathlib import Path


class TestGenerateSkillMd:
    def test_creates_file(self, tmp_path: Path) -> None:
        output = tmp_path / "SKILL.md"
        generate_skill_md(
            skill_name="My Skill",
            description="Does something useful.",
            output=output,
        )
        assert output.exists()

    def test_skill_name_in_output(self, tmp_path: Path) -> None:
        output = tmp_path / "SKILL.md"
        generate_skill_md(
            skill_name="Refactor Module",
            description="Refactors a Python module.",
            output=output,
        )
        content = output.read_text(encoding="utf-8")
        assert "Refactor Module" in content

    def test_description_in_output(self, tmp_path: Path) -> None:
        output = tmp_path / "SKILL.md"
        generate_skill_md(
            skill_name="X",
            description="A very specific description.",
            output=output,
        )
        content = output.read_text(encoding="utf-8")
        assert "A very specific description." in content

    def test_when_to_use_in_output(self, tmp_path: Path) -> None:
        output = tmp_path / "SKILL.md"
        generate_skill_md(
            skill_name="X",
            description="Desc.",
            output=output,
            when_to_use="reorganize the project structure",
        )
        content = output.read_text(encoding="utf-8")
        assert "reorganize the project structure" in content

    def test_expected_output_in_content(self, tmp_path: Path) -> None:
        output = tmp_path / "SKILL.md"
        generate_skill_md(
            skill_name="X",
            description="Desc.",
            output=output,
            expected_output="A clean directory with no unused files.",
        )
        content = output.read_text(encoding="utf-8")
        assert "A clean directory with no unused files." in content

    def test_default_when_to_use(self, tmp_path: Path) -> None:
        output = tmp_path / "SKILL.md"
        generate_skill_md(skill_name="X", description="Desc.", output=output)
        content = output.read_text(encoding="utf-8")
        assert "perform this task" in content

    def test_file_exists_raises_without_force(self, tmp_path: Path) -> None:
        output = tmp_path / "SKILL.md"
        output.write_text("original", encoding="utf-8")
        with pytest.raises(FileExistsError):
            generate_skill_md(skill_name="X", description="Desc.", output=output)
        assert output.read_text(encoding="utf-8") == "original"

    def test_force_overwrites_existing(self, tmp_path: Path) -> None:
        output = tmp_path / "SKILL.md"
        output.write_text("old content", encoding="utf-8")
        generate_skill_md(
            skill_name="New Skill",
            description="New description.",
            output=output,
            force=True,
        )
        content = output.read_text(encoding="utf-8")
        assert "New Skill" in content
        assert "old content" not in content

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        output = tmp_path / "skills" / "SKILL.md"
        generate_skill_md(skill_name="X", description="Desc.", output=output)
        assert output.exists()

    def test_output_has_when_to_use_section(self, tmp_path: Path) -> None:
        output = tmp_path / "SKILL.md"
        generate_skill_md(skill_name="X", description="Desc.", output=output)
        content = output.read_text(encoding="utf-8")
        assert "## When to Use" in content

    def test_output_has_steps_section(self, tmp_path: Path) -> None:
        output = tmp_path / "SKILL.md"
        generate_skill_md(skill_name="X", description="Desc.", output=output)
        content = output.read_text(encoding="utf-8")
        assert "## Steps" in content

    def test_output_has_expected_output_section(self, tmp_path: Path) -> None:
        output = tmp_path / "SKILL.md"
        generate_skill_md(skill_name="X", description="Desc.", output=output)
        content = output.read_text(encoding="utf-8")
        assert "## Expected Output" in content
