import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import click


def get_gitwsp_root() -> Path:
    """Get the GITWSP_ROOT directory, defaulting to ~/.gitwsp."""
    root = os.environ.get("GITWSP_ROOT", os.path.expanduser("~/.gitwsp"))
    return Path(root)


def extract_repo_id(repo: str) -> str:
    """Extract a unique repository identifier from a git URL.

    Returns a flat string like 'github_com_user_repo' that uniquely identifies
    the repository across different hosts and users.
    """
    # Handle SSH URLs like git@github.com:user/repo.git
    if repo.startswith("git@"):
        # git@github.com:user/repo.git -> github.com_user_repo
        host_and_path = repo[4:]  # Remove 'git@'
        host, path = host_and_path.split(":", 1)
        path = path.rstrip("/").removesuffix(".git")
        raw_id = f"{host}/{path}"
    elif (parsed := urlparse(repo)).netloc:
        # Handle HTTPS/HTTP URLs
        path = parsed.path.rstrip("/").removesuffix(".git").lstrip("/")
        raw_id = f"{parsed.netloc}/{path}"
    else:
        # Fallback: treat as a path
        raw_id = repo.rstrip("/").removesuffix(".git").lstrip("/")

    # Sanitize: replace . / : with underscores
    return raw_id.replace(".", "_").replace("/", "_").replace(":", "_")


