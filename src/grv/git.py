import subprocess
from pathlib import Path

import click

from grv.constants import (
    GIT_CLONE_FILTER,
    GIT_REF_HEADS_FMT,
    GIT_REF_REMOTE_HEAD,
    GIT_REMOTE_NAME,
)


def run_git(
    *args: str, cwd: Path | None = None, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run a git command."""
    cmd = ["git", *args]
    if capture:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    return subprocess.run(cmd, cwd=cwd, text=True, check=True)


def get_default_branch(repo_path: Path) -> str:
    """Get the default branch name (main or master)."""
    result = run_git("symbolic-ref", GIT_REF_REMOTE_HEAD, cwd=repo_path, capture=True)
    return result.stdout.strip().split("/")[-1]


def branch_exists_locally(base_path: Path, branch: str) -> bool:
    """Check if a branch exists locally."""
    ref = GIT_REF_HEADS_FMT.format(branch=branch)
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", ref],
        cwd=base_path,
    )
    return result.returncode == 0


def ensure_base_repo(repo_url: str, base_path: Path) -> None:
    """Ensure the base repository exists and is up to date."""
    if base_path.exists():
        click.secho("Fetching latest changes...", fg="blue", err=True)
        run_git("fetch", "--all", "--prune", cwd=base_path)
        default_branch = get_default_branch(base_path)
        detach_ref = f"{GIT_REMOTE_NAME}/{default_branch}"
        run_git("checkout", "--detach", detach_ref, cwd=base_path)
    else:
        click.secho(
            "Cloning repository (this may take a moment)...", fg="blue", err=True
        )
        base_path.parent.mkdir(parents=True, exist_ok=True)
        run_git("clone", GIT_CLONE_FILTER, repo_url, str(base_path))
        default_branch = get_default_branch(base_path)
        detach_ref = f"{GIT_REMOTE_NAME}/{default_branch}"
        run_git("checkout", "--detach", detach_ref, cwd=base_path)


def ensure_worktree(base_path: Path, tree_path: Path, branch: str) -> None:
    """Ensure the worktree exists for the given branch."""
    if tree_path.exists():
        click.secho("Worktree ready.", fg="green", err=True)
        return

    click.secho(f"Setting up worktree for '{branch}'...", fg="blue", err=True)
    tree_path.parent.mkdir(parents=True, exist_ok=True)

    if branch_exists_locally(base_path, branch):
        run_git("worktree", "add", str(tree_path), branch, cwd=base_path)
        return

    result = run_git(
        "ls-remote", "--heads", GIT_REMOTE_NAME, branch, cwd=base_path, capture=True
    )

    if result.stdout.strip():
        run_git(
            "worktree",
            "add",
            "--track",
            "-b",
            branch,
            str(tree_path),
            f"{GIT_REMOTE_NAME}/{branch}",
            cwd=base_path,
        )
    else:
        default_branch = get_default_branch(base_path)
        run_git(
            "worktree",
            "add",
            "-b",
            branch,
            str(tree_path),
            default_branch,
            cwd=base_path,
        )
