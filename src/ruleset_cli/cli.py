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


ENFORCEMENT_CHOICES = ["disabled", "evaluate", "active"]
TARGET_CHOICES = ["branch", "tag", "push"]


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "handler"):
        parser.print_help()
        return

    try:
        repo = resolve_repository(args.repo)
        api = GitHubAPI(repo)
        args.handler(api, args)
    except KeyboardInterrupt:
        print("\nInterruption par l'utilisateur (Ctrl+C).", file=sys.stderr)
        sys.exit(130)
    except GitHubAPIError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        if exc.stderr:
            print(exc.stderr, file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(f"Erreur : {exc}", file=sys.stderr)
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gh ruleset",
        description="Gérer les rulesets d'un dépôt GitHub.",
    )
    parser.add_argument(
        "--repo",
        help="Dépôt cible (OWNER/REPO ou HOST/OWNER/REPO). Par défaut utilise le dépôt courant.",
    )

    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="Lister les rulesets du dépôt.")
    list_parser.add_argument("--json", action="store_true", help="Sortie JSON brute.")
    list_parser.set_defaults(handler=handle_list)

    view_parser = subparsers.add_parser("view", help="Afficher un ruleset précis.")
    view_parser.add_argument("ruleset_id", type=int, help="Identifiant numérique du ruleset.")
    view_parser.add_argument("--json", action="store_true", help="Sortie JSON brute.")
    view_parser.set_defaults(handler=handle_view)

    delete_parser = subparsers.add_parser("delete", help="Supprimer un ruleset.")
    delete_parser.add_argument("ruleset_id", type=int, help="Identifiant numérique du ruleset.")
    delete_parser.add_argument(
        "-y", "--yes", action="store_true", help="Confirmation automatique (non interactif)."
    )
    delete_parser.set_defaults(handler=handle_delete)

    create_parser = subparsers.add_parser("create", help="Créer un nouveau ruleset.")
    create_parser.add_argument(
        "--file",
        help="Fichier JSON pré-rempli pour la création. Si omis, un assistant interactif est utilisé.",
    )
    create_parser.add_argument(
        "--from-existing",
        type=int,
        help="Cloner un ruleset existant avant modifications interactives.",
    )
    create_parser.add_argument(
        "--editor",
        action="store_true",
        help="Ouvrir l'objet JSON final dans l'éditeur par défaut avant envoi.",
    )
    create_parser.set_defaults(handler=handle_create)

    update_parser = subparsers.add_parser("update", help="Modifier un ruleset existant.")
    update_parser.add_argument("ruleset_id", type=int, help="Identifiant du ruleset.")
    update_parser.add_argument(
        "--file",
        help="Fichier JSON à utiliser pour remplacer le ruleset. Sinon assistant interactif.",
    )
    update_parser.add_argument(
        "--editor",
        action="store_true",
        help="Ouvrir l'objet JSON final dans l'éditeur par défaut avant envoi.",
    )
    update_parser.set_defaults(handler=handle_update)

    rule_parser = subparsers.add_parser("rule", help="Gérer les règles individuelles d'un ruleset.")
    rule_sub = rule_parser.add_subparsers(dest="rule_command")

    rule_list = rule_sub.add_parser("list", help="Lister les règles d'un ruleset.")
    rule_list.add_argument("ruleset_id", type=int)
    rule_list.set_defaults(handler=handle_rule_list)

    rule_add = rule_sub.add_parser("add", help="Ajouter une règle à un ruleset.")
    rule_add.add_argument("ruleset_id", type=int)
    rule_add.set_defaults(handler=handle_rule_add)

    rule_edit = rule_sub.add_parser("edit", help="Modifier une règle existante.")
    rule_edit.add_argument("ruleset_id", type=int)
    rule_edit.add_argument("rule_index", type=int, help="Index (1-based) de la règle à modifier.")
    rule_edit.set_defaults(handler=handle_rule_edit)

    rule_delete = rule_sub.add_parser("delete", help="Supprimer une règle d'un ruleset.")
    rule_delete.add_argument("ruleset_id", type=int)
    rule_delete.add_argument("rule_index", type=int, help="Index (1-based) de la règle à supprimer.")
    rule_delete.add_argument(
        "-y", "--yes", action="store_true", help="Confirmation automatique (non interactif)."
    )
    rule_delete.set_defaults(handler=handle_rule_delete)

    contexts_parser = subparsers.add_parser(
        "checks", help="Lister les checks (statuts/actions) récemment observés."
    )
    contexts_parser.add_argument(
        "--ref",
        help="Référence (branche ou SHA) pour détecter les checks. Défaut : branche par défaut.",
    )
    contexts_parser.add_argument(
        "--pr",
        type=int,
        action="append",
        help="Numéro de pull request à inclure (répétable).",
    )
    contexts_parser.add_argument(
        "--latest-pr",
        action="store_true",
        help="Inclure automatiquement la PR ouverte la plus récente.",
    )
    contexts_parser.add_argument(
        "--no-default",
        action="store_true",
        help="Ne pas analyser le commit de la branche par défaut.",
    )
    contexts_parser.set_defaults(handler=handle_checks_list)

    return parser


