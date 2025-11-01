# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Bilingual CLI prompts with English default and `--lang`/`GH_RULESET_EXT_LANG` overrides (initial French translation included).
- Annotated JSON editor helper that accepts comment lines and surfaces guidance headers in the selected language.

### Changed
- README documentation now explains language selection and localisation contributions.

## [0.2.0] - 2025-11-01

- Added local OpenAPI-derived validation for ruleset payloads with a `--skip-validate` escape hatch.

## [0.1.0] - 2025-10-31

- Initial public release of `gh-ruleset-ext`:
  - GitHub CLI extension for managing repository rulesets.
  - Interactive builders for `required_status_checks` and bypass actors.
  - Aggregated status check discovery across default branch, PRs, and custom refs.
