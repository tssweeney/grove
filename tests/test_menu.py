from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from grv.menu import MenuAction, build_menu_entries, interactive_select
from grv.status import BranchInfo


class TestBuildMenuEntries:
    def test_builds_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        branch = BranchInfo(name="main", path=tmp_path / "main")
        with (
            patch("grv.menu.get_all_repos", return_value=[("repo", tmp_path)]),
            patch("grv.menu.get_repo_branches_fast", return_value=[branch]),
        ):
            entries = build_menu_entries()
            assert len(entries) == 2  # repo header + branch
            assert "repo" in entries[0][0]
            assert entries[0][1] is None  # repo header
            assert "main" in entries[1][0]
            assert entries[1][1] == branch

    def test_empty_repos(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        with patch("grv.menu.get_all_repos", return_value=[]):
            entries = build_menu_entries()
            assert entries == []

    def test_skips_repos_with_no_branches(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        with (
            patch("grv.menu.get_all_repos", return_value=[("repo", tmp_path)]),
            patch("grv.menu.get_repo_branches_fast", return_value=[]),
        ):
            entries = build_menu_entries()
            assert entries == []


class TestInteractiveSelect:
    def test_returns_none_when_no_entries(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        with patch("grv.menu.build_menu_entries", return_value=[]):
            result = interactive_select()
            assert result is None

    def test_returns_selected_path_and_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        branch = BranchInfo(name="main", path=tmp_path / "main")
        with (
            patch(
                "grv.menu.build_menu_entries",
                return_value=[
                    ("└── repo", None),
                    ("    └─ main", branch),
                ],
            ),
            patch("grv.menu.TerminalMenu") as mock_menu_class,
        ):
            mock_menu = MagicMock()
            mock_menu.show.return_value = 1  # Select the branch, not header
            mock_menu.chosen_accept_key = "enter"
            mock_menu_class.return_value = mock_menu
            result = interactive_select()
            assert result == (tmp_path / "main", "main", MenuAction.SHELL)

    def test_returns_none_when_cancelled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        branch = BranchInfo(name="main", path=tmp_path / "main")
        with (
            patch(
                "grv.menu.build_menu_entries",
                return_value=[
                    ("└── repo", None),
                    ("    └─ main", branch),
                ],
            ),
            patch("grv.menu.TerminalMenu") as mock_menu_class,
        ):
            mock_menu = MagicMock()
            mock_menu.show.return_value = None
            mock_menu_class.return_value = mock_menu
            result = interactive_select()
            assert result is None

    def test_returns_none_when_repo_header_selected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRV_ROOT", str(tmp_path))
        branch = BranchInfo(name="main", path=tmp_path / "main")
        with (
            patch(
                "grv.menu.build_menu_entries",
                return_value=[
                    ("└── repo", None),
                    ("    └─ main", branch),
                ],
            ),
            patch("grv.menu.TerminalMenu") as mock_menu_class,
        ):
            mock_menu = MagicMock()
            mock_menu.show.return_value = 0  # Select the repo header
            mock_menu_class.return_value = mock_menu
            result = interactive_select()
            assert result is None