# ---------------------------------------------------------------------------
# Basic commands


def handle_list(api: GitHubAPI, args: argparse.Namespace) -> None:
    rulesets = api.list_rulesets() or []
    if args.json:
        print(json.dumps(rulesets, indent=2))
        return

    if not rulesets:
        print("Aucun ruleset dans ce dépôt.")
        return

    headers = ["ID", "Nom", "Cible", "Mode", "Règles", "Mis à jour"]
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
            f"Supprimer le ruleset {args.ruleset_id} ? Cette action est irréversible.",
            default=False,
        )
        if not confirm:
            print("Suppression annulée.")
            return
    api.delete_ruleset(args.ruleset_id)
    print(f"Ruleset {args.ruleset_id} supprimé.")


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

    created = api.create_ruleset(payload)
    print(f"Ruleset créé avec succès (ID {created.get('id')}).")


def handle_update(api: GitHubAPI, args: argparse.Namespace) -> None:
    if args.file:
        payload = load_json_file(args.file)
    else:
        existing = api.get_ruleset(args.ruleset_id)
        payload = interactive_ruleset_builder(api, prepare_ruleset_payload(existing))

    if args.editor:
        payload = open_editor_with_json(payload)

    updated = api.update_ruleset(args.ruleset_id, payload)
    print(f"Ruleset {updated.get('id')} mis à jour.")


# ---------------------------------------------------------------------------
# Rule sub-commands


def handle_rule_list(api: GitHubAPI, args: argparse.Namespace) -> None:
    ruleset = api.get_ruleset(args.ruleset_id)
    rules = ruleset.get("rules") or []
    if not rules:
        print("Ce ruleset ne contient aucune règle.")
        return
    for idx, rule in enumerate(rules, start=1):
        summary = summarize_rule(rule)
        print(f"[{idx}] {summary}")


def handle_rule_add(api: GitHubAPI, args: argparse.Namespace) -> None:
    existing = api.get_ruleset(args.ruleset_id)
    payload = prepare_ruleset_payload(existing)
    payload["rules"] = manage_rules_interactively(
        api, payload.get("rules", []), action="add"
    )
    updated = api.update_ruleset(args.ruleset_id, payload)
    print(f"Règle ajoutée. Le ruleset compte désormais {len(updated.get('rules', []))} règles.")


def handle_rule_edit(api: GitHubAPI, args: argparse.Namespace) -> None:
    existing = api.get_ruleset(args.ruleset_id)
    payload = prepare_ruleset_payload(existing)
    rules = payload.get("rules", [])
    index = args.rule_index - 1
    if index < 0 or index >= len(rules):
        raise RuntimeError("Index de règle invalide.")
    rules[index] = edit_rule_interactively(api, rules[index])
    updated = api.update_ruleset(args.ruleset_id, payload)
    print(f"Règle {args.rule_index} mise à jour. ({summary_for_rule(updated['rules'][index])})")


