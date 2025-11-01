from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .api import GitHubAPI, GitHubAPIError
from .prompts import (
    open_editor_with_json,
    prompt_choice,
    prompt_multi_value,
    prompt_string,
    prompt_yes_no,
)
from .utils import resolve_repository
from .validation import validate_ruleset_payload
from .i18n import translate as _, set_language, language_from_env, available_languages


ENFORCEMENT_CHOICES = ["disabled", "evaluate", "active"]
TARGET_CHOICES = ["branch", "tag", "push"]

DEFAULT_BRANCH_TOKEN = "~DEFAULT_BRANCH"
DEFAULT_BRANCH_REF = f"refs/heads/{DEFAULT_BRANCH_TOKEN}"
GENERIC_RULE_EDITOR_HEADER = (
    "Edit the rule JSON."
    "\n- The 'type' key must match a supported rule type (e.g. required_status_checks)."
    "\n- The 'parameters' key contains options specific to that type."
    "\n- Lines starting with # or // are ignored when saving."
)


def main(argv: Optional[List[str]] = None) -> None:
    set_language(language_from_env())
    parser = build_parser()
    args = parser.parse_args(argv)

    set_language(getattr(args, "lang", None) or language_from_env())

    if not hasattr(args, "handler"):
        parser.print_help()
        return

    try:
        repo = resolve_repository(args.repo)
        api = GitHubAPI(repo)
        args.handler(api, args)
    except KeyboardInterrupt:
        print(_("error_keyboard_interrupt", "\nInterrupted by user (Ctrl+C)."), file=sys.stderr)
        sys.exit(130)
    except GitHubAPIError as exc:
        print(_("error_api", "Error: {message}", message=exc), file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(_("error_runtime", "Error: {message}", message=exc), file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gh ruleset-ext",
        description=_("cli_description", "Manage repository rulesets."),
    )
    parser.add_argument(
        "--repo",
        help=_(
            "arg_repo_help",
            "Target repository (OWNER/REPO or HOST/OWNER/REPO). Defaults to current gh repo.",
        ),
    )
    parser.add_argument(
        "--lang",
        choices=sorted(available_languages().keys()),
        help=_("arg_lang_help", "Interface language (default: English)."),
    )

    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser(
        "list",
        help=_("command_list_help", "List repository rulesets."),
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        help=_("option_json_output", "Return raw JSON."),
    )
    list_parser.set_defaults(handler=handle_list)

    view_parser = subparsers.add_parser(
        "view",
        help=_("command_view_help", "View a specific ruleset."),
    )
    view_parser.add_argument(
        "ruleset_id",
        type=int,
        help=_("arg_ruleset_id", "Numeric ruleset identifier."),
    )
    view_parser.add_argument(
        "--json",
        action="store_true",
        help=_("option_json_output", "Return raw JSON."),
    )
    view_parser.set_defaults(handler=handle_view)

    delete_parser = subparsers.add_parser(
        "delete",
        help=_("command_delete_help", "Delete a ruleset."),
    )
    delete_parser.add_argument(
        "ruleset_id",
        type=int,
        help=_("arg_ruleset_id", "Numeric ruleset identifier."),
    )
    delete_parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=_("option_yes_help", "Auto-confirm (non-interactive)."),
    )
    delete_parser.set_defaults(handler=handle_delete)

    create_parser = subparsers.add_parser(
        "create",
        help=_("command_create_help", "Create a new ruleset."),
    )
    create_parser.add_argument(
        "--file",
        help=_(
            "option_file_help",
            "Pre-filled JSON file for creation. Otherwise an interactive wizard is used.",
        ),
    )
    create_parser.add_argument(
        "--from-existing",
        type=int,
        help=_(
            "option_from_existing_help",
            "Clone an existing ruleset before interactive changes.",
        ),
    )
    create_parser.add_argument(
        "--editor",
        action="store_true",
        help=_(
            "option_editor_help",
            "Open final JSON in editor before submission.",
        ),
    )
    create_parser.add_argument(
        "--skip-validate",
        action="store_true",
        help=_(
            "option_skip_validate_help",
            "Skip local payload validation against the OpenAPI schema.",
        ),
    )
    create_parser.set_defaults(handler=handle_create)

    update_parser = subparsers.add_parser(
        "update",
        help=_("command_update_help", "Update an existing ruleset."),
    )
    update_parser.add_argument(
        "ruleset_id",
        type=int,
        help=_("arg_ruleset_id", "Numeric ruleset identifier."),
    )
    update_parser.add_argument(
        "--file",
        help=_(
            "option_update_file_help",
            "JSON file to replace the ruleset. Otherwise use the interactive wizard.",
        ),
    )
    update_parser.add_argument(
        "--editor",
        action="store_true",
        help=_(
            "option_editor_help",
            "Open final JSON in editor before submission.",
        ),
    )
    update_parser.add_argument(
        "--skip-validate",
        action="store_true",
        help=_(
            "option_skip_validate_help",
            "Skip local payload validation against the OpenAPI schema.",
        ),
    )
    update_parser.set_defaults(handler=handle_update)

    rule_parser = subparsers.add_parser(
        "rule",
        help=_("command_rule_help", "Manage individual rules within a ruleset."),
    )
    rule_parser.add_argument(
        "--skip-validate",
        action="store_true",
        help=_(
            "option_rule_skip_validate_help",
            "Skip local validation when modifying the ruleset.",
        ),
    )
    rule_sub = rule_parser.add_subparsers(dest="rule_command")

    rule_list = rule_sub.add_parser(
        "list",
        help=_("command_rules_list_help", "List rules inside a ruleset."),
    )
    rule_list.add_argument("ruleset_id", type=int)
    rule_list.set_defaults(handler=handle_rule_list)

    rule_add = rule_sub.add_parser(
        "add",
        help=_("command_rules_add_help", "Add a rule to a ruleset."),
    )
    rule_add.add_argument("ruleset_id", type=int)
    rule_add.set_defaults(handler=handle_rule_add)

    rule_edit = rule_sub.add_parser(
        "edit",
        help=_("command_rules_edit_help", "Edit an existing rule."),
    )
    rule_edit.add_argument("ruleset_id", type=int)
    rule_edit.add_argument(
        "rule_index",
        type=int,
        help=_("arg_rule_index", "Rule index (1-based)."),
    )
    rule_edit.set_defaults(handler=handle_rule_edit)

    rule_delete = rule_sub.add_parser(
        "delete",
        help=_("command_rules_delete_help", "Delete a rule from a ruleset."),
    )
    rule_delete.add_argument("ruleset_id", type=int)
    rule_delete.add_argument(
        "rule_index",
        type=int,
        help=_("arg_rule_index", "Rule index (1-based)."),
    )
    rule_delete.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=_("option_rules_delete_confirm_help", "Auto-confirm (non-interactive)."),
    )
    rule_delete.set_defaults(handler=handle_rule_delete)

    contexts_parser = subparsers.add_parser(
        "checks",
        help=_("command_checks_help", "List recently observed checks."),
    )
    contexts_parser.add_argument(
        "--ref",
        help=_(
            "option_checks_ref_help",
            "Reference (branch or SHA) used to inspect checks. Defaults to the default branch.",
        ),
    )
    contexts_parser.add_argument(
        "--pr",
        type=int,
        action="append",
        help=_("option_checks_pr_help", "Pull request number to include (repeatable)."),
    )
    contexts_parser.add_argument(
        "--latest-pr",
        action="store_true",
        help=_(
            "option_checks_latest_pr_help",
            "Automatically include the most recent open PR.",
        ),
    )
    contexts_parser.add_argument(
        "--no-default",
        action="store_true",
        help=_(
            "option_checks_no_default_help",
            "Do not inspect the default branch commit.",
        ),
    )
    contexts_parser.set_defaults(handler=handle_checks_list)

    return parser


