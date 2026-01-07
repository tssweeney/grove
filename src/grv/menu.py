import os
from pathlib import Path

import click
from simple_term_menu import TerminalMenu  # type: ignore[import-untyped]

from grv.config import get_grv_root
from grv.constants import (
    DEFAULT_SHELL,
    MENU_CURSOR_STYLE,
    SHELL_ENV_VAR,
    TREE_BRANCH,
    TREE_INDENT,
    TREE_ITEM,
    TREE_LAST_BRANCH,
    TREE_LAST_INDENT,
    TREE_LAST_ITEM,
)
from grv.status import BranchInfo, get_all_repos, get_repo_branches_fast


def build_menu_entries() -> list[tuple[str, BranchInfo | None]]:
    """Build menu entries: (display, branch_info). None = repo header."""
    entries: list[tuple[str, BranchInfo | None]] = []
    repos = [(n, p) for n, p in get_all_repos() if get_repo_branches_fast(p)]

    for ri, (repo_name, repo_path) in enumerate(repos):
        branches = get_repo_branches_fast(repo_path)
        is_last_repo = ri == len(repos) - 1
        repo_prefix = TREE_LAST_ITEM if is_last_repo else TREE_ITEM
        entries.append((f"{repo_prefix}{repo_name}", None))
        branch_indent = TREE_LAST_INDENT if is_last_repo else TREE_INDENT
        for bi, branch in enumerate(branches):
            is_last = bi == len(branches) - 1
            branch_prefix = TREE_LAST_BRANCH if is_last else TREE_BRANCH
            prefix = f"{branch_indent}{branch_prefix} "
            entries.append((f"{prefix}{branch.name}", branch))
    return entries


def interactive_select() -> tuple[Path, str] | None:
    """Show interactive tree menu and return (branch_path, branch_name) or None."""
    entries = build_menu_entries()
    if not entries:
        return None

    display = [e[0] for e in entries]
    first_branch = next((i for i, e in enumerate(entries) if e[1] is not None), 0)
    title = f"grv workspace\n{get_grv_root()}\n"
    menu = TerminalMenu(
        display,
        title=title,
        cursor_index=first_branch,
        menu_cursor_style=MENU_CURSOR_STYLE,
    )
    selected: int | None = menu.show()
    if selected is None:
        return None
    branch = entries[selected][1]
    if branch is None:
        return None  # Selected a repo header, ignore
    return (branch.path, branch.name)


def shell_into(path: Path, branch_name: str) -> None:
    """Change to directory and exec shell with nice output."""
    click.secho("\nReady! Entering worktree shell...", fg="green", bold=True)
    click.echo(f"\n  Branch: {click.style(branch_name, fg='cyan', bold=True)}")
    click.echo(f"  Path:   {click.style(str(path), fg='blue')}\n")
    os.chdir(path)
    user_shell = os.environ.get(SHELL_ENV_VAR, DEFAULT_SHELL)
    os.execvp(user_shell, [user_shell])