def run_git(*args: str, cwd: Path | None = None, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a git command."""
    cmd = ["git", *args]
    if capture:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    return subprocess.run(cmd, cwd=cwd, check=True)


def get_default_branch(repo_path: Path) -> str:
    """Get the default branch name (main or master)."""
    result = run_git("symbolic-ref", "refs/remotes/origin/HEAD", cwd=repo_path, capture=True)
    # Returns something like "refs/remotes/origin/main"
    return result.stdout.strip().split("/")[-1]


def ensure_base_repo(repo_url: str, base_path: Path) -> None:
    """Ensure the base repository exists and is up to date.

    The base repo is kept with a detached HEAD so all branches
    can be used in worktrees.
    """
    if base_path.exists():
        click.echo(f"Updating base repo at {base_path}...", err=True)
        run_git("fetch", "--all", "--prune", cwd=base_path)
        # Update local tracking branches
        default_branch = get_default_branch(base_path)
        run_git("checkout", "--detach", f"origin/{default_branch}", cwd=base_path)
    else:
        click.echo(f"Cloning base repo to {base_path}...", err=True)
        base_path.parent.mkdir(parents=True, exist_ok=True)
        run_git("clone", "--filter=blob:none", repo_url, str(base_path))
        # Detach HEAD so branches can be used in worktrees
        default_branch = get_default_branch(base_path)
        run_git("checkout", "--detach", f"origin/{default_branch}", cwd=base_path)


def branch_exists_locally(base_path: Path, branch: str) -> bool:
    """Check if a branch exists locally."""
    result = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        cwd=base_path,
    )
    return result.returncode == 0


def ensure_worktree(base_path: Path, tree_path: Path, branch: str) -> None:
    """Ensure the worktree exists for the given branch."""
    if tree_path.exists():
        click.echo(f"Worktree already exists at {tree_path}", err=True)
        return

    click.echo(f"Creating worktree for branch '{branch}' at {tree_path}...", err=True)
    tree_path.parent.mkdir(parents=True, exist_ok=True)

    # Check if branch exists locally
    if branch_exists_locally(base_path, branch):
        # Branch exists locally, just add worktree
        run_git("worktree", "add", str(tree_path), branch, cwd=base_path)
        return

    # Check if branch exists remotely
    result = run_git("ls-remote", "--heads", "origin", branch, cwd=base_path, capture=True)

    if result.stdout.strip():
        # Branch exists on remote, create worktree tracking it
        run_git("worktree", "add", "--track", "-b", branch, str(tree_path), f"origin/{branch}", cwd=base_path)
    else:
        # Branch doesn't exist, create new branch from default
        default_branch = get_default_branch(base_path)
        run_git("worktree", "add", "-b", branch, str(tree_path), default_branch, cwd=base_path)


@dataclass
class BranchStatus:
    """Status information for a worktree branch."""

    name: str
    path: Path
    has_remote: bool
    is_merged: bool
    unpushed_commits: int
    uncommitted_changes: int  # lines changed
    insertions: int
    deletions: int

    @property
    def is_safe_to_clean(self) -> bool:
        """Check if this branch can be safely removed."""
        return self.has_remote and self.unpushed_commits == 0 and self.uncommitted_changes == 0


def get_branch_status(tree_path: Path, trunk_path: Path, branch: str) -> BranchStatus:
    """Get status information for a worktree branch."""
    # Check if remote branch exists
    result = subprocess.run(
        ["git", "ls-remote", "--heads", "origin", branch],
        cwd=trunk_path,
        capture_output=True,
        text=True,
    )
    has_remote = bool(result.stdout.strip())

    # Check if branch is merged into default branch
    default_branch = get_default_branch(trunk_path)
    result = subprocess.run(
        ["git", "branch", "--merged", f"origin/{default_branch}"],
        cwd=tree_path,
        capture_output=True,
        text=True,
    )
    merged_branches = [b.strip().lstrip("* ") for b in result.stdout.strip().split("\n")]
    is_merged = branch in merged_branches

    # Check for unpushed commits
    if has_remote:
        result = subprocess.run(
            ["git", "rev-list", "--count", f"origin/{branch}..{branch}"],
            cwd=tree_path,
            capture_output=True,
            text=True,
        )
        unpushed_commits = int(result.stdout.strip()) if result.returncode == 0 else 0
    else:
        # No remote, count commits ahead of default branch
        result = subprocess.run(
            ["git", "rev-list", "--count", f"origin/{default_branch}..{branch}"],
            cwd=tree_path,
            capture_output=True,
            text=True,
        )
        unpushed_commits = int(result.stdout.strip()) if result.returncode == 0 else 0

    # Check for uncommitted changes (staged + unstaged)
    result = subprocess.run(
        ["git", "diff", "--stat", "HEAD"],
        cwd=tree_path,
        capture_output=True,
        text=True,
    )
    uncommitted_changes = 0
    insertions = 0
    deletions = 0
    if result.stdout.strip():
        lines = result.stdout.strip().split("\n")
        if lines:
            # Parse last line like "3 files changed, 10 insertions(+), 5 deletions(-)"
            summary = lines[-1]
            if "insertion" in summary or "deletion" in summary:
                ins_match = re.search(r"(\d+) insertion", summary)
                del_match = re.search(r"(\d+) deletion", summary)
                insertions = int(ins_match.group(1)) if ins_match else 0
                deletions = int(del_match.group(1)) if del_match else 0
                uncommitted_changes = insertions + deletions

    return BranchStatus(
        name=branch,
        path=tree_path,
        has_remote=has_remote,
        is_merged=is_merged,
        unpushed_commits=unpushed_commits,
        uncommitted_changes=uncommitted_changes,
        insertions=insertions,
        deletions=deletions,
    )


def get_all_repos() -> list[tuple[str, Path]]:
    """Get all repos in the workspace."""
    root = get_gitwsp_root()
    repos_dir = root / "repos"
    if not repos_dir.exists():
        return []

    repos = []
    for repo_dir in repos_dir.iterdir():
        if repo_dir.is_dir() and (repo_dir / "trunk").exists():
            repos.append((repo_dir.name, repo_dir))
    return sorted(repos)


def get_repo_branches(repo_path: Path) -> list[BranchStatus]:
    """Get all branches for a repo with their status."""
    trunk_path = repo_path / "trunk"
    tree_branches_dir = repo_path / "tree_branches"

    if not tree_branches_dir.exists():
        return []

    branches = []
    for branch_dir in tree_branches_dir.iterdir():
        if branch_dir.is_dir() and (branch_dir / ".git").exists():
            status = get_branch_status(branch_dir, trunk_path, branch_dir.name)
            branches.append(status)

    return sorted(branches, key=lambda b: b.name)


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """Manage git worktrees with ease.

    \b
    Examples:
        gtwsp shell git@github.com:user/repo.git
        gtwsp shell git@github.com:user/repo.git feature-branch
    """
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument("repo")
@click.argument("branch", required=False)
def shell(repo: str, branch: str | None = None) -> None:
    """Open a shell in a git worktree.

    Clones the repo (if needed) and creates a worktree for the branch.
    Uses blobless clones for speed. Drops you into a shell in the worktree.

    \b
    REPO      Git URL (ssh or https)
    BRANCH    Branch name (default: repo's default branch)
    """
    root = get_gitwsp_root()
    repo_id = extract_repo_id(repo)
    repo_path = root / "repos" / repo_id

    trunk_path = repo_path / "trunk"
    ensure_base_repo(repo, trunk_path)

    # Determine branch
    if branch is None:
        branch = get_default_branch(trunk_path)

    tree_path = repo_path / "tree_branches" / branch
    ensure_worktree(trunk_path, tree_path, branch)

    # Print summary
    click.echo("")
    click.echo(f"Trunk:  {trunk_path}")
    click.echo(f"Tree:   {tree_path}")
    click.echo(f"Branch: {branch}")
    click.echo("")

    # Change to worktree directory and exec shell
    os.chdir(tree_path)
    user_shell = os.environ.get("SHELL", "/bin/sh")
    os.execvp(user_shell, [user_shell])


@main.command("list")
def list_cmd() -> None:
    """List all worktrees with their status.

    \b
    Status indicators:
      [merged]     Branch has been merged into default branch
      [+N]         N unpushed commits
      [~N +X -Y]   N lines changed (X insertions, Y deletions)
      [no remote]  No remote branch exists
    """
    repos = get_all_repos()

    if not repos:
        click.echo("No repositories found.")
        click.echo(f"Workspace root: {get_gitwsp_root()}")
        return

    for repo_name, repo_path in repos:
        branches = get_repo_branches(repo_path)
        if not branches:
            continue

        click.echo(f"\n{repo_name}")

        for i, branch in enumerate(branches):
            is_last = i == len(branches) - 1
            prefix = "  └── " if is_last else "  ├── "

            # Build status indicators
            status_parts = []

            if branch.is_merged:
                status_parts.append(click.style("merged", fg="green"))

            if branch.unpushed_commits > 0:
                status_parts.append(click.style(f"+{branch.unpushed_commits} unpushed", fg="yellow"))

            if branch.uncommitted_changes > 0:
                changes = f"~{branch.uncommitted_changes} (+{branch.insertions} -{branch.deletions})"
                status_parts.append(click.style(changes, fg="red"))

            if not branch.has_remote:
                status_parts.append(click.style("no remote", fg="cyan"))

            status_str = f" [{', '.join(status_parts)}]" if status_parts else ""

            # Show checkmark if safe to clean
            clean_indicator = click.style(" *", fg="green") if branch.is_safe_to_clean else ""

            click.echo(f"{prefix}{branch.name}{status_str}{clean_indicator}")

    click.echo("")
    click.echo(click.style("  * ", fg="green") + "= safe to clean (has remote, no unpushed commits, no uncommitted changes)")


@main.command()
@click.option("--dry-run", "-n", is_flag=True, help="Show what would be cleaned without doing it")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
def clean(dry_run: bool, force: bool) -> None:
    """Remove worktrees that are safe to clean.

    A worktree is safe to clean if:
      - It has a remote branch (state is preserved externally)
      - It has no unpushed commits
      - It has no uncommitted changes
    """
    repos = get_all_repos()
    to_clean: list[BranchStatus] = []

    for _repo_name, repo_path in repos:
        branches = get_repo_branches(repo_path)
        for branch in branches:
            if branch.is_safe_to_clean:
                to_clean.append(branch)

    if not to_clean:
        click.echo("Nothing to clean. All worktrees have unpushed work or no remote.")
        return

    click.echo("Worktrees to clean:")
    for branch in to_clean:
        click.echo(f"  - {branch.path}")

    if dry_run:
        click.echo(f"\nWould remove {len(to_clean)} worktree(s).")
        return

    if not force:
        click.confirm(f"\nRemove {len(to_clean)} worktree(s)?", abort=True)

    trunk_paths: dict[Path, Path] = {}
    for branch in to_clean:
        repo_path = branch.path.parent.parent
        trunk_paths[branch.path] = repo_path / "trunk"

    for branch in to_clean:
        trunk_path = trunk_paths[branch.path]
        click.echo(f"Removing {branch.name}...", nl=False)

        # Remove worktree via git
        subprocess.run(
            ["git", "worktree", "remove", str(branch.path)],
            cwd=trunk_path,
            capture_output=True,
        )

        # Also delete local branch
        subprocess.run(
            ["git", "branch", "-d", branch.name],
            cwd=trunk_path,
            capture_output=True,
        )

        click.echo(" done")

    click.echo(f"\nCleaned {len(to_clean)} worktree(s).")


if __name__ == "__main__":
    main()
