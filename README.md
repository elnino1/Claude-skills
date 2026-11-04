# Claude-skills

A collection of personal skills for [Claude Code](https://claude.com/claude-code).

A skill is a folder containing a `SKILL.md` file (`name` / `description` frontmatter + instructions)
and, when needed, supporting files (templates, scripts). Claude loads it automatically when a request
matches its description, or explicitly via `/<skill-name>`.

## Available skills

| Skill | Purpose |
|---|---|
| [`github-ci`](github-ci/) | Sets up the standard GitHub Actions CI for a Python, Rust or Swift (SwiftPM / Xcode) repository: a `Test` workflow (lint + tests on every push), `auto_pr` (opens / refreshes a PR to the default branch automatically) and `release` (semver tag + GitHub Release after green tests). See its [README](github-ci/README.md). |

## Installation

Clone the repository:

```sh
git clone https://github.com/elnino1/Claude-skills.git
```

Then, for each skill, either:

- **Personal skill** (available in every project): copy or symlink it into `~/.claude/skills/`

  ```sh
  ln -s "$PWD/Claude-skills/github-ci" ~/.claude/skills/github-ci
  ```

  With a symlink, a `git pull` is enough to update the skill.

- **Project skill** (shared with the team through the project's repository): copy the folder into
  `.claude/skills/` at the project root.

Then check in Claude Code that the skill shows up (for example by typing `/` in the prompt).

## Layout

```
Claude-skills/
├── README.md
└── <skill>/
    ├── SKILL.md      # frontmatter + instructions read by Claude
    ├── README.md     # human-facing documentation
    └── templates/    # supporting files used by the skill
```

## Adding a skill

1. Create a `<skill-name>/` folder with a `SKILL.md`:

   ```markdown
   ---
   name: skill-name
   description: What the skill does and when to use it (this text is what triggers loading it).
   ---

   # Instructions
   ...
   ```

2. Add a `README.md` for human documentation, plus any supporting files.
3. List the skill in the [Available skills](#available-skills) table.

## Conventions

- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `ci:`…).
- Documentation and `SKILL.md` files are written in English.
