from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from grv.cli import main
from grv.menu import MenuAction
from grv.status import BranchInfo, BranchStatus


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


class TestMain:
    def test_no_command_shows_help(self, runner: CliRunner) -> None:
        result = runner.invoke(main)
        assert result.exit_code == 0
        assert "Manage git worktrees" in result.output

    def test_help_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "shell" in result.output


class TestShell:
    def test_shell_creates_worktree(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        with (
            patch("grv.cli.ensure_base_repo"),
            patch("grv.cli.ensure_worktree"),
            patch("grv.cli.get_default_branch", return_value="main"),
            patch("os.chdir"),
            patch("os.execvp"),
        ):
            tree_path = (
                tmp_path / "repos" / "github_com_user_repo" / "tree_branches" / "main"
            )
            tree_path.mkdir(parents=True)
            result = runner.invoke(main, ["shell", "https://github.com/user/repo.git"])
            assert "Branch: main" in result.output

    def test_shell_with_branch(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        with (
            patch("grv.cli.ensure_base_repo"),
            patch("grv.cli.ensure_worktree"),
            patch("os.chdir"),
            patch("os.execvp"),
        ):
            tree_path = (
                tmp_path
                / "repos"
                / "github_com_user_repo"
                / "tree_branches"
                / "feature"
            )
            tree_path.mkdir(parents=True)
            result = runner.invoke(
                main, ["shell", "https://github.com/user/repo.git", "feature"]
            )
            assert "Branch: feature" in result.output

    def test_shell_with_from_branch(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        with (
            patch("grv.cli.ensure_base_repo"),
            patch("grv.cli.ensure_worktree") as mock_ensure_worktree,
            patch("os.chdir"),
            patch("os.execvp"),
        ):
            tree_path = (
                tmp_path
                / "repos"
                / "github_com_user_repo"
                / "tree_branches"
                / "feature"
            )
            tree_path.mkdir(parents=True)
            result = runner.invoke(
                main,
                [
                    "shell",
                    "https://github.com/user/repo.git",
                    "feature",
                    "--from",
                    "develop",
                ],
            )
            assert "Branch: feature" in result.output
            mock_ensure_worktree.assert_called_once()
            call_kwargs = mock_ensure_worktree.call_args
            assert call_kwargs.kwargs.get("from_branch") == "develop"


class TestList:
    def test_list_no_repos(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        result = runner.invoke(main, ["list"])
        assert "No repositories found" in result.output

    def test_list_selects_branch(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", tmp_path)]),
            patch(
                "grv.menu.interactive_select",
                return_value=(tmp_path / "main", "main", MenuAction.SHELL),
            ),
            patch("grv.menu.shell_into") as mock_shell,
        ):
            runner.invoke(main, ["list"])
            mock_shell.assert_called_once_with(tmp_path / "main", "main")

    def test_list_cancelled(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", tmp_path)]),
            patch("grv.menu.interactive_select", return_value=None),
            patch("grv.menu.shell_into") as mock_shell,
        ):
            runner.invoke(main, ["list"])
            mock_shell.assert_not_called()

    def test_list_clean_action_safe_removes_empty_repo(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        repo_path = tmp_path / "repo"
        branch_path = repo_path / "tree_branches" / "feature"
        branch_path.mkdir(parents=True)
        (repo_path / "trunk").mkdir(parents=True)
        safe_status = BranchStatus(
            name="feature",
            path=branch_path,
            has_remote=True,
            is_merged=True,
            unpushed_commits=0,
            uncommitted_changes=0,
            insertions=0,
            deletions=0,
        )
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", repo_path)]),
            patch(
                "grv.menu.interactive_select",
                return_value=(branch_path, "feature", MenuAction.CLEAN),
            ),
            patch("grv.cli.get_branch_status", return_value=safe_status),
            patch("grv.cli.get_repo_branches_fast", return_value=[]),
            patch("subprocess.run"),
        ):
            result = runner.invoke(main, ["list"])
            assert "Cleaning 'feature'" in result.output
            assert "Removing empty repo" in result.output
            assert "Done" in result.output

    def test_list_clean_action_safe_keeps_nonempty_repo(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        repo_path = tmp_path / "repo"
        branch_path = repo_path / "tree_branches" / "feature"
        branch_path.mkdir(parents=True)
        (repo_path / "trunk").mkdir(parents=True)
        safe_status = BranchStatus(
            name="feature",
            path=branch_path,
            has_remote=True,
            is_merged=True,
            unpushed_commits=0,
            uncommitted_changes=0,
            insertions=0,
            deletions=0,
        )
        other_path = repo_path / "tree_branches" / "other"
        other_branch = BranchInfo(name="other", path=other_path)
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", repo_path)]),
            patch(
                "grv.menu.interactive_select",
                return_value=(branch_path, "feature", MenuAction.CLEAN),
            ),
            patch("grv.cli.get_branch_status", return_value=safe_status),
            patch("grv.cli.get_repo_branches_fast", return_value=[other_branch]),
            patch("subprocess.run"),
        ):
            result = runner.invoke(main, ["list"])
            assert "Cleaning 'feature'" in result.output
            assert "Removing empty repo" not in result.output
            assert "Done" in result.output

    def test_list_clean_action_unsafe_no_remote(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        repo_path = tmp_path / "repo"
        branch_path = repo_path / "tree_branches" / "feature"
        branch_path.mkdir(parents=True)
        (repo_path / "trunk").mkdir(parents=True)
        unsafe_status = BranchStatus(
            name="feature",
            path=branch_path,
            has_remote=False,
            is_merged=False,
            unpushed_commits=0,
            uncommitted_changes=0,
            insertions=0,
            deletions=0,
        )
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", repo_path)]),
            patch(
                "grv.menu.interactive_select",
                return_value=(branch_path, "feature", MenuAction.CLEAN),
            ),
            patch("grv.cli.get_branch_status", return_value=unsafe_status),
        ):
            result = runner.invoke(main, ["list"])
            assert "Cannot clean 'feature'" in result.output
            assert "No remote branch found" in result.output

    def test_list_clean_action_unsafe_unpushed(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        repo_path = tmp_path / "repo"
        branch_path = repo_path / "tree_branches" / "feature"
        branch_path.mkdir(parents=True)
        (repo_path / "trunk").mkdir(parents=True)
        unsafe_status = BranchStatus(
            name="feature",
            path=branch_path,
            has_remote=True,
            is_merged=False,
            unpushed_commits=2,
            uncommitted_changes=0,
            insertions=0,
            deletions=0,
        )
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", repo_path)]),
            patch(
                "grv.menu.interactive_select",
                return_value=(branch_path, "feature", MenuAction.CLEAN),
            ),
            patch("grv.cli.get_branch_status", return_value=unsafe_status),
        ):
            result = runner.invoke(main, ["list"])
            assert "Cannot clean 'feature'" in result.output
            assert "2 unpushed commit(s)" in result.output

    def test_list_clean_action_unsafe_uncommitted(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        repo_path = tmp_path / "repo"
        branch_path = repo_path / "tree_branches" / "feature"
        branch_path.mkdir(parents=True)
        (repo_path / "trunk").mkdir(parents=True)
        unsafe_status = BranchStatus(
            name="feature",
            path=branch_path,
            has_remote=True,
            is_merged=False,
            unpushed_commits=0,
            uncommitted_changes=5,
            insertions=3,
            deletions=2,
        )
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", repo_path)]),
            patch(
                "grv.menu.interactive_select",
                return_value=(branch_path, "feature", MenuAction.CLEAN),
            ),
            patch("grv.cli.get_branch_status", return_value=unsafe_status),
        ):
            result = runner.invoke(main, ["list"])
            assert "Cannot clean 'feature'" in result.output
            assert "5 uncommitted changes" in result.output

    def test_list_delete_action_confirmed(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        repo_path = tmp_path / "repo"
        branch_path = repo_path / "tree_branches" / "feature"
        branch_path.mkdir(parents=True)
        (repo_path / "trunk").mkdir(parents=True)
        unsafe_status = BranchStatus(
            name="feature",
            path=branch_path,
            has_remote=False,
            is_merged=False,
            unpushed_commits=1,
            uncommitted_changes=0,
            insertions=0,
            deletions=0,
        )
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", repo_path)]),
            patch(
                "grv.menu.interactive_select",
                return_value=(branch_path, "feature", MenuAction.DELETE),
            ),
            patch("grv.cli.get_branch_status", return_value=unsafe_status),
            patch("grv.cli.get_repo_branches_fast", return_value=[]),
            patch("subprocess.run"),
        ):
            result = runner.invoke(main, ["list"], input="y\n")
            assert "Force deleting 'feature'" in result.output
            assert "Done" in result.output

    def test_list_delete_action_declined(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        repo_path = tmp_path / "repo"
        branch_path = repo_path / "tree_branches" / "feature"
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", repo_path)]),
            patch(
                "grv.menu.interactive_select",
                return_value=(branch_path, "feature", MenuAction.DELETE),
            ),
        ):
            result = runner.invoke(main, ["list"], input="n\n")
            assert "Force deleting" not in result.output


class TestClean:
    def test_clean_no_repos(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        result = runner.invoke(main, ["clean"])
        assert "No repositories to scan" in result.output

    def test_clean_no_branches(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", tmp_path)]),
            patch("grv.cli.get_repo_branches_fast", return_value=[]),
        ):
            result = runner.invoke(main, ["clean"])
            assert "No branches to scan" in result.output

    def test_clean_nothing_to_clean(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        branch_info = BranchInfo(name="feature", path=tmp_path / "feature")
        unsafe_status = BranchStatus(
            name="feature",
            path=tmp_path / "feature",
            has_remote=False,
            is_merged=False,
            unpushed_commits=1,
            uncommitted_changes=0,
            insertions=0,
            deletions=0,
        )
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", tmp_path)]),
            patch("grv.cli.get_repo_branches_fast", return_value=[branch_info]),
            patch("grv.cli.get_branch_status", return_value=unsafe_status),
        ):
            result = runner.invoke(main, ["clean"])
            assert "Nothing to clean" in result.output

    def test_clean_dry_run(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        branch_info = BranchInfo(name="feature", path=tmp_path / "feature")
        safe_status = BranchStatus(
            name="feature",
            path=tmp_path / "feature",
            has_remote=True,
            is_merged=True,
            unpushed_commits=0,
            uncommitted_changes=0,
            insertions=0,
            deletions=0,
        )
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", tmp_path)]),
            patch("grv.cli.get_repo_branches_fast", return_value=[branch_info]),
            patch("grv.cli.get_branch_status", return_value=safe_status),
        ):
            result = runner.invoke(main, ["clean", "--dry-run"])
            assert "Would remove 1 worktree" in result.output

    def test_clean_with_force(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        repo_path = tmp_path / "repo"
        trunk = repo_path / "trunk"
        trunk.mkdir(parents=True)
        branch_path = repo_path / "tree_branches" / "feature"
        branch_info = BranchInfo(name="feature", path=branch_path)
        safe_status = BranchStatus(
            name="feature",
            path=branch_path,
            has_remote=True,
            is_merged=True,
            unpushed_commits=0,
            uncommitted_changes=0,
            insertions=0,
            deletions=0,
        )
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", repo_path)]),
            patch("grv.cli.get_repo_branches_fast", return_value=[branch_info]),
            patch("grv.cli.get_branch_status", return_value=safe_status),
            patch("subprocess.run"),
        ):
            result = runner.invoke(main, ["clean", "--force"])
            assert "Cleaned 1 worktree" in result.output

    def test_clean_abort(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        branch_info = BranchInfo(name="feature", path=tmp_path / "feature")
        safe_status = BranchStatus(
            name="feature",
            path=tmp_path / "feature",
            has_remote=True,
            is_merged=True,
            unpushed_commits=0,
            uncommitted_changes=0,
            insertions=0,
            deletions=0,
        )
        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", tmp_path)]),
            patch("grv.cli.get_repo_branches_fast", return_value=[branch_info]),
            patch("grv.cli.get_branch_status", return_value=safe_status),
        ):
            result = runner.invoke(main, ["clean"], input="n\n")
            assert result.exit_code == 1

    def test_clean_filters_unsafe_branches(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        clean_info = BranchInfo(name="cleanable", path=tmp_path / "cleanable")
        dirty_info = BranchInfo(name="dirty", path=tmp_path / "dirty")
        clean_status = BranchStatus(
            name="cleanable",
            path=tmp_path / "cleanable",
            has_remote=True,
            is_merged=True,
            unpushed_commits=0,
            uncommitted_changes=0,
            insertions=0,
            deletions=0,
        )
        dirty_status = BranchStatus(
            name="dirty",
            path=tmp_path / "dirty",
            has_remote=False,
            is_merged=True,
            unpushed_commits=0,
            uncommitted_changes=0,
            insertions=0,
            deletions=0,
        )

        def mock_status(_path: Path, _trunk: Path, name: str) -> BranchStatus:
            return clean_status if name == "cleanable" else dirty_status

        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", tmp_path)]),
            patch(
                "grv.cli.get_repo_branches_fast",
                return_value=[clean_info, dirty_info],
            ),
            patch("grv.cli.get_branch_status", side_effect=mock_status),
        ):
            result = runner.invoke(main, ["clean", "--dry-run"])
            assert "cleanable" in result.output
            assert "dirty" not in result.output
            assert "Would remove 1 worktree" in result.output

    def test_clean_removes_empty_repo(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        repo_path = tmp_path / "repo"
        trunk = repo_path / "trunk"
        trunk.mkdir(parents=True)
        branch_path = repo_path / "tree_branches" / "feature"
        branch_path.mkdir(parents=True)
        branch_info = BranchInfo(name="feature", path=branch_path)
        safe_status = BranchStatus(
            name="feature",
            path=branch_path,
            has_remote=True,
            is_merged=True,
            unpushed_commits=0,
            uncommitted_changes=0,
            insertions=0,
            deletions=0,
        )
        call_count = [0]

        def mock_branches_fast(_path: Path) -> list[BranchInfo]:
            call_count[0] += 1
            return [branch_info] if call_count[0] == 1 else []

        with (
            patch("grv.cli.get_all_repos", return_value=[("repo", repo_path)]),
            patch("grv.cli.get_repo_branches_fast", side_effect=mock_branches_fast),
            patch("grv.cli.get_branch_status", return_value=safe_status),
            patch("subprocess.run"),
        ):
            result = runner.invoke(main, ["clean", "--force"])
            assert "Cleaned 1 worktree" in result.output
            assert "1 empty repo" in result.output
            assert not repo_path.exists()


class TestShellWithPrUrl:
    """
    Requirement: Accept GitHub PR URLs as alternative to repo + branch
    Interface: CLI stdout (terminal output)
    """

    def test_shell_with_pr_url_resolves_and_enters(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given: User passes a GitHub PR URL
        When: grv shell is invoked
        Then: Output shows "Resolving PR..." and resolved branch info
        """
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        tree_path = (
            tmp_path
            / "repos"
            / "github_com_owner_repo"
            / "tree_branches"
            / "feature-branch"
        )
        tree_path.mkdir(parents=True)

        with (
            patch("grv.cli.is_pr_url", return_value=True),
            patch(
                "grv.cli.resolve_pr",
                return_value=type(
                    "PRInfo",
                    (),
                    {
                        "repo_url": "https://github.com/owner/repo",
                        "branch": "feature-branch",
                    },
                )(),
            ),
            patch("grv.cli.ensure_base_repo"),
            patch("grv.cli.ensure_worktree"),
            patch("os.chdir"),
            patch("os.execvp"),
        ):
            result = runner.invoke(
                main, ["shell", "https://github.com/owner/repo/pull/42"]
            )
            assert "Resolving PR" in result.output
            assert "Branch: feature-branch" in result.output

    def test_shell_with_pr_url_and_branch_arg_errors(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given: User passes both a PR URL and a branch argument
        When: grv shell is invoked
        Then: Error message is shown
        """
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))

        with patch("grv.cli.is_pr_url", return_value=True):
            result = runner.invoke(
                main, ["shell", "https://github.com/owner/repo/pull/42", "some-branch"]
            )
            assert result.exit_code != 0
            assert "Cannot specify branch" in result.output

    def test_shell_with_pr_url_respects_from_option(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given: User passes a PR URL with --from option
        When: grv shell is invoked
        Then: The --from option is passed to ensure_worktree
        """
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        tree_path = (
            tmp_path
            / "repos"
            / "github_com_owner_repo"
            / "tree_branches"
            / "feature-branch"
        )
        tree_path.mkdir(parents=True)

        with (
            patch("grv.cli.is_pr_url", return_value=True),
            patch(
                "grv.cli.resolve_pr",
                return_value=type(
                    "PRInfo",
                    (),
                    {
                        "repo_url": "https://github.com/owner/repo",
                        "branch": "feature-branch",
                    },
                )(),
            ),
            patch("grv.cli.ensure_base_repo"),
            patch("grv.cli.ensure_worktree") as mock_ensure_worktree,
            patch("os.chdir"),
            patch("os.execvp"),
        ):
            runner.invoke(
                main,
                ["shell", "https://github.com/owner/repo/pull/42", "--from", "develop"],
            )
            mock_ensure_worktree.assert_called_once()
            call_kwargs = mock_ensure_worktree.call_args
            assert call_kwargs.kwargs.get("from_branch") == "develop"

    def test_shell_with_pr_url_resolution_error(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given: PR URL resolution fails (e.g., gh not installed)
        When: grv shell is invoked
        Then: Error message is displayed
        """
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))

        with (
            patch("grv.cli.is_pr_url", return_value=True),
            patch(
                "grv.cli.resolve_pr",
                side_effect=RuntimeError(
                    "GitHub CLI (gh) is required. Install from https://cli.github.com"
                ),
            ),
        ):
            result = runner.invoke(
                main, ["shell", "https://github.com/owner/repo/pull/42"]
            )
            assert result.exit_code != 0
            assert "GitHub CLI (gh) is required" in result.output

    def test_shell_with_regular_repo_url_unchanged(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given: User passes a regular repo URL (not a PR URL)
        When: grv shell is invoked
        Then: Existing behavior is unchanged (no PR resolution)
        """
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        tree_path = (
            tmp_path / "repos" / "github_com_user_repo" / "tree_branches" / "main"
        )
        tree_path.mkdir(parents=True)

        with (
            patch("grv.cli.is_pr_url", return_value=False),
            patch("grv.cli.ensure_base_repo"),
            patch("grv.cli.ensure_worktree"),
            patch("grv.cli.get_default_branch", return_value="main"),
            patch("os.chdir"),
            patch("os.execvp"),
        ):
            result = runner.invoke(main, ["shell", "https://github.com/user/repo.git"])
            # Should NOT show "Resolving PR" message
            assert "Resolving PR" not in result.output
            assert "Branch: main" in result.output


class TestDir:
    """
    Requirement: Output worktree path to stdout for unix pipe composition
    Interface: CLI stdout (path only), stderr (progress), exit code
    """

    def test_dir_outputs_path_to_stdout(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given: User passes a repo URL
        When: grv dir is invoked
        Then: stdout contains only the absolute path, exit code 0
        """
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        tree_path = (
            tmp_path / "repos" / "github_com_user_repo" / "tree_branches" / "main"
        )
        tree_path.mkdir(parents=True)

        with (
            patch("grv.cli.is_pr_url", return_value=False),
            patch("grv.cli.ensure_base_repo"),
            patch("grv.cli.ensure_worktree"),
            patch("grv.cli.get_default_branch", return_value="main"),
        ):
            result = runner.invoke(main, ["dir", "https://github.com/user/repo.git"])
            assert result.exit_code == 0
            # stdout should be just the path (stripped)
            assert result.output.strip() == str(tree_path)

    def test_dir_with_branch(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given: User passes repo URL + branch
        When: grv dir is invoked
        Then: stdout contains path to that branch's worktree
        """
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        tree_path = (
            tmp_path / "repos" / "github_com_user_repo" / "tree_branches" / "feature"
        )
        tree_path.mkdir(parents=True)

        with (
            patch("grv.cli.is_pr_url", return_value=False),
            patch("grv.cli.ensure_base_repo"),
            patch("grv.cli.ensure_worktree"),
        ):
            result = runner.invoke(
                main, ["dir", "https://github.com/user/repo.git", "feature"]
            )
            assert result.exit_code == 0
            assert result.output.strip() == str(tree_path)

    def test_dir_with_from_option(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given: User passes --from option
        When: grv dir is invoked
        Then: --from is passed to ensure_worktree
        """
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        tree_path = (
            tmp_path / "repos" / "github_com_user_repo" / "tree_branches" / "feature"
        )
        tree_path.mkdir(parents=True)

        with (
            patch("grv.cli.is_pr_url", return_value=False),
            patch("grv.cli.ensure_base_repo"),
            patch("grv.cli.ensure_worktree") as mock_ensure_worktree,
        ):
            result = runner.invoke(
                main,
                [
                    "dir",
                    "https://github.com/user/repo.git",
                    "feature",
                    "--from",
                    "develop",
                ],
            )
            assert result.exit_code == 0
            mock_ensure_worktree.assert_called_once()
            call_kwargs = mock_ensure_worktree.call_args
            assert call_kwargs.kwargs.get("from_branch") == "develop"

    def test_dir_with_pr_url(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given: User passes a PR URL
        When: grv dir is invoked
        Then: PR is resolved, stdout contains path to PR branch (last line)
        """
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        tree_path = (
            tmp_path / "repos" / "github_com_owner_repo" / "tree_branches" / "pr-branch"
        )
        tree_path.mkdir(parents=True)

        with (
            patch("grv.cli.is_pr_url", return_value=True),
            patch(
                "grv.cli.resolve_pr",
                return_value=type(
                    "PRInfo",
                    (),
                    {
                        "repo_url": "https://github.com/owner/repo",
                        "branch": "pr-branch",
                    },
                )(),
            ),
            patch("grv.cli.ensure_base_repo"),
            patch("grv.cli.ensure_worktree"),
        ):
            result = runner.invoke(
                main, ["dir", "https://github.com/owner/repo/pull/42"]
            )
            assert result.exit_code == 0
            # Path is last line (progress to stderr, but CliRunner mixes them)
            assert result.output.strip().endswith(str(tree_path))

    def test_dir_pr_url_with_branch_arg_errors(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given: User passes both PR URL and branch argument
        When: grv dir is invoked
        Then: Error to stderr, non-zero exit
        """
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))

        with patch("grv.cli.is_pr_url", return_value=True):
            result = runner.invoke(
                main, ["dir", "https://github.com/owner/repo/pull/42", "some-branch"]
            )
            assert result.exit_code != 0
            assert "Cannot specify branch" in result.output

    def test_dir_pr_resolution_error(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given: PR resolution fails
        When: grv dir is invoked
        Then: Error message, non-zero exit, no path to stdout
        """
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))

        with (
            patch("grv.cli.is_pr_url", return_value=True),
            patch(
                "grv.cli.resolve_pr",
                side_effect=RuntimeError("GitHub CLI (gh) is required"),
            ),
        ):
            result = runner.invoke(
                main, ["dir", "https://github.com/owner/repo/pull/42"]
            )
            assert result.exit_code != 0
            assert "GitHub CLI (gh) is required" in result.output
            # Should not contain a path
            assert "tree_branches" not in result.output

    def test_dir_does_not_exec_shell(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Given: User runs grv dir
        When: Command completes
        Then: No shell is executed (os.execvp not called)
        """
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        tree_path = (
            tmp_path / "repos" / "github_com_user_repo" / "tree_branches" / "main"
        )
        tree_path.mkdir(parents=True)

        with (
            patch("grv.cli.is_pr_url", return_value=False),
            patch("grv.cli.ensure_base_repo"),
            patch("grv.cli.ensure_worktree"),
            patch("grv.cli.get_default_branch", return_value="main"),
            patch("os.execvp") as mock_execvp,
        ):
            runner.invoke(main, ["dir", "https://github.com/user/repo.git"])
            mock_execvp.assert_not_called()
