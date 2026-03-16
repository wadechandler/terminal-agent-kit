"""Tests for tak.scaffold.rules."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tak.scaffold.detect import TechStack
from tak.scaffold.rules import _render_rule, _rules_for_stack, generate_rules

if TYPE_CHECKING:
    from pathlib import Path


class TestRulesForStack:
    def test_python_includes_coding_style(self) -> None:
        rules = _rules_for_stack(TechStack(language="Python"))
        filenames = [r.filename for r in rules]
        assert "coding-style.mdc" in filenames

    def test_python_includes_testing(self) -> None:
        rules = _rules_for_stack(TechStack(language="Python"))
        filenames = [r.filename for r in rules]
        assert "testing.mdc" in filenames

    def test_python_includes_workspace_safety(self) -> None:
        rules = _rules_for_stack(TechStack(language="Python"))
        filenames = [r.filename for r in rules]
        assert "workspace-safety.mdc" in filenames

    def test_javascript_includes_coding_style(self) -> None:
        rules = _rules_for_stack(TechStack(language="JavaScript"))
        filenames = [r.filename for r in rules]
        assert "coding-style.mdc" in filenames

    def test_typescript_included_with_js_rules(self) -> None:
        rules = _rules_for_stack(TechStack(language="TypeScript"))
        filenames = [r.filename for r in rules]
        assert "coding-style.mdc" in filenames
        assert "testing.mdc" in filenames

    def test_unknown_gets_only_generic(self) -> None:
        rules = _rules_for_stack(TechStack(language="unknown"))
        filenames = [r.filename for r in rules]
        assert filenames == ["workspace-safety.mdc"]

    def test_rust_gets_only_generic(self) -> None:
        rules = _rules_for_stack(TechStack(language="Rust"))
        filenames = [r.filename for r in rules]
        assert filenames == ["workspace-safety.mdc"]


class TestRenderRule:
    def test_frontmatter_description(self) -> None:
        from tak.scaffold.rules import _PYTHON_RULES

        rule = _PYTHON_RULES[0]
        rendered = _render_rule(rule)
        assert f"description: {rule.description}" in rendered

    def test_frontmatter_always_apply_false(self) -> None:
        from tak.scaffold.rules import _PYTHON_RULES

        rule = _PYTHON_RULES[0]
        rendered = _render_rule(rule)
        assert "alwaysApply: false" in rendered

    def test_frontmatter_always_apply_true(self) -> None:
        from tak.scaffold.rules import _GENERIC_RULES

        workspace_rule = next(r for r in _GENERIC_RULES if r.filename == "workspace-safety.mdc")
        rendered = _render_rule(workspace_rule)
        assert "alwaysApply: true" in rendered

    def test_title_in_body(self) -> None:
        from tak.scaffold.rules import _PYTHON_RULES

        rule = _PYTHON_RULES[0]
        rendered = _render_rule(rule)
        assert f"# {rule.title}" in rendered

    def test_body_content_present(self) -> None:
        from tak.scaffold.rules import _PYTHON_RULES

        rule = _PYTHON_RULES[0]
        rendered = _render_rule(rule)
        assert rule.body[:30] in rendered

    def test_yaml_frontmatter_block(self) -> None:
        from tak.scaffold.rules import _PYTHON_RULES

        rendered = _render_rule(_PYTHON_RULES[0])
        assert rendered.startswith("---\n")
        assert "---\n\n" in rendered


class TestGenerateRules:
    def test_creates_rules_directory(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".cursor" / "rules"
        generate_rules(rules_dir=rules_dir, stack=TechStack(language="unknown"))
        assert rules_dir.is_dir()

    def test_python_creates_three_files(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".cursor" / "rules"
        created, skipped = generate_rules(
            rules_dir=rules_dir, stack=TechStack(language="Python")
        )
        assert len(created) == 3
        assert skipped == []

    def test_unknown_creates_one_file(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".cursor" / "rules"
        created, _ = generate_rules(rules_dir=rules_dir, stack=TechStack(language="unknown"))
        assert len(created) == 1
        assert (rules_dir / "workspace-safety.mdc").exists()

    def test_idempotent_skips_existing(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".cursor" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "workspace-safety.mdc").write_text("existing", encoding="utf-8")
        created, skipped = generate_rules(
            rules_dir=rules_dir, stack=TechStack(language="unknown")
        )
        assert created == []
        assert "workspace-safety.mdc" in skipped
        assert (rules_dir / "workspace-safety.mdc").read_text(encoding="utf-8") == "existing"

    def test_partial_existing_creates_missing(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".cursor" / "rules"
        rules_dir.mkdir(parents=True)
        (rules_dir / "coding-style.mdc").write_text("old", encoding="utf-8")
        created, skipped = generate_rules(
            rules_dir=rules_dir, stack=TechStack(language="Python")
        )
        assert "coding-style.mdc" in skipped
        assert "testing.mdc" in created
        assert "workspace-safety.mdc" in created

    def test_generated_file_has_frontmatter(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".cursor" / "rules"
        generate_rules(rules_dir=rules_dir, stack=TechStack(language="Python"))
        content = (rules_dir / "coding-style.mdc").read_text(encoding="utf-8")
        assert content.startswith("---\n")
        assert "description:" in content
        assert "alwaysApply:" in content

    def test_uses_cwd_when_no_stack_or_path(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        rules_dir = tmp_path / ".cursor" / "rules"
        created, _ = generate_rules(rules_dir=rules_dir, project_path=tmp_path)
        assert len(created) == 3

    def test_javascript_creates_three_files(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".cursor" / "rules"
        created, _ = generate_rules(
            rules_dir=rules_dir, stack=TechStack(language="JavaScript")
        )
        assert len(created) == 3

    def test_workspace_safety_has_always_apply_true(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".cursor" / "rules"
        generate_rules(rules_dir=rules_dir, stack=TechStack(language="unknown"))
        content = (rules_dir / "workspace-safety.mdc").read_text(encoding="utf-8")
        assert "alwaysApply: true" in content
