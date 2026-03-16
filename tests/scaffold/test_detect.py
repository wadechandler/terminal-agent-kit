"""Tests for tak.scaffold.detect."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from tak.scaffold.detect import TechStack, detect_tech_stack


class TestTechStackDataclass:
    def test_defaults(self) -> None:
        stack = TechStack(language="Python")
        assert stack.framework is None
        assert stack.build_system is None
        assert stack.test_framework is None
        assert stack.extra_languages == []

    def test_fully_populated(self) -> None:
        stack = TechStack(
            language="Python",
            framework="FastAPI",
            build_system="hatchling",
            test_framework="pytest",
            extra_languages=["TypeScript"],
        )
        assert stack.language == "Python"
        assert stack.framework == "FastAPI"


class TestDetectUnknown:
    def test_empty_directory(self, tmp_path: Path) -> None:
        stack = detect_tech_stack(tmp_path)
        assert stack.language == "unknown"
        assert stack.framework is None
        assert stack.build_system is None

    def test_nonexistent_directory(self, tmp_path: Path) -> None:
        missing = tmp_path / "does_not_exist"
        stack = detect_tech_stack(missing)
        assert stack.language == "unknown"


class TestDetectPython:
    def test_via_pyproject_toml(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='foo'\n", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.language == "Python"

    def test_via_setup_py(self, tmp_path: Path) -> None:
        (tmp_path / "setup.py").write_text("from setuptools import setup\n", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.language == "Python"

    def test_hatchling_build_system(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[build-system]\nrequires=['hatchling']\n", encoding="utf-8"
        )
        stack = detect_tech_stack(tmp_path)
        assert stack.build_system == "hatchling"

    def test_poetry_build_system(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.poetry]\nname='foo'\n", encoding="utf-8"
        )
        stack = detect_tech_stack(tmp_path)
        assert stack.build_system == "poetry"

    def test_setuptools_build_system(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[build-system]\nrequires=['setuptools']\n", encoding="utf-8"
        )
        stack = detect_tech_stack(tmp_path)
        assert stack.build_system == "setuptools"

    def test_pytest_test_framework(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\ntestpaths=['tests']\n", encoding="utf-8"
        )
        stack = detect_tech_stack(tmp_path)
        assert stack.test_framework == "pytest"

    def test_pytest_ini_file(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='foo'\n", encoding="utf-8")
        (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.test_framework == "pytest"

    def test_fastapi_framework(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            "[project]\ndependencies=['fastapi']\n", encoding="utf-8"
        )
        stack = detect_tech_stack(tmp_path)
        assert stack.framework == "FastAPI"

    def test_django_via_requirements(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
        (tmp_path / "requirements.txt").write_text("django>=4.0\n", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.framework == "Django"

    def test_flask_via_requirements(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
        (tmp_path / "requirements.txt").write_text("flask>=3.0\n", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.framework == "Flask"

    def test_no_framework_when_empty_pyproject(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='minimal'\n", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.framework is None


class TestDetectJavaScript:
    def test_via_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"name":"app"}', encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.language == "JavaScript"

    def test_typescript_when_tsconfig(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"name":"app"}', encoding="utf-8")
        (tmp_path / "tsconfig.json").write_text('{}', encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.language == "TypeScript"

    def test_react_framework(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            '{"dependencies":{"react":"^18.0"}}', encoding="utf-8"
        )
        stack = detect_tech_stack(tmp_path)
        assert stack.framework == "React"

    def test_nextjs_framework(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            '{"dependencies":{"next":"^14.0"}}', encoding="utf-8"
        )
        stack = detect_tech_stack(tmp_path)
        assert stack.framework == "Next.js"

    def test_vue_framework(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            '{"dependencies":{"vue":"^3.0"}}', encoding="utf-8"
        )
        stack = detect_tech_stack(tmp_path)
        assert stack.framework == "Vue"

    def test_jest_test_framework(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            '{"devDependencies":{"jest":"^29.0"}}', encoding="utf-8"
        )
        stack = detect_tech_stack(tmp_path)
        assert stack.test_framework == "Jest"

    def test_vitest_test_framework(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text(
            '{"devDependencies":{"vitest":"^1.0"}}', encoding="utf-8"
        )
        stack = detect_tech_stack(tmp_path)
        assert stack.test_framework == "Vitest"

    def test_npm_build_system(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"name":"app"}', encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.build_system == "npm"

    def test_pnpm_build_system(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"name":"app"}', encoding="utf-8")
        (tmp_path / "pnpm-lock.yaml").write_text("", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.build_system == "pnpm"

    def test_yarn_build_system(self, tmp_path: Path) -> None:
        (tmp_path / "package.json").write_text('{"name":"app"}', encoding="utf-8")
        (tmp_path / "yarn.lock").write_text("", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.build_system == "yarn"


class TestDetectRust:
    def test_via_cargo_toml(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("[package]\nname='foo'\n", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.language == "Rust"
        assert stack.build_system == "cargo"

    def test_no_framework(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("[package]\nname='foo'\n", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.framework is None


class TestDetectGo:
    def test_via_go_mod(self, tmp_path: Path) -> None:
        (tmp_path / "go.mod").write_text("module example.com/myapp\ngo 1.21\n", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.language == "Go"
        assert stack.build_system == "go"


class TestDetectJava:
    def test_maven_via_pom_xml(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.language == "Java"
        assert stack.build_system == "Maven"

    def test_gradle_via_build_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle").write_text("plugins {}\n", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.language == "Java"
        assert stack.build_system == "Gradle"

    def test_gradle_via_build_gradle_kts(self, tmp_path: Path) -> None:
        (tmp_path / "build.gradle.kts").write_text("plugins {}\n", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.language == "Java"
        assert stack.build_system == "Gradle"

    def test_pom_takes_priority_over_gradle(self, tmp_path: Path) -> None:
        (tmp_path / "pom.xml").write_text("<project/>\n", encoding="utf-8")
        (tmp_path / "build.gradle").write_text("plugins {}\n", encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.build_system == "Maven"


class TestDetectPriority:
    def test_pyproject_beats_package_json(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
        (tmp_path / "package.json").write_text('{"name":"x"}', encoding="utf-8")
        stack = detect_tech_stack(tmp_path)
        assert stack.language == "Python"


@pytest.mark.parametrize(
    ("marker", "expected_lang"),
    [
        ("pyproject.toml", "Python"),
        ("Cargo.toml", "Rust"),
        ("go.mod", "Go"),
        ("pom.xml", "Java"),
    ],
)
def test_parametrized_detection(tmp_path: Path, marker: str, expected_lang: str) -> None:
    (tmp_path / marker).write_text("", encoding="utf-8")
    stack = detect_tech_stack(tmp_path)
    assert stack.language == expected_lang