def handle_rule_delete(api: GitHubAPI, args: argparse.Namespace) -> None:
    existing = api.get_ruleset(args.ruleset_id)
    payload = prepare_ruleset_payload(existing)
    rules = payload.get("rules", [])
    index = args.rule_index - 1
    if index < 0 or index >= len(rules):
        raise RuntimeError("Index de règle invalide.")
    if not args.yes:
        summary = summarize_rule(rules[index])
        if not prompt_yes_no(f"Supprimer la règle [{args.rule_index}] {summary} ?", default=False):
            print("Suppression annulée.")
            return
    removed = rules.pop(index)
    api.update_ruleset(args.ruleset_id, payload)
    print(f"Règle supprimée : {summarize_rule(removed)}")


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
            warnings.append(f"Branche par défaut: {exc}")
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
                warnings.append(f"PR #{number}: {exc}")
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
            warnings.append(f"PR la plus récente (ouverte): {exc}")
            if exc.stderr:
                warnings.append(exc.stderr.strip())
        if not latest:
            try:
                latest = api.get_latest_merged_pull_request()
            except GitHubAPIError as exc:
                warnings.append(f"PR la plus récente (fusionnée): {exc}")
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
                warnings.append("PR la plus récente: impossible de déterminer le SHA du head.")
        else:
            warnings.append("Aucune PR ouverte ni fusionnée récemment trouvée.")

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
        print(f"Avertissement: {warning}", file=sys.stderr)

    if not context_entries:
        print("Aucun check détecté parmi les références inspectées.")
        return

    print("Checks détectés :")
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
        print(f"- {label}  [sources: {origins}]")

    if inspected_sources:
        print("\nRéférences analysées :")
        for label in inspected_sources:
            print(f"- {label}")


# ---------------------------------------------------------------------------
# Interactive helpers


