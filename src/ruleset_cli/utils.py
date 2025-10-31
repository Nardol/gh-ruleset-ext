from __future__ import annotations

import subprocess
from typing import Optional
from urllib.parse import urlparse

from .api import GitHubAPIError, Repository


def parse_repository_input(value: str) -> Repository:
    """Parse repo input like owner/name or host/owner/name or URL."""

    value = value.strip()
    if value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        parts = [segment for segment in parsed.path.split("/") if segment]
        if len(parts) < 2:
            raise GitHubAPIError(
                "Impossible d'interpréter l'URL fournie. Format attendu : https://HOST/OWNER/REPO.",
            )
        owner, name = parts[-2], parts[-1]
        return Repository(owner=owner, name=name, hostname=parsed.hostname)

    parts = value.split("/")
    if len(parts) == 2:
        owner, name = parts
        return Repository(owner=owner, name=name)
    if len(parts) == 3:
        hostname, owner, name = parts
        return Repository(owner=owner, name=name, hostname=hostname)

    raise GitHubAPIError(
        "Format de dépôt invalide. Utilisez owner/repo ou hostname/owner/repo.",
    )


def resolve_repository(repo_input: Optional[str]) -> Repository:
    """Resolve repository from input or current gh context."""

    if repo_input:
        return parse_repository_input(repo_input)

    command = [
        "gh",
        "repo",
        "view",
        "--json",
        "nameWithOwner",
        "--jq",
        ".nameWithOwner",
    ]
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - interactive flow
        stderr = exc.stderr.decode("utf-8", errors="replace")
        raise GitHubAPIError(
            "Impossible de déterminer le dépôt courant avec `gh repo view`. "
            "Passez --repo OWNER/NOM.",
            stderr=stderr,
        ) from exc

    name_with_owner = completed.stdout.decode("utf-8").strip()
    if not name_with_owner:
        raise GitHubAPIError(
            "Réponse vide de `gh repo view`. Précisez --repo OWNER/NOM."
        )
    owner, name = name_with_owner.split("/")
    return Repository(owner=owner, name=name)
