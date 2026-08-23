"""Gate <-> git state: the commit/reset/tag recipe PROGRAM.md prescribes.

Simulates manager steps in a throwaway repo: accept advances the branch,
reject resets to the pre-edit commit, accept_new_best moves the best tag,
and a crash never leaves an unscored commit on the branch.
"""
import subprocess
from pathlib import Path

import pytest

from gate import decide


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture()
def repo(tmp_path):
    git_dir = tmp_path / "repo"
    git_dir.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(git_dir)], check=True)
    git(git_dir, "config", "user.email", "t@t")
    git(git_dir, "config", "user.name", "t")
    (git_dir / "SKILL.md").write_text("baseline\n", encoding="utf-8")
    git(git_dir, "add", "-A")
    git(git_dir, "commit", "-qm", "baseline")
    git(git_dir, "tag", "best/demo")
    return git_dir


def commit_candidate(repo: Path, content: str) -> str:
    (repo / "SKILL.md").write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "candidate")
    return git(repo, "rev-parse", "HEAD")


def test_reject_resets_to_pre_edit_commit(repo):
    base = git(repo, "rev-parse", "HEAD")
    commit_candidate(repo, "worse skill\n")
    decision = decide(candidate=0.60, current=0.65, best=0.70, min_delta=0.01)
    assert decision["action"] == "reject"
    git(repo, "reset", "--hard", "-q", base)
    assert git(repo, "rev-parse", "HEAD") == base
    assert (repo / "SKILL.md").read_text() == "baseline\n"


def test_accept_advances_branch_without_moving_best(repo):
    base = git(repo, "rev-parse", "HEAD")
    sha = commit_candidate(repo, "better skill\n")
    decision = decide(candidate=0.68, current=0.65, best=0.70, min_delta=0.01)
    assert decision["action"] == "accept"
    assert git(repo, "rev-parse", "HEAD") == sha != base
    assert git(repo, "rev-parse", "best/demo") == base  # tag untouched


def test_accept_new_best_moves_tag(repo):
    sha = commit_candidate(repo, "best skill yet\n")
    decision = decide(candidate=0.75, current=0.65, best=0.70, min_delta=0.01)
    assert decision["action"] == "accept_new_best"
    git(repo, "tag", "-f", "best/demo", sha)
    assert git(repo, "rev-parse", "best/demo") == sha


def test_orphan_commit_detection(repo):
    """Resume ritual: a commit with no results.tsv row is an unscored orphan."""
    base = git(repo, "rev-parse", "HEAD")
    results = repo / "results.tsv"
    results.write_text(f"commit\tstatus\n{base[:7]}\tkeep\n", encoding="utf-8")
    orphan = commit_candidate(repo, "unscored candidate\n")
    logged = {line.split("\t")[0] for line in results.read_text().splitlines()[1:]}
    assert orphan[:7] not in logged  # detected as orphan -> manager must reset and redo
    git(repo, "reset", "--hard", "-q", base)
    assert git(repo, "rev-parse", "HEAD") == base
