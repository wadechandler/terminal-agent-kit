# Phase J: Scaffold & Project Creation

## Goal

Implement the `tak scaffold` commands that generate standards files
(AGENTS.md, .cursor/rules/, SKILL.md) and the `tak new project` command
for interactive or quick project creation.

## Context

The CLI already has stub commands at `src/tak/cli/main.py`:
- `tak scaffold agents` -- generate AGENTS.md
- `tak scaffold rules` -- generate .cursor/rules/
- `tak scaffold skills` -- generate SKILL.md

These print "[not yet implemented]" today. This phase fills them in with
template-driven generation, plus adds a new `tak new project` command.

The `src/tak/scaffold/` package was planned in the architecture but does
not exist yet. Templates will live alongside the scaffold code or in the
`config/` directory.

## Files to Read First

- `src/tak/cli/main.py` -- existing stub commands (lines 170-199)
- `AGENTS.md` -- this project's own AGENTS.md (good reference for template)
- `.cursor/rules/python-style.mdc` -- example rule file
- `config/default.yaml` -- existing config structure
- `AGENTS.md` -- project conventions

## What to Build

### 1. Create `src/tak/scaffold/__init__.py` (empty)

### 2. Create `src/tak/scaffold/templates/`

Template files using Python string.Template or Jinja2-lite (avoid heavy
Jinja2 dep -- Python's `string.Template` or simple f-string replacement
is fine for this scope):

- `templates/AGENTS.md.tpl` -- AGENTS.md skeleton with placeholders for
  project name, tech stack, conventions
- `templates/cursor-rule.mdc.tpl` -- .cursor/rules/ rule file template
- `templates/SKILL.md.tpl` -- SKILL.md skeleton

### 3. Create `src/tak/scaffold/agents_md.py` -- `tak scaffold agents`

Generate an AGENTS.md file:

1. Prompt for project name (or accept --name flag)
2. Detect tech stack heuristics:
   - `pyproject.toml` or `setup.py` → Python
   - `package.json` → JavaScript/TypeScript
   - `Cargo.toml` → Rust
   - `go.mod` → Go
   - `pom.xml` or `build.gradle` → Java
3. Fill template with detected info
4. Write to `--output` path (default: `./AGENTS.md`)
5. If file exists: warn and require `--force` to overwrite
6. Print what was generated

### 4. Create `src/tak/scaffold/rules.py` -- `tak scaffold rules`

Generate .cursor/rules/ directory structure:

1. Create `.cursor/rules/` if not exists
2. Generate rule files based on detected tech stack:
   - Python: coding-style.mdc, testing.mdc
   - JavaScript/TypeScript: coding-style.mdc, testing.mdc
   - Generic: workspace-safety.mdc
3. Each rule file has proper frontmatter (description, globs, alwaysApply)
4. Skip files that already exist (idempotent)
5. Print what was created and what was skipped

### 5. Create `src/tak/scaffold/skills.py` -- `tak scaffold skills`

Generate a SKILL.md file:

1. Prompt for skill name and description (or accept --name/--desc flags)
2. Fill template with proper structure (Description, When to Use, Steps,
   Expected Output sections)
3. Write to `--output` path (default: `./SKILL.md`)
4. If file exists: warn and require `--force` to overwrite

### 6. Create `src/tak/scaffold/new_project.py` -- `tak new project`

Two modes:

**Quick mode** (`tak new project --quick myproject`):
- Create directory
- Generate AGENTS.md + .cursor/rules/ + README.md
- `git init`
- Print summary

**Interactive mode** (`tak new project myproject`):
- Prompt for project details (name, description, language, framework)
- Generate files based on responses
- Optionally scaffold additional files (SKILL.md, .gitignore, etc.)
- `git init`
- Print summary with next steps

### 7. Wire into CLI

Update `src/tak/cli/main.py`:
- Replace scaffold stubs with actual calls to scaffold modules
- Add `tak new` group with `project` subcommand
- Add `--force`, `--name`, `--output` options where appropriate

### 8. Tech stack detection utility

Create `src/tak/scaffold/detect.py`:
- `detect_tech_stack(path: Path) -> TechStack` -- scans for marker files
- Returns a dataclass with language, framework, build system, test framework
- Used by both scaffold and new project commands

## Tests to Write

- `tests/scaffold/test_agents_md.py`:
  - Test template rendering with various tech stacks
  - Test file write and --force behavior
  - Test tech stack detection

- `tests/scaffold/test_rules.py`:
  - Test rule file generation per language
  - Test idempotency (skip existing files)
  - Test frontmatter correctness

- `tests/scaffold/test_skills.py`:
  - Test template rendering
  - Test file write and --force behavior

- `tests/scaffold/test_new_project.py`:
  - Test quick mode creates expected files
  - Test directory creation
  - Use tmp_path for all file operations

- `tests/scaffold/test_detect.py`:
  - Test detection of Python, JS, Rust, Go, Java projects
  - Test unknown/empty project

## Acceptance Criteria

- `ruff check src/ tests/` passes with zero errors
- All tests pass
- `tak scaffold agents` generates a usable AGENTS.md
- `tak scaffold rules` generates .cursor/rules/ with correct frontmatter
- `tak scaffold skills` generates a usable SKILL.md
- `tak new project --quick` creates a working project skeleton
- All commands are idempotent (won't overwrite without --force)
- Template files exist in `src/tak/scaffold/templates/`

## Dependencies

- None on Phases F-I. Can run independently as Wave 3.
- Can run in parallel with Phase K (Multi-Agent & Resilience).

---

## Agent Prompt

```
Read AGENTS.md for project conventions, then read these files:
- src/tak/cli/main.py (especially the scaffold command stubs at lines 170-199)
- .cursor/rules/python-style.mdc (example rule file for template reference)
- config/default.yaml

Then read docs/tasks/phase-j-scaffold-project.md for the full task spec.

Implement everything: create the src/tak/scaffold/ package with templates,
tech stack detection, AGENTS.md generator, rules generator, SKILL.md
generator, new project command, and wire into the CLI. Write all tests
using tmp_path for file operations. Run ruff check and pytest after each
major piece. Do not stop until ruff check src/ tests/ shows zero errors
and all tests pass.
```
