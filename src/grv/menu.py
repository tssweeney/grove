import os
from enum import Enum
from pathlib import Path
from typing import Callable

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
from grv.status import (
    BranchInfo,
    FooterStatus,
    get_all_repos,
    get_footer_status,
    get_repo_branches_fast,
)


class MenuAction(Enum):
    """Actions that can be taken from the menu."""

    SHELL = "shell"
    CLEAN = "clean"
    DELETE = "delete"


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


def _format_status_bar(status: FooterStatus | None) -> str:
    """Format status bar with controls and git status."""
    controls = "(s/enter) Shell  (c) Clean  (d) Delete"

    if status is None:
        return controls

    # Build git status line
    parts = [f"base: {status.base_branch}"]

    if status.has_remote:
        parts.append("remote: yes")
    else:
        parts.append("remote: no")

    if status.unpushed > 0:
        parts.append(f"unpushed: {status.unpushed}")

    if status.uncommitted > 0:
        parts.append(f"uncommitted: +{status.insertions}/-{status.deletions}")

    if status.is_clean:
        parts.append("[clean]")

    git_status = "  ".join(parts)
    return f"{controls}\n{git_status}"


def _create_status_bar_callback(
    entries: list[tuple[str, BranchInfo | None]],
) -> Callable[[str], str]:
    """Create status bar callback that fetches git status for selected entry."""
    cache: dict[int, FooterStatus | None] = {}

    def callback(entry: str) -> str:
        # Find the index of this entry
        try:
            idx = next(i for i, (d, _) in enumerate(entries) if d == entry)
        except StopIteration:
            return _format_status_bar(None)

        # Check cache first
        if idx in cache:
            return _format_status_bar(cache[idx])

        branch = entries[idx][1]
        if branch is None:
            cache[idx] = None
            return _format_status_bar(None)

        # Fetch status (this is the expensive part)
        status = get_footer_status(branch)
        cache[idx] = status
        return _format_status_bar(status)

    return callback


def interactive_select() -> tuple[Path, str, MenuAction] | None:
    """Show interactive tree menu and return (branch_path, branch_name, action) or None."""
    entries = build_menu_entries()
    if not entries:
        return None

    display = [e[0] for e in entries]
    first_branch = next((i for i, e in enumerate(entries) if e[1] is not None), 0)
    title = f"grv workspace\n{get_grv_root()}\n"

    status_bar_callback = _create_status_bar_callback(entries)

    menu = TerminalMenu(
        display,
        title=title,
        cursor_index=first_branch,
        menu_cursor_style=MENU_CURSOR_STYLE,
        status_bar=status_bar_callback,
        accept_keys=("enter", "s", "c", "d"),
    )
    selected: int | None = menu.show()
    if selected is None:
        return None
    branch = entries[selected][1]
    if branch is None:
        return None  # Selected a repo header, ignore

    # Determine action based on key pressed
    key = menu.chosen_accept_key
    if key in ("enter", "s"):
        action = MenuAction.SHELL
    elif key == "c":
        action = MenuAction.CLEAN
    elif key == "d":
        action = MenuAction.DELETE
    else:
        action = MenuAction.SHELL

    return (branch.path, branch.name, action)


def shell_into(path: Path, branch_name: str) -> None:
    """Change to directory and exec shell with nice output."""
    click.secho("\nReady! Entering worktree shell...", fg="green", bold=True)
    click.echo(f"\n  Branch: {click.style(branch_name, fg='cyan', bold=True)}")
    click.echo(f"  Path:   {click.style(str(path), fg='blue')}\n")
    os.chdir(path)
    user_shell = os.environ.get(SHELL_ENV_VAR, DEFAULT_SHELL)
    os.execvp(user_shell, [user_shell])
