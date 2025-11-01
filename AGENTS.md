# Repository Guidelines

## Project Structure & Module Organization

- `gh-ruleset-ext` – entry script executed by GitHub CLI (`gh ruleset-ext …`).
- `src/ruleset_cli/` – Python package containing the CLI dispatcher (`cli.py`), API wrapper (`api.py`), prompts, and utilities.
- `docs/` – supporting documentation (requirements, etc.).
- Root files: `README.md`, `README.fr.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `LICENSE`.

## Build, Test, and Development Commands

- `gh extension install .` – install the extension locally for iterative development.
- `./gh-ruleset-ext --help` – confirm CLI wiring and available subcommands.
- `python3 -m py_compile $(find src -name "*.py")` – quick syntax validation.
- Use real repository contexts to exercise interactive flows (e.g., `gh ruleset-ext checks --repo owner/name`).

## Coding Style & Naming Conventions

- Python 3.10+, 4-space indentation, type hints where practical.
- Stick to lower_snake_case for variables/functions, CamelCase for classes.
- Keep modules ASCII unless upstream data demands otherwise.
- Limit comments to clarifying non-obvious logic; prefer self-explanatory code.

## Testing Guidelines

- No formal test harness yet; rely on manual verification against a test repo with admin rights.
- For new features, document manual checks performed in PR descriptions (e.g., `gh ruleset-ext create`, `gh ruleset-ext checks --pr 123`).
- When adding pytests or mocks in the future, place them under `tests/` (to be created).

## Commit & Pull Request Guidelines

- Follow conventional, descriptive commit messages (e.g., `feat: add --latest-pr fallback`, `docs: translate README`).
- Update `CHANGELOG.md` under the appropriate release section and note manual testing steps.
- PRs should include: purpose/motivation, summary of CLI commands exercised, and any screenshots/terminal captures if UX changes.
- Ensure documentation (README, French README, docs/) stays in sync when altering user workflows.

## Security & Configuration Tips

- All commands call `gh api`; contributors must avoid printing tokens in logs.
- Document required scopes or permissions if new endpoints are introduced.
- When adding new environment variables or config flags, describe defaults and overrides in README.
