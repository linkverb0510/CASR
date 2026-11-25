from __future__ import annotations

from pathlib import Path, PurePosixPath

from git import Repo
from git.exc import BadName, BadObject

from casr.models import Artifact


def normalize_repo_path(path: str) -> str:
    candidate = PurePosixPath(path)
    if (
        not path
        or "\\" in path
        or candidate.is_absolute()
        or any(part in {"", ".", ".."} for part in path.split("/"))
        or candidate.as_posix() != path
    ):
        raise ValueError(f"unsafe repository path: {path!r}")
    return path


def extract_git_changes(
    repo_path: Path, base_revision: str, correction_revision: str
) -> list[Artifact]:
    repo = Repo(repo_path)
    try:
        base = repo.commit(base_revision)
        correction = repo.commit(correction_revision)
    except (BadName, BadObject, ValueError) as exc:
        raise ValueError("invalid git revision") from exc

    artifacts: dict[str, Artifact] = {}
    try:
        for change in base.diff(correction):
            path = normalize_repo_path(change.b_path or change.a_path)
            baseline_blob = change.a_blob.hexsha if change.a_blob is not None else None
            current_blob = change.b_blob.hexsha if change.b_blob is not None else None
            artifacts[path] = Artifact(
                artifact_id=path,
                path=path,
                baseline_blob=baseline_blob,
                current_blob=current_blob,
            )
    finally:
        repo.close()
    return [artifacts[path] for path in sorted(artifacts)]
