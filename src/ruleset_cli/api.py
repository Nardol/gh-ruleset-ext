from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


class GitHubAPIError(RuntimeError):
    """Raised when invoking `gh api` fails."""

    def __init__(self, message: str, stderr: str | None = None) -> None:
        super().__init__(message)
        self.stderr = stderr


@dataclass(slots=True)
class Repository:
    owner: str
    name: str
    hostname: Optional[str] = None

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"


class GitHubAPI:
    """Small wrapper around `gh api` with JSON helpers."""

    def __init__(self, repo: Repository, *, api_version: str = "2022-11-28") -> None:
        self.repo = repo
        self.api_version = api_version

    def _run(
        self,
        path: str,
        *,
        method: str = "GET",
        input_data: Optional[Dict[str, Any]] = None,
        params: Optional[Iterable[str]] = None,
    ) -> Any:
        """Invoke `gh api` with JSON response."""

        command: List[str] = ["gh", "api"]
        if self.repo.hostname:
            command.extend(["--hostname", self.repo.hostname])
        command.extend(
            [
                f"/repos/{self.repo.full_name}/{path.lstrip('/')}",
                "--method",
                method.upper(),
                "-H",
                "Accept: application/vnd.github+json",
                "-H",
                f"X-GitHub-Api-Version: {self.api_version}",
            ]
        )

        if params:
            command.extend(params)

        stdin_bytes: Optional[bytes] = None
        if input_data is not None:
            command.extend(["--input", "-"])
            stdin_bytes = json.dumps(input_data, separators=(",", ":")).encode("utf-8")

        try:
            completed = subprocess.run(
                command,
                input=stdin_bytes,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as exc:  # pragma: no cover - interactive flow
            stderr = exc.stderr.decode("utf-8", errors="replace")
            raise GitHubAPIError(
                f"Échec de l'appel API GitHub ({method} {path}): {stderr}",
                stderr=stderr,
            ) from exc

        stdout_text = completed.stdout.decode("utf-8")
        if not stdout_text.strip():
            return None

        try:
            return json.loads(stdout_text)
        except json.JSONDecodeError as exc:
            raise GitHubAPIError(
                f"Réponse JSON invalide pour {method} {path}: {stdout_text}",
            ) from exc

    # Repository rulesets -------------------------------------------------

    def list_rulesets(self, *, include_links: bool = False) -> List[Dict[str, Any]]:
        params: List[str] = []
        if include_links:
            params.extend(["--include", "next"])
        return self._run("rulesets", params=params)

    def get_ruleset(self, ruleset_id: int) -> Dict[str, Any]:
        return self._run(f"rulesets/{ruleset_id}")

    def delete_ruleset(self, ruleset_id: int) -> None:
        self._run(f"rulesets/{ruleset_id}", method="DELETE")

    def create_ruleset(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._run("rulesets", method="POST", input_data=payload)

    def update_ruleset(self, ruleset_id: int, payload: Dict[str, Any]) -> Dict[str, Any]:
        return self._run(f"rulesets/{ruleset_id}", method="PUT", input_data=payload)

    def list_available_rules(self) -> List[Dict[str, Any]]:
        return self._run("rulesets/rules")

    # Pull requests -------------------------------------------------------

    def get_pull_request_head_sha(self, number: int) -> tuple[str, Optional[str]]:
        data = self._run(f"pulls/{number}")
        head = data.get("head", {})
        sha = head.get("sha")
        if not sha:
            raise GitHubAPIError(f"Impossible de récupérer le commit de la PR #{number}.")
        return sha, head.get("ref")

    def get_latest_open_pull_request(self) -> Optional[Dict[str, Any]]:
        prs = self._run(
            "pulls",
            params=[
                "-f",
                "state=open",
                "-f",
                "sort=updated",
                "-f",
                "direction=desc",
                "-f",
                "per_page=1",
            ],
        )
        if isinstance(prs, list) and prs:
            return prs[0]
        return None

    def get_latest_merged_pull_request(self) -> Optional[Dict[str, Any]]:
        page = 1
        per_page = 20
        while page <= 5:
            prs = self._run(
                "pulls",
                params=[
                    "-f",
                    "state=closed",
                    "-f",
                    "sort=updated",
                    "-f",
                    "direction=desc",
                    "-f",
                    f"per_page={per_page}",
                    "-f",
                    f"page={page}",
                ],
            )
            if not prs:
                break
            for pr in prs:
                if pr.get("merged_at"):
                    return pr
            if len(prs) < per_page:
                break
            page += 1
        return None

    # Helpers -------------------------------------------------------------

    def get_default_branch(self) -> str:
        data = self._call_repo_view(["--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name"])
        if not data:
            raise GitHubAPIError("Impossible de déterminer la branche par défaut du dépôt.")
        return data.strip()

    def get_latest_commit_sha(self, branch: str) -> str:
        response = self._run(f"commits/{branch}")
        sha = response.get("sha")
        if not sha:
            raise GitHubAPIError(f"Impossible de récupérer le dernier commit pour {branch}.")
        return sha

    def list_check_contexts(self, ref: str) -> List[Dict[str, Any]]:
        """Return unique status check contexts for a ref."""
        entries: List[Dict[str, Any]] = []
        seen: set[tuple[str, Optional[int], Optional[str], str]] = set()

        try:
            status = self._run(f"commits/{ref}/status")
        except GitHubAPIError:
            status = {}
        for status_obj in status.get("statuses", []):
            context = status_obj.get("context")
            if not context:
                continue
            key = (context, None, None, "status")
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                {
                    "context": context,
                    "integration_id": None,
                    "app_slug": None,
                    "app_name": None,
                    "type": "status",
                }
            )

        try:
            check_runs = self._run(f"commits/{ref}/check-runs")
        except GitHubAPIError:
            check_runs = {}
        for check in check_runs.get("check_runs", []):
            name = check.get("name")
            if not name:
                continue
            app = check.get("app") or {}
            integration_id = app.get("id")
            app_slug = app.get("slug")
            app_name = app.get("name")
            key = (name, integration_id, app_slug, "check_run")
            if key in seen:
                continue
            seen.add(key)
            entries.append(
                {
                    "context": name,
                    "integration_id": integration_id,
                    "app_slug": app_slug,
                    "app_name": app_name,
                    "type": "check_run",
                }
            )

        entries.sort(key=lambda item: (item["context"], item.get("integration_id") or -1))
        return entries

    def _call_repo_view(self, extra_args: Optional[Iterable[str]] = None) -> str:
        command = ["gh", "repo", "view", self.repo.full_name]
        if self.repo.hostname:
            command.extend(["--hostname", self.repo.hostname])
        if extra_args:
            command.extend(extra_args)
        try:
            completed = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
        except subprocess.CalledProcessError as exc:  # pragma: no cover - interactive flow
            stderr = exc.stderr.decode("utf-8", errors="replace")
            raise GitHubAPIError(f"gh repo view a échoué: {stderr}", stderr=stderr) from exc
        return completed.stdout.decode("utf-8")
