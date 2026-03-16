# Dependency Security Audit (March 2026)

This document records a full dependency security audit performed in March 2026. It covers tak's direct and indirect dependencies, optional packages, and setup-related tools.

## Methodology

- CVE search: MITRE CVE database, NVD
- Package health: maintenance status, bus factor, recent activity
- Version pinning: minimum versions verified against latest stable releases

---

## Core Dependencies

### iterm2 (>=2.7)

**Status**: Clean. No known CVEs in the Python package.

**Note**: The iTerm2 *application* has had CVEs. See [iterm2-security.md](iterm2-security.md) for details. Recommendation: document minimum iTerm2 app version (3.5.11 or later) for users.

### PyYAML (>=6.0)

**Status**: Historic CVEs in versions &lt;5.4 related to unsafe loaders (`yaml.load()` without `Loader=`).

**Action**: Audit codebase to ensure only `yaml.safe_load()` (or equivalent safe APIs) is used. Never use `yaml.load()` without an explicit safe Loader.

### Click (>=8.1)

**Status**: Zero CVEs. Health 91/100. Maintained by Pallets team. Stable and widely used.

### Rich (>=13.0)

**Status**: Zero CVEs. Maintained by Textualize. Active development.

---

## Optional Dependencies

### httpx (>=0.27)

**Status**: CVE-2025-43859 (CVSS 9.1) in the `h11` dependency. Fixed in `h11>=0.16`.

**Action**: Pin `h11>=0.16` (or ensure httpx pulls a version that depends on h11>=0.16). Verify transitive dependency resolution.

---

## Setup / External Tools

### Starship (latest via brew)

**Status**: CVE-2024-41815 fixed in 1.20.0. Current release 1.24.2. Clean.

### font-jetbrains-mono-nerd-font (brew cask v3.4.0)

**Status**: Legitimate package. ~73k installs/year. Historical HTTPS certificate issue has been fixed.

### pytest, pytest-asyncio, ruff, mypy

**Status**: No known CVEs. Standard tooling with active maintenance.

---

## Summary Table

| Package | CVEs | Action |
|---------|------|--------|
| iterm2 | None (pkg) | Document min iTerm2 app version |
| PyYAML | Historic (&lt;5.4) | Audit for safe_load only |
| Click | None | — |
| Rich | None | — |
| httpx | h11 CVE | Pin h11>=0.16 |
| Starship | Fixed in 1.20.0 | — |
| font-jetbrains-mono-nerd-font | None | — |
| pytest, pytest-asyncio, ruff, mypy | None | — |

---

## Ongoing Practices

Per AGENTS.md:

- Check MITRE CVE and NVD before adopting new packages
- Avoid packages with unpatched critical or high CVEs
- Prefer packages with recent commits, responsive maintainers, bus factor &gt; 1
- Use latest stable versions; specify minimum versions explicitly
