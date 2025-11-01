# gh-ruleset-ext

> GitHub CLI extension for managing repository Rulesets.  
> Looking for the French documentation? See [README.fr.md](README.fr.md).

## Overview

`gh-ruleset-ext` enhances `gh` with a `ruleset-ext` command group so repository administrators can manage Rulesets straight from the terminal. It wraps the official REST API and provides interactive flows to create, update, inspect, and delete rulesets — including fine-grained control over status checks and bypass actors. (GitHub CLI already ships a basic `gh ruleset`; this extension goes further with interactive prompts and check discovery.)

### Highlights

- Works against the current repo (`gh repo view`) or any `--repo owner/name` (GitHub.com or Enterprise hostname).
- Interactive builder for `required_status_checks` rules with automatic discovery of recent checks on:
  - the default branch,
  - the latest open PR (falls back to the latest merged PR),
  - additional PR numbers or refs you provide.
- Displays each check’s GitHub App (integration) when available so you can lock the rule to that integration ID.
- Manage bypass actors (repository roles, teams, integrations, organisation/enterprise admins) interactively.
- Fully JSON-friendly: feed a file (`--file`), open the payload in `$EDITOR` (`--editor`), or clone an existing ruleset before editing (`--from-existing`).
- Validates payloads locally against the GitHub REST OpenAPI schema before calling `gh api` (bypass with `--skip-validate` when necessary).

> ℹ️ Ruleset operations require **admin** permissions on the target repository. Make sure your `gh` session is authenticated with a token that has admin rights.

---

## Requirements

- GitHub CLI `gh` **2.43+** (needed for Ruleset endpoints and extended `gh api` flags).
- Python **3.10+** available on the machine.
- A valid authentication context (`gh auth status`) with admin access.

No third-party Python libraries are required; the extension shells out to `gh api`.

### Language support

The CLI prompts are **English by default**, matching the upstream GitHub CLI experience. You can switch to another language (currently French) either per command or globally:

```bash
# One-off invocation
gh ruleset-ext create --lang fr

# Persist for all commands in the current shell
export GH_RULESET_EXT_LANG=fr
```

If `--lang` is not provided, the extension checks `GH_RULESET_EXT_LANG`, then `LANG`, and finally falls back to English. Contributions with additional translations are welcome—see `src/ruleset_cli/i18n.py` for the existing keys.

---

## Installation

Once this repository is public:

```bash
gh extension install Nardol/gh-ruleset-ext
```

During local development/testing:

```bash
gh extension install .
# or run directly
./gh-ruleset-ext --help
```

Uninstall at any time with `gh extension remove gh-ruleset-ext`.

---

## Quick start

```bash
# List rulesets in the current repository
gh ruleset-ext list

# Show details about one ruleset (pretty output or JSON)
gh ruleset-ext view 42
gh ruleset-ext view 42 --json

# Create or update rulesets interactively
gh ruleset-ext create
gh ruleset-ext update 42

# Skip local validation (not recommended unless the schema lags behind)
gh ruleset-ext create --skip-validate --file fixtures/ruleset.json

# Manage individual rules inside a ruleset
gh ruleset-ext rule list 42
gh ruleset-ext rule add 42
gh ruleset-ext rule edit 42 1     # 1-based index
gh ruleset-ext rule delete 42 2

# Discover recently observed status checks
gh ruleset-ext checks --repo owner/repo
gh ruleset-ext checks --pr 123              # include PR #123
gh ruleset-ext checks --latest-pr           # latest open PR, or latest merged if none open
gh ruleset-ext checks --no-default --ref <sha-or-branch>
```

Every subcommand accepts `--repo HOST/OWNER/REPO` to target another repository or a GitHub Enterprise host.

---

## Interactive workflows

Running `gh ruleset-ext create` or `gh ruleset-ext update` without `--file` launches an assistant that covers:

1. **Basics** — name, target (`branch`, `tag`, `push`), enforcement (`disabled`, `evaluate`, `active`).
2. **Conditions** — include/exclude ref patterns (helper automatically prefixes `refs/heads/` or `refs/tags/`).
3. **Bypass actors** — repository roles, teams (looked up via `gh api`), integrations, organisation/enterprise admins.
4. **Rules** — add/edit/remove rules individually.
   - `required_status_checks` builder pulls recent contexts, shows integration IDs/apps where available, and prompts for `strict_required_status_checks_policy` / `do_not_enforce_on_create`.
   - A JSON editor fallback (`--editor`) lets you tweak the final payload before sending it.

You can bootstrap the process from an existing ruleset or a file:

```bash
gh ruleset-ext create --from-existing 42
gh ruleset-ext update 42 --file path/to/ruleset.json
```

---

## Status checks & integrations

- Check runs (e.g. GitHub Actions) expose an `integration_id` and App slug — the assistant auto-suggests them.
- Some checks, such as `pre-commit.ci - pr`, are published as plain statuses; they don’t have an `integration_id`, so the rule will match by context name only.
- `gh ruleset-ext checks` aggregates contexts across all requested refs and prints their provenance (`default:main`, `pr#123`, etc.).

Example output:

```
- lint [integration 15368 (github-actions)] <check_run>  [sources: pr#238 (renovate/qt6-ruff-0.x) [merged]]
- pre-commit.ci - pr <status>  [sources: pr#238 (renovate/qt6-ruff-0.x) [merged]]
```

When adding a required check interactively, you can select a numbered entry to auto-fill the integration ID (if any) or leave it blank.

---

## Bypass actors

The assistant supports the full set of bypass actors:

- `RepositoryRole` (e.g. `admin`, `maintain`, `triage`)
- `Team` (resolved via `gh api /orgs/{org}/teams/{slug}`)
- `Integration` (numeric ID)
- `OrganizationAdmin`, `EnterpriseAdmin`

Each actor also specifies a bypass mode (`always` or `pull_request`).

---

## Project resources

- License: [MIT](LICENSE)
- Changelog: [CHANGELOG.md](CHANGELOG.md)
- Contributing guide: [CONTRIBUTING.md](CONTRIBUTING.md)
- Requirements recap: [docs/requirements.md](docs/requirements.md)

Quick sanity check:

```bash
python3 -m py_compile $(find src -name "*.py")
```

---

## Roadmap / ideas

- Optional YAML import/export helpers for sharing rulesets.
- Client-side validation against the official OpenAPI schema.
- Guided builders for additional rule types (e.g. `pull_request`, `actor_allow_list`).
- Automated tests with mocked `gh api` responses.

Contributions and suggestions are very welcome — see `CONTRIBUTING.md`.

---

## Ethical note

This project is built with the help of OpenAI Codex (GPT‑5). Every change is reviewed by a human maintainer before it is committed or released.
