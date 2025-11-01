from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence

from .i18n import translate as _


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
        print(_("error_value_required", "Please enter a value."))


def prompt_choice(
    message: str,
    choices: Sequence[str],
    *,
    default: Optional[str] = None,
) -> str:
    """Prompt user to pick one choice from a list."""

    if not choices:
        raise ValueError(_("error_empty_choice_list", "Choice list is empty."))

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
        print(_("error_invalid_choice", "Invalid response, please choose a valid index."))


def prompt_yes_no(message: str, *, default: bool = False) -> bool:
    default_label = _("prompt_yes_no_default_yes", "Y/n") if default else _(
        "prompt_yes_no_default_no", "y/N"
    )
    while True:
        response = input(f"{message} [{default_label}]: ").strip().lower()
        if not response:
            return default
        if response in {"o", "oui", "y", "yes"}:
            return True
        if response in {"n", "non", "no"}:
            return False
        print(_("prompt_yes_no_invalid", "Please answer yes or no."))


def prompt_multi_value(
    message: str,
    *,
    default: Optional[Iterable[str]] = None,
    formatter=lambda x: x,
) -> List[str]:
    """Prompt user to enter multiple lines until empty line."""

    values: List[str] = []
    default_list = list(default or [])
    if default_list and prompt_yes_no(
        _("prompt_keep_existing", "{message} (keep existing values?)", message=message),
        default=True,
    ):
        return [formatter(value) for value in default_list]

    print(
        _(
            "prompt_multi_value_hint",
            "{message} (leave blank to finish)",
            message=message,
        )
    )
    while True:
        response = input("> ").strip()
        if not response:
            break
        values.append(formatter(response))
    return values


def _resolve_editor() -> str:
    for env_var in ("VISUAL", "EDITOR"):
        value = os.environ.get(env_var)
        if value:
            return value

    command = ["gh", "config", "get", "editor"]
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except FileNotFoundError:
        completed = None
    except subprocess.CalledProcessError:
        completed = None
    if completed:
        gh_editor = completed.stdout.decode("utf-8").strip()
        if gh_editor:
            return gh_editor

    if sys.platform == "win32":
        return "notepad"

    for candidate in ("nano", "vi"):
        if shutil.which(candidate):
            return candidate

    raise RuntimeError(
        _(
            "prompt_editor_not_found",
            "No editor detected (VISUAL/EDITOR, gh config get editor). Set one or use --file to provide JSON.",
        )
    )


def open_editor_with_json(
    data: Any,
    *,
    header: Optional[str] = None,
    allow_comments: bool = False,
) -> Any:
    """Open user editor and return parsed JSON."""

    editor = _resolve_editor()

    with tempfile.NamedTemporaryFile("w+", suffix=".json", delete=False) as tmp:
        path = Path(tmp.name)
        if header:
            header_lines = header.strip().splitlines()
            for line in header_lines:
                tmp.write(f"# {line}\n")
            tmp.write("\n")
        json.dump(data, tmp, indent=2, ensure_ascii=False)
        tmp.flush()

    try:
        subprocess.run(f"{editor} {path}", shell=True, check=True)
        with path.open("r", encoding="utf-8") as handle:
            content = handle.read()
        if allow_comments:
            filtered_lines = []
            for line in content.splitlines():
                stripped = line.lstrip()
                if stripped.startswith("#") or stripped.startswith("//"):
                    continue
                filtered_lines.append(line)
            content = "\n".join(filtered_lines)
        if not content.strip():
            raise RuntimeError(_("prompt_empty_editor_content", "Editor content is empty."))
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:  # pragma: no cover - interactive flow
            raise RuntimeError(
                _(
                    "prompt_invalid_json",
                    "Provided content is not valid JSON. Remove or fix annotations.",
                )
            ) from exc
    except subprocess.CalledProcessError as exc:  # pragma: no cover - interactive flow
        raise RuntimeError(
            _("prompt_open_editor_error", "Editor exited with an error ({exc}).", exc=exc)
        ) from exc
    finally:
        try:
            path.unlink()
        except OSError:
            pass
