---
name: github-ci
description: Set up (or update) the standard GitHub Actions CI for a repository — a Test workflow (lint + tests on every push), an Auto-PR workflow (opens/refreshes a PR to the default branch with a description built from the commits) and a Release workflow (semver tag + GitHub Release after green tests on the default branch). Supports Python, Rust and Swift (SwiftPM or Xcode). Use when the user asks to add CI, GitHub workflows, auto PR, automatic releases, or "my usual workflows" to a project.
---

# GitHub CI setup

Installs three workflows in `.github/workflows/` of the current repo, adapted to its language.
Templates live next to this file in `templates/` (read them; do not rewrite from memory).

| File | Role | Language-specific? |
|---|---|---|
| `test.yml` | lint + tests on every push, every branch | yes — pick a `test-*.yml` template |
| `auto_pr.yml` | on push to a non-default branch: open a PR (title/body from commits), or refresh the auto-generated commit list of the existing PR, keeping hand-written text | no |
| `release.yml` | after a successful `Test` run triggered by a push on the default branch: bump the semver tag (patch by default, `feat:` → minor, `BREAKING CHANGE` → major) and publish a GitHub Release with the changelog | no |

Why `test.yml` runs on `push` (all branches) and not `pull_request`: PRs created by `auto_pr.yml` use `GITHUB_TOKEN`, and GitHub does not trigger `pull_request` workflows for events caused by `GITHUB_TOKEN`. The push run's status attaches to the commit and shows on the PR. Keep it that way.

## Steps

1. **Inspect the repo** before writing anything:
   - default branch: `git symbolic-ref refs/remotes/origin/HEAD` (fallback: `gh repo view --json defaultBranchRef`, else `main`).
   - existing `.github/workflows/`: if workflows already exist, read them and show the user what will be replaced or merged; never overwrite silently.
   - language markers: `pyproject.toml` / `requirements*.txt` / `setup.py` → Python; `Cargo.toml` → Rust; `Package.swift` → Swift SwiftPM; `*.xcodeproj` / `*.xcworkspace` → Swift Xcode. Several languages → one job per language in `test.yml` (same workflow name `Test`), or ask.

2. **Write `test.yml`** from the matching template, adapting it to the project:
   - **Python** (`test-python.yml`):
     - Python version: from `requires-python`, ruff `target-version`, `.python-version`, or deployment docs. Don't guess 3.10 by default.
     - install: `pip install -r requirements.txt` if there's no `[project]` table in `pyproject.toml`; `pip install -e ".[dev]"` only if that extra really exists; if `uv.lock` exists, use `astral-sh/setup-uv` + `uv sync` + `uv run pytest`. Set `cache-dependency-path` to the real lock/requirements file.
     - keep the `ruff check .` step only if ruff is configured/installed; otherwise drop it (or use the project's linter, e.g. flake8).
     - test path: from `[tool.pytest.ini_options] testpaths`, else `tests/`.
   - **Rust** (`test-rust.yml`): drop `--all-features` if features are mutually exclusive; if the root `Cargo.toml` has a `[workspace]` table, add `--workspace` to the clippy and test commands. If the crate needs system libs, add an `apt-get install` step.
   - **Swift SwiftPM** (`test-swift-spm.yml`): runs on `macos-latest`. If the package is Linux-compatible (no Apple-only frameworks), `ubuntu-latest` is cheaper — mention it.
   - **Swift Xcode** (`test-swift-xcode.yml`): replace `__PROJECT_FLAG__`, `__SCHEME__` (from `xcodebuild -list` if on macOS, else from `*.xcodeproj/xcshareddata/xcschemes/*.xcscheme`; the scheme must be *shared*), `__DESTINATION__` (`platform=macOS` for Mac apps; for iOS pick a simulator name and tell the user it may need updating when the runner image changes). No placeholder may remain.
   - The workflow `name:` must stay exactly `Test` — `release.yml` listens to it by name.

3. **Copy `auto_pr.yml` and `release.yml`** unchanged, except: if the default branch is not `main`, replace every `main` (branch filters, `--base main`, `origin/main`, `git fetch origin main`).
   - Optional, only if the project needs it and the user agrees: inject the version into the manifest before the release (`Cargo.toml` `version`, `pyproject.toml` `version`, Xcode `MARKETING_VERSION`) and attach build artifacts (`files:` in the release step). By default release = tag + changelog only.

4. **Verify locally** what you can: YAML parses (`python3 -c "import yaml,sys; yaml.safe_load(open(sys.argv[1]))" file`, using a throwaway venv if PyYAML is missing), and run the same lint/test commands as the Test workflow (`ruff check . && pytest`, `cargo fmt --check && cargo clippy -- -D warnings && cargo test`, `swift test`). If they fail, tell the user — the first CI run would be red, and `release.yml` would never fire.

5. **Repository settings** — tell the user these are required (the auto-PR fails otherwise):
   - Settings → Actions → General → Workflow permissions → tick **Allow GitHub Actions to create and approve pull requests**.
   - Equivalent command (outward-facing change: ask before running it, and only if `gh` is authenticated):
     `gh api -X PUT repos/{owner}/{repo}/actions/permissions/workflow -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true`
     (the workflows declare their own `permissions:`, so `read` as default is fine.)

6. Don't commit or push unless asked. When committing, use a `ci:` conventional-commit message (the release action derives the bump from commit prefixes).

## Report

Tell the user which template was used and what was adapted (version, install command, scheme…), the local verification result, and the repository setting to enable.
