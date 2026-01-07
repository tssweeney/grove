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
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("repo")
@click.argument("branch", required=False)
def shell(repo: str, branch: str | None = None) -> None:
    """Open a shell in a git worktree."""
    root = get_grv_root()
    repo_id = extract_repo_id(repo)
    repo_path = root / REPOS_DIR / repo_id

    trunk_path = repo_path / TRUNK_DIR
    ensure_base_repo(repo, trunk_path)

    if branch is None:
        branch = get_default_branch(trunk_path)

    tree_path = repo_path / TREE_BRANCHES_DIR / branch
    ensure_worktree(trunk_path, tree_path, branch)

    click.secho("\nReady! Entering worktree shell...", fg="green", bold=True)
    click.echo(f"\n  Branch: {click.style(branch, fg='cyan', bold=True)}")
    click.echo(f"  Path:   {click.style(str(tree_path), fg='blue')}\n")
    os.chdir(tree_path)
    user_shell = os.environ.get(SHELL_ENV_VAR, DEFAULT_SHELL)
    os.execvp(user_shell, [user_shell])


@main.command("list")
def list_cmd() -> None:
    """List all worktrees and select one to enter."""
    from grv.menu import interactive_select, shell_into

    repos = get_all_repos()

    if not repos:
        click.secho("No repositories found.", fg="yellow")
        click.echo(f"Workspace: {click.style(str(get_grv_root()), fg='blue')}\n")
        click.echo("Get started: " + click.style("grv shell <repo-url>", fg="cyan"))
        return

    if result := interactive_select():
        path, branch_name = result
        shell_into(path, branch_name)


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
