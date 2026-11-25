from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo

from casr.extraction import extract_git_changes, normalize_repo_path


def commit(repo: Repo, message: str) -> str:
    repo.index.add([item.path for item in repo.untracked_files])
    repo.index.commit(message)
    return repo.head.commit.hexsha


def make_repo(tmp_path: Path) -> Repo:
    repo = Repo.init(tmp_path)
    with repo.config_writer() as config:
        config.set_value("user", "name", "CASR Test")
        config.set_value("user", "email", "casr-test@example.invalid")
    (tmp_path / "README.md").write_text("fixture\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/shared.py").write_text("value = 1\n", encoding="utf-8")
    (tmp_path / "src/removed.py").write_text("remove me\n", encoding="utf-8")
    (tmp_path / "src/old_name.py").write_text("def renamed():\n    return True\n", encoding="utf-8")
    repo.index.add(["README.md", "src/shared.py", "src/removed.py", "src/old_name.py"])
    repo.index.commit("base")
    return repo


def test_extracts_added_modified_deleted_and_renamed_artifacts(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    base = repo.head.commit.hexsha
    (tmp_path / "src/new.py").write_text("new = True\n", encoding="utf-8")
    (tmp_path / "src/shared.py").write_text("value = 2\n", encoding="utf-8")
    repo.index.remove(["src/removed.py"], working_tree=True)
    repo.index.remove(["src/old_name.py"])
    (tmp_path / "src/new_name.py").write_text("def renamed():\n    return True\n", encoding="utf-8")
    repo.index.add(["src/new.py", "src/shared.py", "src/new_name.py"])
    repo.index.commit("agent work")

    changes = extract_git_changes(tmp_path, base, repo.head.commit.hexsha)
    by_path = {item.path: item for item in changes}
    assert set(by_path) == {
        "src/new.py",
        "src/shared.py",
        "src/removed.py",
        "src/new_name.py",
    }
    assert by_path["src/new.py"].baseline_blob is None
    assert by_path["src/new.py"].current_blob is not None
    assert by_path["src/shared.py"].baseline_blob is not None
    assert by_path["src/shared.py"].current_blob is not None
    assert by_path["src/removed.py"].baseline_blob is not None
    assert by_path["src/removed.py"].current_blob is None
    assert by_path["src/new_name.py"].baseline_blob is not None
    assert by_path["src/new_name.py"].current_blob is not None
    assert by_path["src/new.py"].baseline_mode is None
    assert by_path["src/new.py"].current_mode == "100644"
    assert by_path["src/shared.py"].baseline_mode == "100644"
    assert by_path["src/shared.py"].current_mode == "100644"


def test_invalid_revision_and_empty_diff(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    revision = repo.head.commit.hexsha
    assert extract_git_changes(tmp_path, revision, revision) == []
    with pytest.raises(ValueError, match="revision"):
        extract_git_changes(tmp_path, revision, "missing-revision")


@pytest.mark.parametrize("path", ["../outside.py", "/absolute.py", "src/../x.py", "src\\x.py"])
def test_normalize_repo_path_rejects_unsafe_paths(path: str) -> None:
    with pytest.raises(ValueError):
        normalize_repo_path(path)


def test_normalize_repo_path_accepts_posix_relative_path() -> None:
    assert normalize_repo_path("src/module.py") == "src/module.py"
