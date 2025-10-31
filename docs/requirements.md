# Runtime requirements

- **GitHub CLI**: 2.43 or newer  
  Required for the Rulesets REST API endpoints and extended `gh api` flags.
- **Python**: 3.10 or newer  
  Used to run the `gh-ruleset-ext` entrypoint script and supporting modules.
- **Authentication**: `gh auth status` must report an authenticated account with **admin** rights on the target repository.

Network access is required so that `gh api` can reach GitHub. The extension does **not** depend on any extra Python packages.

## Optional tooling

- `python3 -m py_compile $(find src -name "*.py")` — quick syntax check.
- `gh extension install .` — install locally for testing before publishing.

That’s it! No other dependencies or language runtimes are needed.
