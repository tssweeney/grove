# loc-skip
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from grv.config import get_grv_root
from grv.constants import (
    DELETION_PATTERN,
    GIT_REMOTE_NAME,
    INSERTION_PATTERN,
    REPOS_DIR,
    TREE_BRANCHES_DIR,
    TRUNK_DIR,
)
from grv.git import get_default_branch


@dataclass
class BranchInfo:
    """Basic branch information (fast, no git operations)."""

    name: str
    path: Path


@dataclass
class BranchStatus:
    """Status information for a worktree branch."""

    name: str
    path: Path
    has_remote: bool
    is_merged: bool
    unpushed_commits: int
    uncommitted_changes: int
    insertions: int
    deletions: int

    @property
    def is_safe_to_clean(self) -> bool:
        """Check if this branch can be safely removed."""
        return (
            self.has_remote
            and self.unpushed_commits == 0
            and self.uncommitted_changes == 0
        )


def get_branch_status(tree_path: Path, trunk_path: Path, branch: str) -> BranchStatus:
    """Get status information for a worktree branch."""
    result = subprocess.run(
        ["git", "ls-remote", "--heads", GIT_REMOTE_NAME, branch],
        cwd=trunk_path,
        capture_output=True,
        text=True,
    )
    has_remote = bool(result.stdout.strip())

    default_branch = get_default_branch(trunk_path)
    result = subprocess.run(
        ["git", "branch", "--merged", f"{GIT_REMOTE_NAME}/{default_branch}"],
        cwd=tree_path,
        capture_output=True,
        text=True,
    )
    merged = [b.strip().lstrip("* ") for b in result.stdout.strip().split("\n")]
    is_merged = branch in merged

    if has_remote:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"{GIT_REMOTE_NAME}/{branch}..{branch}"],
            cwd=tree_path,
            capture_output=True,
            text=True,
        )
        unpushed = int(result.stdout.strip()) if result.returncode == 0 else 0
    else:
        rev_range = f"{GIT_REMOTE_NAME}/{default_branch}..{branch}"
        result = subprocess.run(
            ["git", "rev-list", "--count", rev_range],
            cwd=tree_path,
            capture_output=True,
            text=True,
        )
        unpushed = int(result.stdout.strip()) if result.returncode == 0 else 0

    result = subprocess.run(
        ["git", "diff", "--stat", "HEAD"],
        cwd=tree_path,
        capture_output=True,
        text=True,
    )
    uncommitted, insertions, deletions = 0, 0, 0
    if result.stdout.strip():
        summary = result.stdout.strip().split("\n")[-1]
        if "insertion" in summary or "deletion" in summary:
            ins = re.search(INSERTION_PATTERN, summary)
            dels = re.search(DELETION_PATTERN, summary)
            insertions = int(ins.group(1)) if ins else 0
            deletions = int(dels.group(1)) if dels else 0
            uncommitted = insertions + deletions

    return BranchStatus(
        name=branch,
        path=tree_path,
        has_remote=has_remote,
        is_merged=is_merged,
        unpushed_commits=unpushed,
        uncommitted_changes=uncommitted,
        insertions=insertions,
        deletions=deletions,
    )


def get_all_repos() -> list[tuple[str, Path]]:
    """Get all repos in the workspace."""
    repos_dir = get_grv_root() / REPOS_DIR
    if not repos_dir.exists():
        return []

    repos = []
    for repo_dir in repos_dir.iterdir():
        if repo_dir.is_dir() and (repo_dir / TRUNK_DIR).exists():
            repos.append((repo_dir.name, repo_dir))
    return sorted(repos)


def _find_worktrees(repo_path: Path) -> list[tuple[str, Path]]:
    """Find all worktree directories and their branch names.

    Uses `git worktree list` from the trunk to efficiently find worktrees
    without recursively scanning directories (which is slow when repos
    contain nested git repositories like node_modules or submodules).
    """
    trunk_path = repo_path / TRUNK_DIR
    tree_branches_dir = repo_path / TREE_BRANCHES_DIR

    if not trunk_path.exists():
        return []

    # Use git worktree list to get all worktrees
    result_proc = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=trunk_path,
        capture_output=True,
        text=True,
    )

    if result_proc.returncode != 0:
        return []

    result = []
    # Parse porcelain output: each worktree block starts with "worktree <path>"
    for line in result_proc.stdout.split("\n"):
        if line.startswith("worktree "):
            worktree_path = Path(line[9:])  # Skip "worktree " prefix
            # Only include worktrees under tree_branches/
            if tree_branches_dir.exists():
                try:
                    branch_name = str(worktree_path.relative_to(tree_branches_dir))
                    result.append((branch_name, worktree_path))
                except ValueError:
                    # Path is not under tree_branches_dir (e.g., trunk)
                    pass

    return sorted(result)


def get_repo_branches(repo_path: Path) -> list[BranchStatus]:
    """Get all branches for a repo with their status (slow, uses git)."""
    trunk_path = repo_path / TRUNK_DIR
    return sorted(
        [
            get_branch_status(path, trunk_path, name)
            for name, path in _find_worktrees(repo_path)
        ],
        key=lambda b: b.name,
    )


def get_repo_branches_fast(repo_path: Path) -> list[BranchInfo]:
    """Get all branches for a repo (fast, no git operations)."""
    return [
        BranchInfo(name=name, path=path) for name, path in _find_worktrees(repo_path)
    ]