def interactive_ruleset_builder(
    api: GitHubAPI,
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data = deepcopy(existing) if existing else {}

    data["name"] = prompt_string("Nom du ruleset", default=data.get("name"))
    data["target"] = prompt_choice(
        "Cible du ruleset",
        TARGET_CHOICES,
        default=data.get("target", "branch"),
    )
    data["enforcement"] = prompt_choice(
        "Mode d'application",
        ENFORCEMENT_CHOICES,
        default=data.get("enforcement", "active"),
    )

    conditions = data.get("conditions", {})
    ref_conditions = conditions.get("ref_name", {})
    include_defaults = [strip_ref_prefix(value) for value in ref_conditions.get("include", [])]
    exclude_defaults = [strip_ref_prefix(value) for value in ref_conditions.get("exclude", [])]

    include = prompt_multi_value(
        f"Cibles {data['target']} à inclure (laisser vide pour toutes)",
        default=include_defaults,
        formatter=lambda value: format_ref_pattern(value, data["target"]),
    )
    exclude = prompt_multi_value(
        f"Cibles {data['target']} à exclure",
        default=exclude_defaults,
        formatter=lambda value: format_ref_pattern(value, data["target"]),
    )

    new_conditions = {}
    if include or exclude:
        new_conditions["ref_name"] = {"include": include, "exclude": exclude}
    data["conditions"] = new_conditions

    bypass = data.get("bypass_actors")
    if bypass and prompt_yes_no("Souhaitez-vous modifier les bypass existants ?", default=False):
        bypass = edit_bypass_actors(bypass)
    elif bypass is None:
        bypass = []
        if prompt_yes_no("Définir des acteurs autorisés à contourner le ruleset ?", default=False):
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

        print("\nRègles actuelles :")
        if not rules:
            print("- (aucune)")
        else:
            for idx, rule in enumerate(rules, start=1):
                print(f"[{idx}] {summarize_rule(rule)}")

        print("\nOptions :")
        print("1. Ajouter une règle")
        if rules:
            print("2. Modifier une règle")
            print("3. Supprimer une règle")
            print("4. Terminer")
            choices = {"1", "2", "3", "4"}
        else:
            print("2. Terminer")
            choices = {"1", "2"}

        choice = input("Votre choix: ").strip()
        if choice not in choices:
            print("Choix invalide.")
            continue

        if choice == "1":
            rules.append(add_rule_interactively(api))
        elif choice == "2":
            if not rules:
                return rules
            idx = select_rule_index(rules, "modifier")
            rules[idx] = edit_rule_interactively(api, rules[idx])
        elif choice == "3":
            idx = select_rule_index(rules, "supprimer")
            removed = rules.pop(idx)
            print(f"Règle supprimée : {summarize_rule(removed)}")
        else:
            return rules


def add_rule_interactively(api: GitHubAPI) -> Dict[str, Any]:
    print("\nType de règle à ajouter :")
    print("1. Checks requis (required_status_checks)")
    print("2. Éditeur JSON libre")
    choice = input("Votre choix [1]: ").strip() or "1"
    if choice == "1":
        return build_required_status_rule(api)
    payload = open_editor_with_json({"type": "", "parameters": {}})
    validate_rule_payload(payload)
    return payload


def edit_rule_interactively(api: GitHubAPI, rule: Dict[str, Any]) -> Dict[str, Any]:
    if rule.get("type") == "required_status_checks":
        print("Modification d'une règle de checks requis.")
        return build_required_status_rule(api, existing=rule)

    print("Modification via éditeur JSON.")
    payload = open_editor_with_json(rule)
    validate_rule_payload(payload)
    return payload


def build_required_status_rule(
    api: GitHubAPI,
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    params = existing.get("parameters", {}) if existing else {}
    contexts = params.get("required_status_checks", [])
    print("\nConfiguration des checks requis.")
    available_entries: List[Dict[str, Any]] = []
    if prompt_yes_no("Lister les checks récemment observés ?", default=True):
        include_default = prompt_yes_no("Inclure la branche par défaut ?", default=True)
        include_latest_pr = prompt_yes_no(
            "Inclure la PR ouverte ou récemment fusionnée la plus récente ?", default=True
        )
        pr_numbers: List[int] = []
        pr_input = input("Numéros de PR supplémentaires (séparés par des espaces) : ").strip()
        if pr_input:
            for token in pr_input.split():
                if token.isdigit():
                    pr_numbers.append(int(token))
                else:
                    print(f"Numéro de PR ignoré (non numérique) : {token}")
        ref_input = input("Références supplémentaires (branches ou SHAs, séparées par des espaces) : ").strip()
        extra_refs = [value.strip() for value in ref_input.split() if value.strip()] if ref_input else []

        available_entries, inspected_sources, warnings = collect_check_contexts(
            api,
            include_default=include_default,
            refs=extra_refs,
            prs=pr_numbers,
            include_latest_pr=include_latest_pr,
        )
        for warning in warnings:
            print(f"Avertissement: {warning}")
        if inspected_sources:
            print("Références analysées :")
            for label in inspected_sources:
                print(f"- {label}")
        if not available_entries:
            print("Aucun check détecté pour les références sélectionnées.")

    contexts = prompt_status_checks(contexts, available_entries)
    cleaned_checks: List[Dict[str, Any]] = []
    for item in contexts:
        entry = {"context": item["context"]}
        if item.get("integration_id") is not None:
            entry["integration_id"] = item["integration_id"]
        cleaned_checks.append(entry)
    strict = prompt_yes_no(
        "Exiger que les PR soient testées avec le dernier commit (strict_required_status_checks_policy) ?",
        default=params.get("strict_required_status_checks_policy", True),
    )
    do_not_enforce = prompt_yes_no(
        "Autoriser la création de refs même si les checks ne passent pas (do_not_enforce_on_create) ?",
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
        print("\nChecks actuellement requis :")
        if not checks:
            print("- (aucun)")
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
            print("\nChecks récemment observés :")
            for idx, label in enumerate(available_labels, start=1):
                print(f"{idx}. {label}")

        print("\nOptions :")
        print("1. Ajouter un check")
        if checks:
            print("2. Retirer un check")
            print("3. Terminer")
            valid = {"1", "2", "3"}
        else:
            print("2. Terminer")
            valid = {"1", "2"}

        choice = input("Votre choix: ").strip()
        if choice not in valid:
            print("Choix invalide.")
            continue
        if choice == "1":
            context_input = input("Nom du check (ou numéro de la liste ci-dessus): ").strip()
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
                    print("Index invalide.")
                    continue
            else:
                context = context_input
            if not context:
                print("Nom obligatoire.")
                continue
            prompt_suffix = (
                f" (laisser vide pour utiliser {integration_default})" if integration_default is not None else ""
            )
            integration_raw = input(f"Integration ID{prompt_suffix}: ").strip()
            if integration_raw:
                if not integration_raw.isdigit():
                    print("Integration ID doit être numérique.")
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
            idx = select_rule_index(checks, "retirer")
            removed = checks.pop(idx)
            print(f"Check retiré : {removed['context']}")
        else:
            return checks


def edit_bypass_actors(existing: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    actors = [dict(item) for item in existing]
    while True:
        print("\nActeurs pouvant contourner le ruleset :")
        if not actors:
            print("- (aucun)")
        else:
            for idx, actor in enumerate(actors, start=1):
                label = actor_summary(actor)
                print(f"[{idx}] {label}")
        print("\nOptions :")
        print("1. Ajouter")
        if actors:
            print("2. Supprimer")
            print("3. Terminer")
            valid = {"1", "2", "3"}
        else:
            print("2. Terminer")
            valid = {"1", "2"}
        choice = input("Votre choix: ").strip()
        if choice not in valid:
            print("Choix invalide.")
            continue
        if choice == "1":
            actors.append(prompt_bypass_actor())
        elif choice == "2" and actors:
            idx = select_rule_index(actors, "supprimer")
            removed = actors.pop(idx)
            print(f"Acteur retiré : {actor_summary(removed)}")
        else:
            return actors


def prompt_bypass_actor() -> Dict[str, Any]:
    print("\nType d'acteur :")
    print("1. RepositoryRole (ex: admin, maintain)")
    print("2. Team (ORG/slug)")
    print("3. Integration (ID numérique)")
    print("4. OrganizationAdmin")
    print("5. EnterpriseAdmin")
    choice = input("Votre choix [1]: ").strip() or "1"
    bypass_mode = prompt_choice(
        "Mode de contournement",
        ["always", "pull_request"],
        default="always",
    )
    if choice == "1":
        role = input("Nom du rôle du dépôt (ex: maintain): ").strip()
        if not role:
            raise RuntimeError("Le rôle ne peut pas être vide.")
        return {
            "actor_type": "RepositoryRole",
            "repository_role_name": role,
            "bypass_mode": bypass_mode,
        }
    if choice == "2":
        team = input("Team (ORG/slug): ").strip()
        if "/" not in team:
            raise RuntimeError("Format attendu : ORG/slug.")
        org, slug = team.split("/", 1)
        actor_id = resolve_team_id(org, slug)
        return {"actor_type": "Team", "actor_id": actor_id, "bypass_mode": bypass_mode}
    if choice == "3":
        integration = input("Integration ID: ").strip()
        if not integration.isdigit():
            raise RuntimeError("Integration ID doit être numérique.")
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
        raise RuntimeError("Impossible de récupérer l'identifiant de l'équipe.")
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
        raise RuntimeError(f"Commande {' '.join(command)} en erreur : {stderr}") from exc
    return result.stdout.decode("utf-8")


def print_ruleset_details(ruleset: Dict[str, Any]) -> None:
    print(f"ID : {ruleset.get('id')}")
    print(f"Nom : {ruleset.get('name')}")
    print(f"Cible : {ruleset.get('target')}")
    print(f"Mode : {ruleset.get('enforcement')}")
    print(f"Créé : {ruleset.get('created_at')}")
    print(f"Mis à jour : {ruleset.get('updated_at')}")

    conditions = ruleset.get("conditions") or {}
    if conditions:
        print("Conditions :")
        for key, value in conditions.items():
            print(f"  - {key}: {value}")
    bypass = ruleset.get("bypass_actors") or []
    if bypass:
        print("Acteurs pouvant contourner :")
        for actor in bypass:
            print(f"  - {actor_summary(actor)}")

    rules = ruleset.get("rules") or []
    if rules:
        print("Règles :")
        for idx, rule in enumerate(rules, start=1):
            print(f"  [{idx}] {summarize_rule(rule)}")


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
    response = input(f"Index de la règle à {action}: ").strip()
    if not response.isdigit():
        raise RuntimeError("Index numérique attendu.")
    idx = int(response) - 1
    if not (0 <= idx < len(items)):
        raise RuntimeError("Index hors limites.")
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
        raise RuntimeError("Une règle doit être un objet JSON avec la clé 'type'.")


def strip_ref_prefix(value: str) -> str:
    for prefix in ("refs/heads/", "refs/tags/"):
        if value.startswith(prefix):
            return value[len(prefix) :]
    return value


def format_ref_pattern(value: str, target: str) -> str:
    value = value.strip()
    if not value:
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