# ---------------------------------------------------------------------------
# Validation helpers


def ensure_payload_is_valid(payload: Dict[str, Any], *, skip: bool, action: str) -> bool:
    if skip:
        return True

    errors = validate_ruleset_payload(payload)
    if not errors:
        return True

    print(_("validation_errors_heading", "OpenAPI validation errors detected:"))
    for error in errors:
        print(f"- {error}")

    if prompt_yes_no(
        _("validation_continue", "Continue {action} anyway?", action=action),
        default=False,
    ):
        return True

    print(_("validation_cancelled", "{action} cancelled.", action=action.capitalize()))
    return False


# ---------------------------------------------------------------------------
# Basic commands


def handle_list(api: GitHubAPI, args: argparse.Namespace) -> None:
    rulesets = api.list_rulesets() or []
    if args.json:
        print(json.dumps(rulesets, indent=2))
        return

    if not rulesets:
        print(_("list_no_rulesets", "No rulesets in this repository."))
        return

    headers = [
        _("table_header_id", "ID"),
        _("table_header_name", "Name"),
        _("table_header_target", "Target"),
        _("table_header_enforcement", "Enforcement"),
        _("table_header_rules", "Rules"),
        _("table_header_updated", "Updated"),
    ]
    rows = []
    for item in rulesets:
        rows.append(
            [
                str(item.get("id", "")),
                item.get("name", ""),
                item.get("target", ""),
                item.get("enforcement", ""),
                str(len(item.get("rules", []) or [])),
                item.get("updated_at", "") or item.get("created_at", ""),
            ]
        )
    print_table(headers, rows)


def handle_view(api: GitHubAPI, args: argparse.Namespace) -> None:
    ruleset = api.get_ruleset(args.ruleset_id)
    if args.json:
        print(json.dumps(ruleset, indent=2))
        return

    print_ruleset_details(ruleset)


def handle_delete(api: GitHubAPI, args: argparse.Namespace) -> None:
    if not args.yes:
        confirm = prompt_yes_no(
            _(
                "prompt_confirm_delete",
                "Delete ruleset {ruleset_id}? This action cannot be undone.",
                ruleset_id=args.ruleset_id,
            ),
            default=False,
        )
        if not confirm:
            print(_("prompt_delete_cancelled", "Deletion cancelled."))
            return
    api.delete_ruleset(args.ruleset_id)
    print(
        _(
            "prompt_ruleset_deleted",
            "Ruleset {ruleset_id} deleted.",
            ruleset_id=args.ruleset_id,
        )
    )


def handle_create(api: GitHubAPI, args: argparse.Namespace) -> None:
    if args.file:
        payload = load_json_file(args.file)
    else:
        template: Optional[Dict[str, Any]] = None
        if args.from_existing:
            existing = api.get_ruleset(args.from_existing)
            template = prepare_ruleset_payload(existing)
        payload = interactive_ruleset_builder(api, template)

    if args.editor:
        payload = open_editor_with_json(payload)

    if not ensure_payload_is_valid(
        payload,
        skip=args.skip_validate,
        action=_("action_creation", "creation"),
    ):
        return

    created = api.create_ruleset(payload)
    print(
        _(
            "prompt_ruleset_created",
            "Ruleset created successfully (ID {ruleset_id}).",
            ruleset_id=created.get("id"),
        )
    )


