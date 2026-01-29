from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from grv.cli import main
from grv.menu import MenuAction
from grv.status import BranchInfo, BranchStatus
from grv.constants import WORKTREES_DIR


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

    def test_shell_local_with_branch(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        repo_root = tmp_path / "current"
        tree_path = tmp_path / WORKTREES_DIR / repo_root.name / "feature"
        with (
            patch("grv.cli.get_repo_root", return_value=repo_root),
            patch("grv.cli.is_worktree_registered", return_value=False),
            patch("grv.cli.branch_exists_locally", return_value=True),
            patch("grv.cli.run_git") as mock_run,
            patch("os.chdir"),
            patch("os.execvp"),
        ):
            result = runner.invoke(main, ["shell", "--local", "feature"])
            assert "Branch: feature" in result.output
            mock_run.assert_called_once_with(
                "worktree", "add", str(tree_path), "feature", cwd=repo_root
            )

    def test_shell_local_without_branch(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        repo_root = tmp_path / "current"
        tree_path = tmp_path / WORKTREES_DIR / repo_root.name / "main"
        with (
            patch("grv.cli.get_repo_root", return_value=repo_root),
            patch("grv.cli.get_current_branch", return_value="main"),
            patch("grv.cli.is_worktree_registered", return_value=False),
            patch("grv.cli.branch_exists_locally", return_value=True),
            patch("grv.cli.run_git") as mock_run,
            patch("os.chdir"),
            patch("os.execvp"),
        ):
            result = runner.invoke(main, ["shell", "--local"])
            assert "Branch: main" in result.output
            mock_run.assert_called_once_with(
                "worktree", "add", str(tree_path), "main", cwd=repo_root
            )

    def test_shell_local_creates_new_branch_when_missing(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        repo_root = tmp_path / "current"
        tree_path = tmp_path / WORKTREES_DIR / repo_root.name / "feature"
        with (
            patch("grv.cli.get_repo_root", return_value=repo_root),
            patch("grv.cli.is_worktree_registered", return_value=False),
            patch("grv.cli.branch_exists_locally", return_value=False),
            patch("grv.cli.run_git") as mock_run,
            patch("os.chdir"),
            patch("os.execvp"),
        ):
            result = runner.invoke(main, ["shell", "--local", "feature"])
            assert "Branch: feature" in result.output
            mock_run.assert_called_once_with(
                "worktree", "add", "-b", "feature", str(tree_path), cwd=repo_root
            )

    def test_shell_local_reuses_existing(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        repo_root = tmp_path / "current"
        with (
            patch("grv.cli.get_repo_root", return_value=repo_root),
            patch("grv.cli.is_worktree_registered", return_value=True),
            patch("grv.cli.run_git") as mock_run,
            patch("os.chdir"),
            patch("os.execvp"),
        ):
            result = runner.invoke(main, ["shell", "--local", "feature"])
            assert "Branch: feature" in result.output
            mock_run.assert_not_called()

    def test_shell_local_not_in_repo(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from subprocess import CalledProcessError

        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        with (
            patch(
                "grv.cli.get_repo_root",
                side_effect=CalledProcessError(128, ["git"]),
            ),
            patch("os.chdir"),
            patch("os.execvp"),
        ):
            result = runner.invoke(main, ["shell", "--local", "feature"])
            assert result.exit_code != 0

    def test_shell_without_repo_arg_fails(
        self, runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        result = runner.invoke(main, ["shell"])
        assert result.exit_code == 1
        assert "REPO argument required" in result.output


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
