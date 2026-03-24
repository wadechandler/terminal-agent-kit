"""Tests for tak.scaffold.new_project."""

from __future__ import annotations

from collections.abc import Generator
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from tak.scaffold.detect import TechStack
from tak.scaffold.new_project import _write_gitignore, _write_readme, create_project

if TYPE_CHECKING:
    from pathlib import Path


class TestWriteReadme:
    def test_creates_file(self, tmp_path: Path) -> None:
        _write_readme(tmp_path, "MyApp", "A description.")
        assert (tmp_path / "README.md").exists()

    def test_contains_project_name(self, tmp_path: Path) -> None:
        _write_readme(tmp_path, "MyApp", "A description.")
        content = (tmp_path / "README.md").read_text(encoding="utf-8")
        assert "# MyApp" in content

    def test_contains_description(self, tmp_path: Path) -> None:
        _write_readme(tmp_path, "x", "The best project ever.")
        content = (tmp_path / "README.md").read_text(encoding="utf-8")
        assert "The best project ever." in content


class TestWriteGitignore:
    def test_creates_file(self, tmp_path: Path) -> None:
        _write_gitignore(tmp_path, TechStack(language="Python"))
        assert (tmp_path / ".gitignore").exists()

    def test_python_gitignore_has_pycache(self, tmp_path: Path) -> None:
        _write_gitignore(tmp_path, TechStack(language="Python"))
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert "__pycache__/" in content

    def test_js_gitignore_has_node_modules(self, tmp_path: Path) -> None:
        _write_gitignore(tmp_path, TechStack(language="JavaScript"))
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert "node_modules/" in content

    def test_rust_gitignore_has_target(self, tmp_path: Path) -> None:
        _write_gitignore(tmp_path, TechStack(language="Rust"))
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert "target/" in content

    def test_go_gitignore_has_bin(self, tmp_path: Path) -> None:
        _write_gitignore(tmp_path, TechStack(language="Go"))
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert "bin/" in content

    def test_all_gitignores_have_env(self, tmp_path: Path) -> None:
        _write_gitignore(tmp_path, TechStack(language="unknown"))
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert ".env" in content

    def test_all_gitignores_have_ds_store(self, tmp_path: Path) -> None:
        _write_gitignore(tmp_path, TechStack(language="unknown"))
        content = (tmp_path / ".gitignore").read_text(encoding="utf-8")
        assert ".DS_Store" in content


class TestCreateProject:
    @pytest.fixture
    def no_git(self) -> Generator[None, None, None]:
        with patch("tak.scaffold.new_project._git_init", return_value=False):
            yield

    def test_creates_project_directory(self, tmp_path: Path, no_git: object) -> None:
        create_project(name="myapp", parent_dir=tmp_path, git=False)
        assert (tmp_path / "myapp").is_dir()

    def test_creates_agents_md(self, tmp_path: Path, no_git: object) -> None:
        create_project(name="myapp", parent_dir=tmp_path, git=False)
        assert (tmp_path / "myapp" / "AGENTS.md").exists()

    def test_agents_md_has_project_name(self, tmp_path: Path, no_git: object) -> None:
        create_project(name="coolapp", parent_dir=tmp_path, git=False)
        content = (tmp_path / "coolapp" / "AGENTS.md").read_text(encoding="utf-8")
        assert "coolapp" in content

    def test_creates_readme(self, tmp_path: Path, no_git: object) -> None:
        create_project(name="myapp", parent_dir=tmp_path, git=False)
        assert (tmp_path / "myapp" / "README.md").exists()

    def test_creates_gitignore(self, tmp_path: Path, no_git: object) -> None:
        create_project(name="myapp", parent_dir=tmp_path, git=False)
        assert (tmp_path / "myapp" / ".gitignore").exists()

    def test_creates_cursor_rules(self, tmp_path: Path, no_git: object) -> None:
        create_project(name="myapp", parent_dir=tmp_path, git=False)
        assert (tmp_path / "myapp" / ".cursor" / "rules").is_dir()

    def test_files_created_in_summary(self, tmp_path: Path, no_git: object) -> None:
        result = create_project(name="myapp", parent_dir=tmp_path, git=False)
        files: list[str] = result["files_created"]  # type: ignore[assignment]
        assert "AGENTS.md" in files
        assert "README.md" in files
        assert ".gitignore" in files

    def test_summary_contains_project_dir(self, tmp_path: Path, no_git: object) -> None:
        result = create_project(name="myapp", parent_dir=tmp_path, git=False)
        assert result["project_dir"] == tmp_path / "myapp"

    def test_summary_contains_stack(self, tmp_path: Path, no_git: object) -> None:
        result = create_project(name="myapp", parent_dir=tmp_path, git=False)
        assert isinstance(result["stack"], TechStack)

    def test_language_override(self, tmp_path: Path, no_git: object) -> None:
        result = create_project(
            name="myapp", parent_dir=tmp_path, language="Rust", git=False
        )
        stack: TechStack = result["stack"]  # type: ignore[assignment]
        assert stack.language == "Rust"

    def test_framework_override(self, tmp_path: Path, no_git: object) -> None:
        result = create_project(
            name="myapp", parent_dir=tmp_path, language="Python", framework="FastAPI", git=False
        )
        stack: TechStack = result["stack"]  # type: ignore[assignment]
        assert stack.framework == "FastAPI"

    def test_include_skill_generates_skill_md(self, tmp_path: Path, no_git: object) -> None:
        create_project(name="myapp", parent_dir=tmp_path, include_skill=True, git=False)
        assert (tmp_path / "myapp" / "SKILL.md").exists()

    def test_no_skill_by_default(self, tmp_path: Path, no_git: object) -> None:
        create_project(name="myapp", parent_dir=tmp_path, git=False)
        assert not (tmp_path / "myapp" / "SKILL.md").exists()

    def test_directory_exists_raises(self, tmp_path: Path, no_git: object) -> None:
        (tmp_path / "myapp").mkdir()
        with pytest.raises(FileExistsError):
            create_project(name="myapp", parent_dir=tmp_path, git=False)

    def test_git_init_called_when_git_true(self, tmp_path: Path) -> None:
        with patch("tak.scaffold.new_project._git_init", return_value=True) as mock_git:
            result = create_project(name="myapp", parent_dir=tmp_path, git=True)
            mock_git.assert_called_once_with(tmp_path / "myapp")
        assert result["git_initialized"] is True

    def test_git_not_called_when_git_false(self, tmp_path: Path) -> None:
        with patch("tak.scaffold.new_project._git_init", return_value=False) as mock_git:
            result = create_project(name="myapp", parent_dir=tmp_path, git=False)
            mock_git.assert_not_called()
        assert result["git_initialized"] is False

    def test_description_in_agents_md(self, tmp_path: Path, no_git: object) -> None:
        create_project(
            name="myapp", parent_dir=tmp_path, description="A great project.", git=False
        )
        content = (tmp_path / "myapp" / "AGENTS.md").read_text(encoding="utf-8")
        assert "A great project." in content

    def test_description_in_readme(self, tmp_path: Path, no_git: object) -> None:
        create_project(
            name="myapp", parent_dir=tmp_path, description="Awesome project.", git=False
        )
        content = (tmp_path / "myapp" / "README.md").read_text(encoding="utf-8")
        assert "Awesome project." in content
