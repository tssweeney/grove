from pathlib import Path
from unittest.mock import MagicMock, patch

from grv.git import (
    branch_exists_locally,
    ensure_base_repo,
    ensure_worktree,
    get_current_branch,
    get_default_branch,
    get_repo_root,
    is_worktree_registered,
    run_git,
)


class TestRunGit:
    def test_run_git_capture(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="output", returncode=0)
            run_git("status", cwd=tmp_path, capture=True)
            assert mock_run.called

    def test_run_git_no_capture(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            run_git("status", cwd=tmp_path, capture=False)
            assert mock_run.called


class TestGetDefaultBranch:
    def test_get_default_branch(self, tmp_path: Path) -> None:
        with patch("grv.git.run_git") as mock:
            mock.return_value = MagicMock(
                stdout="refs/remotes/origin/main\n", returncode=0
            )
            result = get_default_branch(tmp_path)
            assert result == "main"

    def test_get_default_branch_master(self, tmp_path: Path) -> None:
        with patch("grv.git.run_git") as mock:
            mock.return_value = MagicMock(
                stdout="refs/remotes/origin/master\n", returncode=0
            )
            result = get_default_branch(tmp_path)
            assert result == "master"


class TestBranchExistsLocally:
    def test_branch_exists(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=0)
            assert branch_exists_locally(tmp_path, "main") is True

    def test_branch_not_exists(self, tmp_path: Path) -> None:
        with patch("subprocess.run") as mock:
            mock.return_value = MagicMock(returncode=1)
            assert branch_exists_locally(tmp_path, "nonexistent") is False


class TestEnsureBaseRepo:
    def test_clone_new_repo(self, tmp_path: Path) -> None:
        base_path = tmp_path / "repo"
        with patch("grv.git.run_git") as mock_git:
            mock_git.return_value = MagicMock(
                stdout="refs/remotes/origin/main\n", returncode=0
            )
            ensure_base_repo("https://github.com/user/repo.git", base_path)
            calls = [str(c) for c in mock_git.call_args_list]
            assert any("clone" in c for c in calls)

    def test_update_existing_repo(self, tmp_path: Path) -> None:
        base_path = tmp_path / "repo"
        base_path.mkdir()
        with patch("grv.git.run_git") as mock_git:
            mock_git.return_value = MagicMock(
                stdout="refs/remotes/origin/main\n", returncode=0
            )
            ensure_base_repo("https://github.com/user/repo.git", base_path)
            calls = [str(c) for c in mock_git.call_args_list]
            assert any("fetch" in c for c in calls)


class TestEnsureWorktree:
    def test_worktree_exists(self, tmp_path: Path) -> None:
        tree_path = tmp_path / "tree"
        tree_path.mkdir()
        with patch("grv.git.run_git") as mock_git:
            ensure_worktree(tmp_path, tree_path, "feature")
            mock_git.assert_not_called()

    def test_create_worktree_local_branch(self, tmp_path: Path) -> None:
        base_path = tmp_path / "base"
        base_path.mkdir()
        tree_path = tmp_path / "tree"
        with (
            patch("grv.git.branch_exists_locally", return_value=True),
            patch("grv.git.run_git") as mock_git,
        ):
            ensure_worktree(base_path, tree_path, "feature")
            calls = [str(c) for c in mock_git.call_args_list]
            assert any("worktree" in c for c in calls)

    def test_create_worktree_remote_branch(self, tmp_path: Path) -> None:
        base_path = tmp_path / "base"
        base_path.mkdir()
        tree_path = tmp_path / "tree"
        with (
            patch("grv.git.branch_exists_locally", return_value=False),
            patch("grv.git.run_git") as mock_git,
        ):
            mock_git.return_value = MagicMock(
                stdout="abc123 refs/heads/feature\n", returncode=0
            )
            ensure_worktree(base_path, tree_path, "feature")

    def test_create_worktree_new_branch(self, tmp_path: Path) -> None:
        base_path = tmp_path / "base"
        base_path.mkdir()
        tree_path = tmp_path / "tree"
        with (
            patch("grv.git.branch_exists_locally", return_value=False),
            patch("grv.git.run_git") as mock_git,
            patch("grv.git.get_default_branch", return_value="main"),
        ):
            mock_git.return_value = MagicMock(stdout="", returncode=0)
            ensure_worktree(base_path, tree_path, "new-feature")


class TestGetRepoRoot:
    def test_returns_repo_root(self) -> None:
        with patch("grv.git.run_git") as mock_git:
            mock_git.return_value = MagicMock(stdout="/fake/repo\n")
            result = get_repo_root()
            assert result == Path("/fake/repo")

    def test_with_custom_cwd(self, tmp_path: Path) -> None:
        with patch("grv.git.run_git") as mock_git:
            mock_git.return_value = MagicMock(stdout="/other/repo\n")
            result = get_repo_root(tmp_path)
            assert result == Path("/other/repo")
            mock_git.assert_called_once()


class TestGetCurrentBranch:
    def test_returns_branch_name(self, tmp_path: Path) -> None:
        with patch("grv.git.run_git") as mock_git:
            mock_git.return_value = MagicMock(stdout="main\n")
            result = get_current_branch(tmp_path)
            assert result == "main"


class TestIsWorktreeRegistered:
    def test_worktree_is_registered(self, tmp_path: Path) -> None:
        tree_path = tmp_path / "worktree"
        with patch("grv.git.run_git") as mock_git:
            mock_git.return_value = MagicMock(
                stdout=f"worktree {tree_path}\nHEAD abcd1234\n\nworktree /other/path\n"
            )
            result = is_worktree_registered(tmp_path, tree_path)
            assert result is True

    def test_worktree_not_registered(self, tmp_path: Path) -> None:
        tree_path = tmp_path / "worktree"
        with patch("grv.git.run_git") as mock_git:
            mock_git.return_value = MagicMock(stdout="worktree /other/path\nHEAD abcd1234\n")
            result = is_worktree_registered(tmp_path, tree_path)
            assert result is False

    def test_worktree_with_empty_lines(self, tmp_path: Path) -> None:
        tree_path = tmp_path / "worktree"
        with patch("grv.git.run_git") as mock_git:
            mock_git.return_value = MagicMock(
                stdout=f"worktree {tree_path}\nHEAD abcd1234\n\nworktree /other/path\n"
            )
            result = is_worktree_registered(tmp_path, tree_path)
            assert result is True

    def test_worktree_not_found_with_empty_lines(self, tmp_path: Path) -> None:
        tree_path = tmp_path / "missing"
        with patch("grv.git.run_git") as mock_git:
            mock_git.return_value = MagicMock(
                stdout="worktree /first/path\nHEAD abcd1234\n\nworktree /second/path\n"
            )
            result = is_worktree_registered(tmp_path, tree_path)
            assert result is False
