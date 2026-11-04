# github-ci

Claude Code skill that sets up the standard GitHub Actions CI in a Python, Rust or Swift repository.

## What it installs

Three workflows in `.github/workflows/`:

| Workflow | Trigger | Purpose |
|---|---|---|
| `test.yml` (named `Test`) | every push, all branches | lint + tests, depending on the language |
| `auto_pr.yml` | push to a branch other than the default branch | opens a PR to the default branch, with title and description generated from the commits. On later pushes, only the commit list is refreshed (between the `<!-- auto-commits:start/end -->` markers); hand-written text is kept |
| `release.yml` | end of a successful `Test` run triggered by a push to the default branch | bumps the semver tag (`patch` by default, `feat:` → minor, `BREAKING CHANGE` → major) + GitHub Release with a changelog |

### Tests per language

| Template | Detected by | Steps |
|---|---|---|
| `test-python.yml` | `pyproject.toml`, `requirements*.txt`, `setup.py` | `ruff check .` + `pytest` (Python version and install method adapted to the project: requirements, `[dev]` extra or uv) |
| `test-rust.yml` | `Cargo.toml` | `cargo fmt --check`, `cargo clippy -D warnings`, `cargo test` (+ `--workspace` when needed), with caching |
| `test-swift-spm.yml` | `Package.swift` | `swift build` + `swift test` on `macos-latest` |
| `test-swift-xcode.yml` | `*.xcodeproj` / `*.xcworkspace` | `xcodebuild test` (shared scheme and destination to fill in) |
| `test-ios-xcodegen.yml` | `project.yml` (XcodeGen) with an iOS target | `xcodegen generate`, newest iPhone simulator picked at run time, `xcodebuild test` (or `build` without test target), unsigned; SwiftLint job with `templates/swiftlint.yml` and a baseline for existing violations |

## Usage

In a project, ask Claude to "add my GitHub workflows" or run `/github-ci`.
The skill detects the language and the default branch, adapts the templates, checks locally
that lint and tests pass, and does not commit without your approval.

## Required GitHub setting

Without this setting, `auto_pr.yml` fails:

**Settings → Actions → General → Workflow permissions → Allow GitHub Actions to create and approve pull requests**

or:

```sh
gh api -X PUT repos/OWNER/REPO/actions/permissions/workflow \
  -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true
```

## Good to know

- `test.yml` runs on `push`, not `pull_request`: PRs created with `GITHUB_TOKEN` do not
  trigger `pull_request` workflows. The push status still shows on the PR.
- The `Test` workflow name must not change: `release.yml` listens to it by name.
- By default, a release is just the tag and the changelog. Injecting the version into
  `Cargo.toml`, `pyproject.toml` or Xcode, and attaching artifacts, is optional.
- iOS XcodeGen template: no signing in CI, so it also fits apps signed with a free Apple ID (Personal Team). Distribution (TestFlight / App Store) needs a paid developer account and is not covered.
- Prefix commits with Conventional Commits types (`feat:`, `fix:`, `ci:`…): the bump type depends on them.

## Installation

Copy the `github-ci/` folder into `~/.claude/skills/` (personal skill, all projects), or into
a project's `.claude/skills/`.
