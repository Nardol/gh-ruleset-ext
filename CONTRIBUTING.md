# Contributing to gh-ruleset-ext

Thanks for your interest in improving the `gh-ruleset-ext` extension!  
All contributions are welcome — from bug reports to pull requests.

## Getting started

1. **Fork and clone** the repository.
2. Ensure you have:
   - GitHub CLI `gh` 2.43 or newer
   - Python 3.10 or newer
3. Install the extension locally for testing:

   ```bash
   gh extension install .
   ```

   Alternatively, run it directly:

   ```bash
   ./gh-ruleset-ext --help
   ```

4. Make your changes. See below for guidelines.

## Development tips

- Keep the codebase compatible with Python 3.10+.
- Use `python3 -m py_compile $(find src -name "*.py")` as a quick syntax guard.
- Avoid adding heavy dependencies; the goal is to rely only on GitHub CLI.
- Re-run interactive commands (create/update/rule/ checks) to make sure prompts still make sense.
- If you touch the CLI UX, document the change in both `README.md` and `README.fr.md`.

## Submitting changes

1. Update the **Changelog** (`CHANGELOG.md`) with a brief note under the “Unreleased” section.
2. Ensure CI/sanity checks pass (`py_compile` and any future tests).
3. Commit with a clear message and open a pull request that describes:
   - Motivation / context
   - Testing performed (`gh ruleset-ext …`, etc.)

We review PRs manually and aim to respond quickly.

## Reporting issues

Please include:

- Reproduction steps (commands, flags, repository type)
- `gh --version` output
- Any relevant console output (redact tokens)

---

### Ethical note

This project leverages OpenAI Codex (GPT‑5) to generate code and documentation. Every contribution — human or AI-assisted — is reviewed by a maintainer before merging.