def handle_update(api: GitHubAPI, args: argparse.Namespace) -> None:
    if args.file:
        payload = load_json_file(args.file)
    else:
        existing = api.get_ruleset(args.ruleset_id)
        payload = interactive_ruleset_builder(api, prepare_ruleset_payload(existing))

    if args.editor:
        payload = open_editor_with_json(payload)

    if not ensure_payload_is_valid(
        payload,
        skip=args.skip_validate,
        action=_("action_update", "update"),
    ):
        return

    updated = api.update_ruleset(args.ruleset_id, payload)
    print(
        _(
            "prompt_ruleset_updated",
            "Ruleset {ruleset_id} updated.",
            ruleset_id=updated.get("id"),
        )
    )


# ---------------------------------------------------------------------------
# Rule sub-commands


def handle_rule_list(api: GitHubAPI, args: argparse.Namespace) -> None:
    ruleset = api.get_ruleset(args.ruleset_id)
    rules = ruleset.get("rules") or []
    if not rules:
        print(_("rule_list_empty", "This ruleset does not contain any rules."))
        return
    for idx, rule in enumerate(rules, start=1):
        summary = summarize_rule(rule)
        print(_("rule_list_entry", "[{index}] {summary}", index=idx, summary=summary))


def handle_rule_add(api: GitHubAPI, args: argparse.Namespace) -> None:
    existing = api.get_ruleset(args.ruleset_id)
    payload = prepare_ruleset_payload(existing)
    payload["rules"] = manage_rules_interactively(
        api, payload.get("rules", []), action="add"
    )
    if not ensure_payload_is_valid(
        payload,
        skip=getattr(args, "skip_validate", False),
        action=_("action_rule_add", "adding the rule"),
    ):
        return
    updated = api.update_ruleset(args.ruleset_id, payload)
    print(
        _(
            "rule_added",
            "Rule added. The ruleset now contains {count} rules.",
            count=len(updated.get("rules", [])),
        )
    )


def handle_rule_edit(api: GitHubAPI, args: argparse.Namespace) -> None:
    existing = api.get_ruleset(args.ruleset_id)
    payload = prepare_ruleset_payload(existing)
    rules = payload.get("rules", [])
    index = args.rule_index - 1
    if index < 0 or index >= len(rules):
        raise RuntimeError(_("error_rule_index", "Invalid rule index."))
    rules[index] = edit_rule_interactively(api, rules[index])
    if not ensure_payload_is_valid(
        payload,
        skip=getattr(args, "skip_validate", False),
        action=_("action_rule_update", "updating the rule"),
    ):
        return
    updated = api.update_ruleset(args.ruleset_id, payload)
    print(
        _(
            "rule_updated",
            "Rule {index} updated. ({summary})",
            index=args.rule_index,
            summary=summary_for_rule(updated["rules"][index]),
        )
    )


def handle_rule_delete(api: GitHubAPI, args: argparse.Namespace) -> None:
    existing = api.get_ruleset(args.ruleset_id)
    payload = prepare_ruleset_payload(existing)
    rules = payload.get("rules", [])
    index = args.rule_index - 1
    if index < 0 or index >= len(rules):
        raise RuntimeError(_("error_rule_index", "Invalid rule index."))
    if not args.yes:
        summary = summarize_rule(rules[index])
        if not prompt_yes_no(
            _(
                "rule_delete_confirm",
                "Delete rule [{index}] {summary}?",
                index=args.rule_index,
                summary=summary,
            ),
            default=False,
        ):
            print(_("prompt_delete_cancelled", "Deletion cancelled."))
            return
    removed = rules.pop(index)
    if not ensure_payload_is_valid(
        payload,
        skip=getattr(args, "skip_validate", False),
        action=_("action_rule_delete", "deleting the rule"),
    ):
        return
    api.update_ruleset(args.ruleset_id, payload)
    print(
        _(
            "rule_deleted",
            "Rule removed: {summary}",
            summary=summarize_rule(removed),
        )
    )


# ---------------------------------------------------------------------------
# Checks helper


