# loc-skip
import os
import shutil
import subprocess
from pathlib import Path

import click

from grv.config import extract_repo_id, get_grv_root
from grv.constants import (
    DEFAULT_SHELL,
    REPOS_DIR,
    SHELL_ENV_VAR,
    TREE_BRANCHES_DIR,
    TRUNK_DIR,
)
from grv.git import ensure_base_repo, ensure_worktree, get_default_branch
from grv.pr import is_pr_url, resolve_pr
from grv.status import (
    BranchStatus,
    get_all_repos,
    get_branch_status,
    get_repo_branches_fast,
)


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """Manage git worktrees with ease.

    \b
    Examples:
        grv shell git@github.com:user/repo.git
        grv shell git@github.com:user/repo.git feature-branch
        grv shell https://github.com/user/repo/pull/123
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


def _resolve_worktree(
    repo: str, branch: str | None, from_branch: str | None, err: bool = False
) -> Path:
    """Resolve repo/branch to worktree path, creating if needed.

    Args:
        repo: Git URL or GitHub PR URL
        branch: Branch name (None for default branch, must be None for PR URLs)
        from_branch: Base branch for new branches
        err: If True, output progress to stderr instead of stdout

    Returns:
        Path to the worktree directory
    """
    output = (
        click.echo if not err else lambda msg, **kw: click.echo(msg, err=True, **kw)
    )
    secho = (
        click.secho if not err else lambda msg, **kw: click.secho(msg, err=True, **kw)
    )

    # Handle PR URLs
    if is_pr_url(repo):
        if branch is not None:
            secho("Cannot specify branch argument with a PR URL.", fg="red")
            raise SystemExit(1)
        output("Resolving PR...")
        try:
            pr_info = resolve_pr(repo)
        except RuntimeError as e:
            secho(str(e), fg="red")
            raise SystemExit(1) from e
        repo = pr_info.repo_url
        branch = pr_info.branch

    root = get_grv_root()
    repo_id = extract_repo_id(repo)
    repo_path = root / REPOS_DIR / repo_id

    trunk_path = repo_path / TRUNK_DIR
    ensure_base_repo(repo, trunk_path)

    if branch is None:
        branch = get_default_branch(trunk_path)

    tree_path = repo_path / TREE_BRANCHES_DIR / branch
    ensure_worktree(trunk_path, tree_path, branch, from_branch=from_branch)

    return tree_path


@main.command()
@click.argument("repo")
@click.argument("branch", required=False)
@click.option(
    "--from",
    "from_branch",
    default=None,
    help="Base branch to create new branch from (instead of main/master).",
)
def shell(repo: str, branch: str | None = None, from_branch: str | None = None) -> None:
    """Open a shell in a git worktree.

    REPO can be a git URL or a GitHub PR URL (e.g., github.com/owner/repo/pull/123).
    """
    tree_path = _resolve_worktree(repo, branch, from_branch)
    branch_name = tree_path.name

    click.secho("\nReady! Entering worktree shell...", fg="green", bold=True)
    click.echo(f"\n  Branch: {click.style(branch_name, fg='cyan', bold=True)}")
    click.echo(f"  Path:   {click.style(str(tree_path), fg='blue')}\n")
    os.chdir(tree_path)
    user_shell = os.environ.get(SHELL_ENV_VAR, DEFAULT_SHELL)
    os.execvp(user_shell, [user_shell])


@main.command("dir")
@click.argument("repo")
@click.argument("branch", required=False)
@click.option(
    "--from",
    "from_branch",
    default=None,
    help="Base branch to create new branch from (instead of main/master).",
)
def dir_cmd(
    repo: str, branch: str | None = None, from_branch: str | None = None
) -> None:
    """Print worktree path to stdout for piping.

    REPO can be a git URL or a GitHub PR URL (e.g., github.com/owner/repo/pull/123).

    \b
    Examples:
        grv dir git@github.com:user/repo.git | xargs code
        grv dir https://github.com/user/repo/pull/123 | xargs cd
    """
    tree_path = _resolve_worktree(repo, branch, from_branch, err=True)
    click.echo(str(tree_path))


def _clean_branch(path: Path, branch_name: str, force: bool = False) -> bool:
    """Clean a single branch if safe. Returns True if cleaned."""
    # Find trunk path
    idx = path.parts.index(TREE_BRANCHES_DIR)
    repo_root = Path(*path.parts[:idx])
    trunk_path = repo_root / TRUNK_DIR

    status = get_branch_status(path, trunk_path, branch_name)

    if not force and not status.is_safe_to_clean:
        click.secho(f"\nCannot clean '{branch_name}' - not safe to remove.", fg="red")
        if not status.has_remote:
            click.echo("  - No remote branch found")
        if status.unpushed_commits > 0:
            click.echo(f"  - {status.unpushed_commits} unpushed commit(s)")
        if status.uncommitted_changes > 0:
            click.echo(f"  - {status.uncommitted_changes} uncommitted changes")
        return False

    if force and not status.is_safe_to_clean:
        click.secho(f"\nForce deleting '{branch_name}'...", fg="yellow")
    else:
        click.secho(f"\nCleaning '{branch_name}'...", fg="green")

    # Remove worktree and branch
    for cmd in [
        ["git", "worktree", "remove", "--force" if force else "", str(path)],
        ["git", "branch", "-D" if force else "-d", branch_name],
    ]:
        cmd = [c for c in cmd if c]  # Filter empty strings
        subprocess.run(cmd, cwd=trunk_path, capture_output=True)

    # Check if repo is now empty
    if not get_repo_branches_fast(repo_root):
        click.echo(
            f"  Removing empty repo {click.style(repo_root.name, fg='yellow')}..."
        )
        shutil.rmtree(repo_root)

    click.secho("Done.", fg="green")
    return True


@main.command("list")
def list_cmd() -> None:
    """List all worktrees and select one to enter."""
    from grv.menu import MenuAction, interactive_select, shell_into

    repos = get_all_repos()

    if not repos:
        click.secho("No repositories found.", fg="yellow")
        click.echo(f"Workspace: {click.style(str(get_grv_root()), fg='blue')}\n")
        click.echo("Get started: " + click.style("grv shell <repo-url>", fg="cyan"))
        return

    if result := interactive_select():
        path, branch_name, action = result

        if action == MenuAction.SHELL:
            shell_into(path, branch_name)
        elif action == MenuAction.CLEAN:
            _clean_branch(path, branch_name, force=False)
        elif action == MenuAction.DELETE and click.confirm(
            f"\nForce delete '{branch_name}'? This cannot be undone.", default=False
        ):
            _clean_branch(path, branch_name, force=True)


@main.command()
@click.option("--dry-run", "-n", is_flag=True, help="Show what would be cleaned")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
def clean(dry_run: bool, force: bool) -> None:
    """Remove worktrees that are safe to clean."""
    repos = get_all_repos()
    if not repos:
        click.secho("No repositories to scan.", fg="yellow")
        return

    # Collect all branches first (fast)
    all_branches = [(r, b) for _, r in repos for b in get_repo_branches_fast(r)]
    total = len(all_branches)
    if not total:
        click.secho("No branches to scan.", fg="yellow")
        return

    to_clean: list[BranchStatus] = []
    for i, (repo_path, branch) in enumerate(all_branches, 1):
        click.echo(f"\rScanning branch {i}/{total}...", nl=False)
        status = get_branch_status(branch.path, repo_path / TRUNK_DIR, branch.name)
        if status.is_safe_to_clean:
            to_clean.append(status)
    click.echo(f"\rScanning branch {total}/{total}... done")

    if not to_clean:
        click.secho("Nothing to clean.", fg="green")
        return

    click.secho("\nWorktrees to clean:", bold=True)
    for b in to_clean:
        click.echo(f"  {click.style(b.name, fg='cyan')} ({b.path})")

    if dry_run:
        click.secho(f"\nWould remove {len(to_clean)} worktree(s).", fg="yellow")
        return

    if not force:
        click.confirm(f"\nRemove {len(to_clean)} worktree(s)?", abort=True)
    click.echo("")
    affected_repos: set[Path] = set()
    for b in to_clean:
        idx = b.path.parts.index(TREE_BRANCHES_DIR)
        repo_root = Path(*b.path.parts[:idx])
        affected_repos.add(repo_root)
        click.echo(f"  Removing {click.style(b.name, fg='cyan')}...", nl=False)
        for cmd in [
            ["git", "worktree", "remove", str(b.path)],
            ["git", "branch", "-d", b.name],
        ]:
            subprocess.run(cmd, cwd=repo_root / TRUNK_DIR, capture_output=True)
        click.secho(" done", fg="green")

    repos_removed = 0
    for repo_root in affected_repos:
        if not get_repo_branches_fast(repo_root):
            click.echo(
                f"  Removing empty repo {click.style(repo_root.name, fg='yellow')}...",
                nl=False,
            )
            shutil.rmtree(repo_root)
            repos_removed += 1
            click.secho(" done", fg="green")

    suffix = f" and {repos_removed} empty repo(s)" if repos_removed else ""
    click.secho(
        f"\nCleaned {len(to_clean)} worktree(s){suffix}.", fg="green", bold=True
    )


if __name__ == "__main__":
    main()
