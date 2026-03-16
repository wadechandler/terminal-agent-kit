# iTerm2 Python API Security Model

This document describes the security model of the iTerm2 Python API, authentication mechanisms, and relevant CVE history. It informs tak's design for daemon scripts and external tool integration.

## API Enablement

The Python API is **disabled by default**. Users must explicitly enable it:

- **GUI**: Settings → General → Magic → Enable Python API
- **CLI**: `defaults write com.googlecode.iterm2 EnableAPIServer -bool true`

## Authentication

### Cookie-Based Auth

- **Mechanism**: 128-bit random `ITERM2_COOKIE` environment variable
- **Scripts launched by iTerm2**: Receive the cookie automatically; no user interaction required
- **External programs**: Must present the cookie. iTerm2 shows a modal dialog for approval:
  - One-time approval (session)
  - 30-day persistent approval

### Disabling Cookie Auth

A special admin-owned file can disable cookie authentication. **Not recommended** for normal use; only for locked-down environments.

## Transport

- **Unix domain socket** (since iTerm2 3.4): Local-only, no network exposure
- **Legacy**: Earlier versions may have used different mechanisms

## macOS Permissions

- **Automation permission**: Required for external programs that connect to iTerm2
- **Accessibility**: May be required for certain operations (e.g., window management)

## iTerm2 Application CVE History

| CVE | CVSS | Fixed Version | Notes |
|-----|------|---------------|-------|
| CVE-2025-22275 | 9.3 | 3.5.11 | — |
| CVE-2024-38395 | 9.8 | 3.5.2 | — |
| CVE-2024-38396 | 9.8 | 3.5.2 | — |
| CVE-2023-46321 | — | — | — |
| CVE-2022-45872 | — | — | — |

**Recommendation**: Document minimum iTerm2 version (e.g., 3.5.11) for tak users. See [dependency-security-audit.md](dependency-security-audit.md).

## Coexistence

- Multiple scripts can run independently
- **Namespaced variables and RPCs** avoid collisions between scripts
- tak daemon and other iTerm2 scripts (e.g., status bar components) can run concurrently

## Implications for tak

1. **Daemon scripts**: Launched by iTerm2 AutoLaunch → receive cookie automatically
2. **CLI invocations**: May run as external process → user may need to approve once or for 30 days
3. **Documentation**: Instruct users to enable API and approve tak if prompted
4. **Version check**: Consider validating iTerm2 version on startup