def collect_check_contexts(
    api: GitHubAPI,
    *,
    include_default: bool = True,
    refs: Optional[Sequence[str]] = None,
    prs: Optional[Sequence[int]] = None,
    include_latest_pr: bool = False,
) -> Tuple[List[Dict[str, Any]], List[str], List[str]]:
    contexts_map: Dict[Tuple[str, Optional[int]], Dict[str, Any]] = {}
    inspected_sources: List[str] = []
    seen_sources: set[str] = set()
    warnings: List[str] = []

    def record_contexts(ref_value: str, label: str) -> None:
        try:
            contexts = api.list_check_contexts(ref_value)
        except GitHubAPIError as exc:
            warnings.append(f"{label}: {exc}")
            if exc.stderr:
                warnings.append(exc.stderr.strip())
            return
        if not contexts:
            return
        if label not in seen_sources:
            inspected_sources.append(label)
            seen_sources.add(label)
        for ctx in contexts:
            key = (ctx["context"], ctx.get("integration_id"))
            data = contexts_map.setdefault(
                key,
                {
                    "context": ctx["context"],
                    "integration_id": ctx.get("integration_id"),
                    "app_slug": ctx.get("app_slug"),
                    "app_name": ctx.get("app_name"),
                    "kinds": set(),
                    "sources": set(),
                },
            )
            if ctx.get("app_slug") and not data.get("app_slug"):
                data["app_slug"] = ctx["app_slug"]
            if ctx.get("app_name") and not data.get("app_name"):
                data["app_name"] = ctx["app_name"]
            if ctx.get("type"):
                data["kinds"].add(ctx["type"])
            data["sources"].add(label)

    if include_default:
        try:
            branch = api.get_default_branch()
            sha = api.get_latest_commit_sha(branch)
            record_contexts(sha, f"default:{branch}")
        except GitHubAPIError as exc:
            warnings.append(
                _(
                    "warning_default_branch",
                    "Default branch: {error}",
                    error=exc,
                )
            )
            if exc.stderr:
                warnings.append(exc.stderr.strip())

    if refs:
        for ref in refs:
            if ref:
                record_contexts(ref, ref)

    if prs:
        for number in prs:
            try:
                sha, ref_name = api.get_pull_request_head_sha(number)
            except GitHubAPIError as exc:
                warnings.append(
                    _(
                        "warning_pr_specific",
                        "PR #{number}: {error}",
                        number=number,
                        error=exc,
                    )
                )
                if exc.stderr:
                    warnings.append(exc.stderr.strip())
                continue
            label = f"pr#{number}"
            if ref_name:
                label += f" ({ref_name})"
            record_contexts(sha, label)

    if include_latest_pr:
        latest = None
        try:
            latest = api.get_latest_open_pull_request()
        except GitHubAPIError as exc:
            warnings.append(
                _(
                    "warning_latest_open_pr",
                    "Latest open PR: {error}",
                    error=exc,
                )
            )
            if exc.stderr:
                warnings.append(exc.stderr.strip())
        if not latest:
            try:
                latest = api.get_latest_merged_pull_request()
            except GitHubAPIError as exc:
                warnings.append(
                    _(
                        "warning_latest_merged_pr",
                        "Latest merged PR: {error}",
                        error=exc,
                    )
                )
                if exc.stderr:
                    warnings.append(exc.stderr.strip())
                latest = None
        if latest:
            sha = latest.get("head", {}).get("sha")
            if sha:
                number = latest.get("number")
                ref_name = latest.get("head", {}).get("ref")
                label = f"pr#{number}"
                if ref_name:
                    label += f" ({ref_name})"
                if latest.get("merged_at") and latest.get("state") != "open":
                    label += " [merged]"
                record_contexts(sha, label)
            else:
                warnings.append(
                    _(
                        "warning_latest_pr_no_sha",
                        "Latest PR: unable to determine head SHA.",
                    )
                )
        else:
            warnings.append(
                _(
                    "warning_no_recent_pr",
                    "No open or recently merged PR found.",
                )
            )

    context_entries: List[Dict[str, Any]] = []
    for data in contexts_map.values():
        data["kinds"] = sorted(data["kinds"])
        data["sources"] = sorted(data["sources"])
        context_entries.append(data)

    context_entries.sort(key=lambda item: (item["context"], item.get("integration_id") or -1))
    return context_entries, inspected_sources, warnings


def handle_checks_list(api: GitHubAPI, args: argparse.Namespace) -> None:
    refs = [args.ref] if args.ref else []
    context_entries, inspected_sources, warnings = collect_check_contexts(
        api,
        include_default=not args.no_default,
        refs=refs,
        prs=args.pr or [],
        include_latest_pr=args.latest_pr,
    )

    for warning in warnings:
        print(_("warning_prefix", "Warning: {message}", message=warning), file=sys.stderr)

    if not context_entries:
        print(_("checks_none_found", "No checks detected among the inspected references."))
        return

    print(_("checks_detected_heading", "Detected checks:"))
    for entry in context_entries:
        label = entry["context"]
        integration_id = entry.get("integration_id")
        app_parts: List[str] = []
        if entry.get("app_slug"):
            app_parts.append(entry["app_slug"])
        elif entry.get("app_name"):
            app_parts.append(entry["app_name"])
        if integration_id is not None:
            info = f"integration {integration_id}"
            if app_parts:
                info += f" ({', '.join(app_parts)})"
            label += f" [{info}]"
        elif app_parts:
            label += f" [app {', '.join(app_parts)}]"
        if entry.get("kinds"):
            label += f" <{', '.join(entry['kinds'])}>"
        origins = ", ".join(entry["sources"])
        print(_("checks_entry", "- {label}  [sources: {origins}]", label=label, origins=origins))

    if inspected_sources:
        print(_("checks_inspected_heading", "\nInspected references:"))
        for label in inspected_sources:
            print(_("checks_reference_entry", "- {label}", label=label))


# ---------------------------------------------------------------------------
# Interactive helpers


