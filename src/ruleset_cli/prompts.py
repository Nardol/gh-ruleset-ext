from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence


def prompt_string(
    message: str,
    *,
    default: Optional[str] = None,
    required: bool = True,
) -> str:
    """Prompt user for a (possibly optional) string."""

    while True:
        suffix = f" [{default}]" if default else ""
        response = input(f"{message}{suffix}: ").strip()
        if response:
            return response
        if default is not None:
            return default
        if not required:
            return ""
        print("Veuillez saisir une valeur.")


def prompt_choice(
    message: str,
    choices: Sequence[str],
    *,
    default: Optional[str] = None,
) -> str:
    """Prompt user to pick one choice from a list."""

    if not choices:
        raise ValueError("La liste de choix est vide.")

    indexed = list(enumerate(choices, start=1))
    options = ", ".join(f"{idx}={label}" for idx, label in indexed)
    default_idx: Optional[int] = None
    if default and default in choices:
        default_idx = choices.index(default) + 1

    while True:
        prompt = f"{message} ({options})"
        if default_idx:
            prompt += f" [{default_idx}]"
        prompt += ": "
        response = input(prompt).strip()
        if not response and default_idx:
            return choices[default_idx - 1]
        if response.isdigit():
            idx = int(response)
            if 1 <= idx <= len(choices):
                return choices[idx - 1]
        print("Réponse invalide, veuillez choisir un index valide.")


def prompt_yes_no(message: str, *, default: bool = False) -> bool:
    default_label = "O/n" if default else "o/N"
    while True:
        response = input(f"{message} [{default_label}]: ").strip().lower()
        if not response:
            return default
        if response in {"o", "oui", "y", "yes"}:
            return True
        if response in {"n", "non", "no"}:
            return False
        print("Merci de répondre par oui ou non.")


def prompt_multi_value(
    message: str,
    *,
    default: Optional[Iterable[str]] = None,
    formatter=lambda x: x,
) -> List[str]:
    """Prompt user to enter multiple lines until empty line."""

    values: List[str] = []
    default_list = list(default or [])
    if default_list and prompt_yes_no(f"{message} (garder les valeurs existantes ?)", default=True):
        return [formatter(value) for value in default_list]

    print(f"{message} (entrée vide pour terminer)")
    while True:
        response = input("> ").strip()
        if not response:
            break
        values.append(formatter(response))
    return values


def open_editor_with_json(data: Any) -> Any:
    """Open user editor (EDITOR/VISUAL) and return parsed JSON."""

    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if not editor:
        raise RuntimeError(
            "Aucun éditeur configuré (variables d'environnement EDITOR ou VISUAL). "
            "Définissez-en un ou utilisez --file pour fournir un JSON."
        )

    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as tmp:
        path = Path(tmp.name)
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp.flush()

    try:
        subprocess.run(f"{editor} {path}", shell=True, check=True)
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except subprocess.CalledProcessError as exc:  # pragma: no cover - interactive flow
        raise RuntimeError(f"L'éditeur s'est terminé en erreur ({exc}).") from exc
    finally:
        try:
            path.unlink()
        except OSError:
            pass