def interactive_ruleset_builder(
    api: GitHubAPI,
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = deepcopy(existing) if existing else {}

    data["name"] = prompt_string(
        _("prompt_ruleset_name", "Ruleset name"),
        default=data.get("name"),
    )
    data["target"] = prompt_choice(
        _("prompt_ruleset_target", "Ruleset target"),
        TARGET_CHOICES,
        default=data.get("target", "branch"),
    )
    data["enforcement"] = prompt_choice(
        _("prompt_ruleset_enforcement", "Enforcement mode"),
        ENFORCEMENT_CHOICES,
        default=data.get("enforcement", "active"),
    )

    conditions = data.get("conditions", {})
    ref_conditions = conditions.get("ref_name", {})
    include_values = list(ref_conditions.get("include", []))
    has_default_branch = any(is_default_branch_pattern(value) for value in include_values)
    include_defaults = [
        strip_ref_prefix(value)
        for value in include_values
        if not is_default_branch_pattern(value)
    ]
    exclude_defaults = [strip_ref_prefix(value) for value in ref_conditions.get("exclude", [])]

    include: List[str] = []
    include_default_branch = prompt_yes_no(
        _("prompt_apply_default_branch", "Apply the ruleset to the default branch?"),
        default=has_default_branch,
    )
    if include_default_branch:
        include.append(DEFAULT_BRANCH_TOKEN)

    prompt_for_include = bool(include_defaults)
    if not prompt_for_include:
        if include_default_branch:
            prompt_for_include = prompt_yes_no(
                _(
                    "prompt_additional_targets",
                    "Add other branches or patterns in addition to the default branch?",
                ),
                default=False,
            )
        else:
            prompt_for_include = True

    if prompt_for_include:
        extra_include = prompt_multi_value(
            _(
                "prompt_include_targets",
                "Targets {target} to include (leave blank for all)",
                target=data["target"],
            ),
            default=include_defaults,
            formatter=lambda value: format_ref_pattern(value, data["target"]),
        )
        include.extend(extra_include)

    exclude = prompt_multi_value(
        _(
            "prompt_exclude_targets",
            "Targets {target} to exclude",
            target=data["target"],
        ),
        default=exclude_defaults,
        formatter=lambda value: format_ref_pattern(value, data["target"]),
    )

    new_conditions = {}
    if include or exclude:
        new_conditions["ref_name"] = {"include": include, "exclude": exclude}
    data["conditions"] = new_conditions

    bypass = data.get("bypass_actors")
    if bypass and prompt_yes_no(
        _("prompt_modify_bypass", "Edit existing bypass actors?"),
        default=False,
    ):
        bypass = edit_bypass_actors(bypass)
    elif bypass is None:
        bypass = []
        if prompt_yes_no(
            _(
                "prompt_define_bypass",
                "Configure actors allowed to bypass the ruleset?",
            ),
            default=False,
        ):
            bypass = edit_bypass_actors([])
    data["bypass_actors"] = bypass

    rules = data.get("rules") or []
    rules = manage_rules_interactively(api, rules)
    data["rules"] = rules
    return prepare_ruleset_payload(data)


def manage_rules_interactively(
    api: GitHubAPI,
    current_rules: List[Dict[str, Any]],
    action: str | None = None,
) -> List[Dict[str, Any]]:
    rules = deepcopy(current_rules)
    while True:
        if action == "add":
            rules.append(add_rule_interactively(api))
            return rules

        print(_("manage_rules_current", "\nCurrent rules:"))
        if not rules:
            print(_("manage_rules_none", "- (none)"))
        else:
            for idx, rule in enumerate(rules, start=1):
                print(
                    _(
                        "manage_rules_entry",
                        "[{index}] {summary}",
                        index=idx,
                        summary=summarize_rule(rule),
                    )
                )

        print(_("manage_options_heading", "\nOptions:"))
        print(_("manage_option_add", "1. Add a rule"))
        if rules:
            print(_("manage_option_edit", "2. Edit a rule"))
            print(_("manage_option_delete", "3. Delete a rule"))
            print(_("manage_option_finish", "4. Finish"))
            choices = {"1", "2", "3", "4"}
        else:
            print(_("manage_option_finish_only", "2. Finish"))
            choices = {"1", "2"}

        choice = input(_("manage_choice_prompt", "Your choice:" ) + " ").strip()
        if choice not in choices:
            print(_("manage_invalid_choice", "Invalid choice."))
            continue

        if choice == "1":
            rules.append(add_rule_interactively(api))
        elif choice == "2":
            if not rules:
                return rules
            idx = select_rule_index(
                rules,
                _("manage_select_action_edit", "edit"),
            )
            rules[idx] = edit_rule_interactively(api, rules[idx])
        elif choice == "3":
            idx = select_rule_index(
                rules,
                _("manage_select_action_delete", "delete"),
            )
            removed = rules.pop(idx)
            print(
                _(
                    "rule_deleted",
                    "Rule removed: {summary}",
                    summary=summarize_rule(removed),
                )
            )
        else:
            return rules


def add_rule_interactively(api: GitHubAPI) -> Dict[str, Any]:
    print(_("add_rule_type_heading", "\nType of rule to add:"))
    print(_("add_rule_option_required_checks", "1. Required status checks"))
    print(_("add_rule_option_json_editor", "2. Free-form JSON editor"))
    choice = input(_("add_rule_choice_prompt", "Your choice [1]: ")).strip() or "1"
    if choice == "1":
        return build_required_status_rule(api)
    payload = open_editor_with_json(
        {"type": "", "parameters": {}},
        header=_("prompt_json_editor_header", GENERIC_RULE_EDITOR_HEADER),
        allow_comments=True,
    )
    validate_rule_payload(payload)
    return payload


def edit_rule_interactively(api: GitHubAPI, rule: Dict[str, Any]) -> Dict[str, Any]:
    if rule.get("type") == "required_status_checks":
        print(
            _(
                "edit_required_checks_heading",
                "Editing a required status checks rule.",
            )
        )
        return build_required_status_rule(api, existing=rule)

    print(_("edit_rule_via_editor", "Editing via JSON editor."))
    payload = open_editor_with_json(
        rule,
        header=_("prompt_json_editor_header", GENERIC_RULE_EDITOR_HEADER),
        allow_comments=True,
    )
    validate_rule_payload(payload)
    return payload


def build_required_status_rule(
    api: GitHubAPI,
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    params = existing.get("parameters", {}) if existing else {}
    contexts = params.get("required_status_checks", [])
    print(_("required_checks_heading", "\nConfigure required checks."))
    available_entries: List[Dict[str, Any]] = []
    if prompt_yes_no(_("required_checks_prompt_recent", "List recently observed checks?"), default=True):
        include_default = prompt_yes_no(
            _("required_checks_include_default", "Include the default branch?"),
            default=True,
        )
        include_latest_pr = prompt_yes_no(
            _(
                "required_checks_include_latest_pr",
                "Include the most recent open or merged PR?",
            ),
            default=True,
        )
        pr_numbers: List[int] = []
        pr_input = input(
            _(
                "required_checks_extra_prs",
                "Additional PR numbers (space-separated): ",
            )
        ).strip()
        if pr_input:
            for token in pr_input.split():
                if token.isdigit():
                    pr_numbers.append(int(token))
                else:
                    print(
                        _(
                            "required_checks_invalid_pr",
                            "Ignored PR number (non-numeric): {token}",
                            token=token,
                        )
                    )
        ref_input = input(
            _(
                "required_checks_extra_refs",
                "Additional references (branches or SHAs, space-separated): ",
            )
        ).strip()
        extra_refs = [value.strip() for value in ref_input.split() if value.strip()] if ref_input else []

        available_entries, inspected_sources, warnings = collect_check_contexts(
            api,
            include_default=include_default,
            refs=extra_refs,
            prs=pr_numbers,
            include_latest_pr=include_latest_pr,
        )
        for warning in warnings:
            print(_("warning_prefix", "Warning: {message}", message=warning))
        if inspected_sources:
            print(_("checks_inspected_heading", "\nInspected references:"))
            for label in inspected_sources:
                print(_("checks_reference_entry", "- {label}", label=label))
        if not available_entries:
            print(_("required_checks_none", "No checks detected for the selected references."))

    contexts = prompt_status_checks(contexts, available_entries)
    cleaned_checks: List[Dict[str, Any]] = []
    for item in contexts:
        entry = {"context": item["context"]}
        if item.get("integration_id") is not None:
            entry["integration_id"] = item["integration_id"]
        cleaned_checks.append(entry)
    strict = prompt_yes_no(
        _(
            "required_checks_strict",
            "Require PRs to be tested with the latest commit (strict_required_status_checks_policy)?",
        ),
        default=params.get("strict_required_status_checks_policy", True),
    )
    do_not_enforce = prompt_yes_no(
        _(
            "required_checks_allow_create",
            "Allow ref creation even if checks fail (do_not_enforce_on_create)?",
        ),
        default=params.get("do_not_enforce_on_create", False),
    )
    return {
        "type": "required_status_checks",
        "parameters": {
            "required_status_checks": cleaned_checks,
            "strict_required_status_checks_policy": strict,
            "do_not_enforce_on_create": do_not_enforce,
        },
    }


def prompt_status_checks(
    existing_checks: List[Dict[str, Any]],
    available_entries: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    checks = [dict(item) for item in existing_checks]
    available_entries = list(available_entries or [])

    for check in checks:
        if check.get("integration_id") is not None:
            for entry in available_entries:
                if (
                    entry.get("integration_id") == check.get("integration_id")
                    and entry.get("context") == check.get("context")
                ):
                    integration_app = entry.get("app_slug") or entry.get("app_name")
                    if integration_app:
                        check.setdefault("integration_app", integration_app)
                    break

    def format_entry(entry: Dict[str, Any]) -> str:
        label = entry["context"]
        integration_id = entry.get("integration_id")
        app_parts: List[str] = []
        if entry.get("app_slug"):
            app_parts.append(entry["app_slug"])
        elif entry.get("app_name"):
            app_parts.append(entry["app_name"])
        if integration_id is not None:
            info = f"integration {integration_id}"
            if app_parts:
                info += f" ({', '.join(app_parts)})"
            label += f" [{info}]"
        elif app_parts:
            label += f" [app {', '.join(app_parts)}]"
        if entry.get("kinds"):
            label += f" <{', '.join(entry['kinds'])}>"
        sources = ", ".join(entry.get("sources", []))
        if sources:
            label += f"  [sources: {sources}]"
        return label

    available_labels = [format_entry(entry) for entry in available_entries]
    while True:
        print(_("status_checks_current_heading", "\nCurrently required checks:"))
        if not checks:
            print(_("status_checks_none", "- (none)"))
        else:
            for idx, item in enumerate(checks, start=1):
                integration = item.get("integration_id")
                extras = []
                label = f"{item['context']} (integration {integration})" if integration else item["context"]
                if item.get("integration_id") and item.get("integration_app"):
                    extras.append(item["integration_app"])
                if extras:
                    label += f" [{', '.join(extras)}]"
                print(f"[{idx}] {label}")

        if available_entries:
            print(_("status_checks_recent_heading", "\nRecently observed checks:"))
            for idx, label in enumerate(available_labels, start=1):
                print(f"{idx}. {label}")

        print(_("status_checks_options_heading", "\nOptions:"))
        print(_("status_checks_option_add", "1. Add a check"))
        if checks:
            print(_("status_checks_option_remove", "2. Remove a check"))
            print(_("status_checks_option_finish", "3. Finish"))
            valid = {"1", "2", "3"}
        else:
            print(_("status_checks_option_finish_only", "2. Finish"))
            valid = {"1", "2"}

        choice = input(_("status_checks_choice_prompt", "Your choice:" ) + " ").strip()
        if choice not in valid:
            print(_("manage_invalid_choice", "Invalid choice."))
            continue
        if choice == "1":
            context_input = input(
                _(
                    "status_checks_context_prompt",
                    "Check name (or number from the list above): ",
                )
            ).strip()
            integration_default: Optional[int] = None
            integration_app: Optional[str] = None
            if context_input.isdigit() and available_entries:
                idx = int(context_input)
                if 1 <= idx <= len(available_entries):
                    entry = available_entries[idx - 1]
                    context = entry["context"]
                    integration_default = entry.get("integration_id")
                    app_slug = entry.get("app_slug") or entry.get("app_name")
                    integration_app = app_slug
                else:
                    print(_("status_checks_invalid_index", "Invalid index."))
                    continue
            else:
                context = context_input
            if not context:
                print(_("status_checks_name_required", "Name is required."))
                continue
            prompt_suffix = (
                _(
                    "status_checks_integration_suffix",
                    " (leave blank to use {value})",
                    value=integration_default,
                )
                if integration_default is not None
                else ""
            )
            integration_raw = input(
                _(
                    "status_checks_integration_prompt",
                    "Integration ID{suffix}: ",
                    suffix=prompt_suffix,
                )
            ).strip()
            if integration_raw:
                if not integration_raw.isdigit():
                    print(_("status_checks_integration_numeric", "Integration ID must be numeric."))
                    continue
                integration_id = int(integration_raw)
            else:
                integration_id = integration_default
            checks.append(
                {
                    "context": context,
                    **({"integration_id": integration_id} if integration_id is not None else {}),
                    **({"integration_app": integration_app} if integration_app else {}),
                }
            )
        elif choice == "2" and checks:
            idx = select_rule_index(
                checks,
                _("status_checks_select_remove", "remove"),
            )
            removed = checks.pop(idx)
            print(
                _(
                    "status_checks_removed",
                    "Check removed: {context}",
                    context=removed["context"],
                )
            )
        else:
            return checks


def edit_bypass_actors(existing: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    actors = [dict(item) for item in existing]
    while True:
        print(_("bypass_heading", "\nActors allowed to bypass the ruleset:"))
        if not actors:
            print(_("manage_rules_none", "- (none)"))
        else:
            for idx, actor in enumerate(actors, start=1):
                label = actor_summary(actor)
                print(_("manage_rules_entry", "[{index}] {summary}", index=idx, summary=label))
        print(_("manage_options_heading", "\nOptions:"))
        print(_("bypass_option_add", "1. Add"))
        if actors:
            print(_("bypass_option_remove", "2. Remove"))
            print(_("bypass_option_finish", "3. Finish"))
            valid = {"1", "2", "3"}
        else:
            print(_("bypass_option_finish_only", "2. Finish"))
            valid = {"1", "2"}
        choice = input(_("manage_choice_prompt", "Your choice:") + " ").strip()
        if choice not in valid:
            print(_("manage_invalid_choice", "Invalid choice."))
            continue
        if choice == "1":
            actors.append(prompt_bypass_actor())
        elif choice == "2" and actors:
            idx = select_rule_index(
                actors,
                _("manage_select_action_delete", "delete"),
            )
            removed = actors.pop(idx)
            print(
                _(
                    "bypass_removed",
                    "Actor removed: {summary}",
                    summary=actor_summary(removed),
                )
            )
        else:
            return actors


def prompt_bypass_actor() -> Dict[str, Any]:
    print(_("bypass_actor_type_heading", "\nActor type:"))
    print(_("bypass_actor_option_repo", "1. RepositoryRole (e.g. admin, maintain)"))
    print(_("bypass_actor_option_team", "2. Team (ORG/slug)"))
    print(_("bypass_actor_option_integration", "3. Integration (numeric ID)"))
    print(_("bypass_actor_option_org_admin", "4. OrganizationAdmin"))
    print(_("bypass_actor_option_enterprise_admin", "5. EnterpriseAdmin"))
    choice = input(_("add_rule_choice_prompt", "Your choice [1]: ")).strip() or "1"
    bypass_mode = prompt_choice(
        _("bypass_mode_prompt", "Bypass mode"),
        ["always", "pull_request"],
        default="always",
    )
    if choice == "1":
        role = input(_("bypass_role_prompt", "Repository role name (e.g. maintain): ")).strip()
        if not role:
            raise RuntimeError(_("bypass_role_empty", "Role cannot be empty."))
        return {
            "actor_type": "RepositoryRole",
            "repository_role_name": role,
            "bypass_mode": bypass_mode,
        }
    if choice == "2":
        team = input(_("bypass_team_prompt", "Team (ORG/slug): ")).strip()
        if "/" not in team:
            raise RuntimeError(_("bypass_team_format", "Expected format: ORG/slug."))
        org, slug = team.split("/", 1)
        actor_id = resolve_team_id(org, slug)
        return {"actor_type": "Team", "actor_id": actor_id, "bypass_mode": bypass_mode}
    if choice == "3":
        integration = input(_("bypass_integration_prompt", "Integration ID: ")).strip()
        if not integration.isdigit():
            raise RuntimeError(_("status_checks_integration_numeric", "Integration ID must be numeric."))
        return {
            "actor_type": "Integration",
            "actor_id": int(integration),
            "bypass_mode": bypass_mode,
        }
    actor_type = "OrganizationAdmin" if choice == "4" else "EnterpriseAdmin"
    return {"actor_type": actor_type, "bypass_mode": bypass_mode}


def resolve_team_id(org: str, slug: str) -> int:
    command = [
        "gh",
        "api",
        f"/orgs/{org}/teams/{slug}",
        "--method",
        "GET",
        "-H",
        "Accept: application/vnd.github+json",
        "-H",
        "X-GitHub-Api-Version: 2022-11-28",
    ]
    completed = subprocess_run(command)
    data = json.loads(completed)
    team_id = data.get("id")
    if not isinstance(team_id, int):
        raise RuntimeError(_("bypass_team_lookup_failed", "Unable to retrieve team identifier."))
    return team_id


def subprocess_run(command: List[str]) -> str:
    import subprocess

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - interactive flow
        stderr = exc.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(
            _(
                "subprocess_error",
                "Command {command} failed: {stderr}",
                command=" ".join(command),
                stderr=stderr,
            )
        ) from exc
    return result.stdout.decode("utf-8")


def print_ruleset_details(ruleset: Dict[str, Any]) -> None:
    print(_("ruleset_details_id", "ID: {value}", value=ruleset.get("id")))
    print(_("ruleset_details_name", "Name: {value}", value=ruleset.get("name")))
    print(_("ruleset_details_target", "Target: {value}", value=ruleset.get("target")))
    print(
        _(
            "ruleset_details_enforcement",
            "Enforcement: {value}",
            value=ruleset.get("enforcement"),
        )
    )
    print(
        _(
            "ruleset_details_created",
            "Created: {value}",
            value=ruleset.get("created_at"),
        )
    )
    print(
        _(
            "ruleset_details_updated",
            "Updated: {value}",
            value=ruleset.get("updated_at"),
        )
    )

    conditions = ruleset.get("conditions") or {}
    if conditions:
        print(_("ruleset_details_conditions", "Conditions:"))
        for key, value in conditions.items():
            print(_("ruleset_details_condition_entry", "  - {key}: {value}", key=key, value=value))
    bypass = ruleset.get("bypass_actors") or []
    if bypass:
        print(_("ruleset_details_bypass", "Bypass actors:"))
        for actor in bypass:
            print(_("ruleset_details_bypass_entry", "  - {summary}", summary=actor_summary(actor)))

    rules = ruleset.get("rules") or []
    if rules:
        print(_("ruleset_details_rules", "Rules:"))
        for idx, rule in enumerate(rules, start=1):
            print(
                _(
                    "ruleset_details_rule_entry",
                    "  [{index}] {summary}",
                    index=idx,
                    summary=summarize_rule(rule),
                )
            )


def summarize_rule(rule: Dict[str, Any]) -> str:
    rule_type = rule.get("type", "?")
    if rule_type == "required_status_checks":
        contexts = []
        for item in rule.get("parameters", {}).get("required_status_checks", []):
            label = item.get("context", "?")
            integration_id = item.get("integration_id")
            if integration_id is not None:
                label += f" (integration {integration_id})"
            contexts.append(label)
        return f"required_status_checks ({', '.join(contexts)})"
    return json.dumps(
        {k: v for k, v in rule.items() if k not in {"conditions"}},
        ensure_ascii=False,
    )


def summary_for_rule(rule: Dict[str, Any]) -> str:
    return summarize_rule(rule)


def actor_summary(actor: Dict[str, Any]) -> str:
    actor_type = actor.get("actor_type")
    if actor_type == "RepositoryRole":
        return f"RepositoryRole:{actor.get('repository_role_name')} ({actor.get('bypass_mode')})"
    if actor_type == "Team":
        return f"Team:{actor.get('actor_id')} ({actor.get('bypass_mode')})"
    if actor_type == "Integration":
        return f"Integration:{actor.get('actor_id')} ({actor.get('bypass_mode')})"
    return f"{actor_type} ({actor.get('bypass_mode')})"


def select_rule_index(items: List[Any], action: str) -> int:
    response = input(
        _(
            "select_rule_prompt",
            "Index of the rule to {action}: ",
            action=action,
        )
    ).strip()
    if not response.isdigit():
        raise RuntimeError(_("select_rule_numeric", "Numeric index expected."))
    idx = int(response) - 1
    if not (0 <= idx < len(items)):
        raise RuntimeError(_("select_rule_out_of_range", "Index out of range."))
    return idx


def load_json_file(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def prepare_ruleset_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "name": data.get("name"),
        "target": data.get("target", "branch"),
        "enforcement": data.get("enforcement", "active"),
        "rules": data.get("rules", []),
    }
    if "conditions" in data:
        payload["conditions"] = data.get("conditions") or {}
    if "bypass_actors" in data:
        payload["bypass_actors"] = data.get("bypass_actors") or []
    return payload


def validate_rule_payload(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict) or "type" not in payload:
        raise RuntimeError(
            _(
                "error_rule_payload_type",
                "A rule must be a JSON object with the 'type' key.",
            )
        )


def strip_ref_prefix(value: str) -> str:
    for prefix in ("refs/heads/", "refs/tags/"):
        if value.startswith(prefix):
            return value[len(prefix) :]
    return value


def is_default_branch_pattern(value: str) -> bool:
    return value in {DEFAULT_BRANCH_TOKEN, DEFAULT_BRANCH_REF}


def format_ref_pattern(value: str, target: str) -> str:
    value = value.strip()
    if not value:
        return value
    if value.startswith("~"):
        return value
    if value.startswith("refs/"):
        return value
    if target == "tag":
        return f"refs/tags/{value}"
    return f"refs/heads/{value}"


def print_table(headers: List[str], rows: List[List[str]]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(str(cell)))

    def format_row(row: List[str]) -> str:
        return "  ".join(str(cell).ljust(widths[idx]) for idx, cell in enumerate(row))

    print(format_row(headers))
    print(format_row(["-" * width for width in widths]))
    for row in rows:
        print(format_row(row))


if __name__ == "__main__":  # pragma: no cover
    main()
