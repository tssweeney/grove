"""Tests for PR URL detection and resolution.

Interface: grv.pr module functions
Consumer: CLI commands that need to resolve PR URLs to repo/branch
"""

from unittest.mock import MagicMock, patch

import pytest

from grv.pr import (
    is_pr_url,
    parse_pr_url,
    resolve_pr,
)


class TestIsPrUrl:
    """
    Requirement: Detect GitHub PR URLs vs regular repo URLs
    Interface: is_pr_url(url: str) -> bool
    """

    def test_https_github_pr_url_detected(self) -> None:
        """
        Given: A GitHub PR URL with https scheme
        When: is_pr_url is called
        Then: Returns True
        """
        assert is_pr_url("https://github.com/owner/repo/pull/123") is True

    def test_https_github_pr_url_with_fragment_detected(self) -> None:
        """
        Given: A GitHub PR URL with a fragment (e.g., #discussion_r123)
        When: is_pr_url is called
        Then: Returns True
        """
        assert (
            is_pr_url("https://github.com/owner/repo/pull/123#discussion_r456") is True
        )

    def test_schemeless_github_pr_url_detected(self) -> None:
        """
        Given: A GitHub PR URL without https:// scheme
        When: is_pr_url is called
        Then: Returns True
        """
        assert is_pr_url("github.com/owner/repo/pull/123") is True

    def test_https_repo_url_not_detected(self) -> None:
        """
        Given: A regular GitHub repo clone URL
        When: is_pr_url is called
        Then: Returns False
        """
        assert is_pr_url("https://github.com/owner/repo.git") is False
        assert is_pr_url("https://github.com/owner/repo") is False

    def test_ssh_repo_url_not_detected(self) -> None:
        """
        Given: An SSH git URL
        When: is_pr_url is called
        Then: Returns False
        """
        assert is_pr_url("git@github.com:owner/repo.git") is False

    def test_non_github_url_not_detected(self) -> None:
        """
        Given: A non-GitHub URL
        When: is_pr_url is called
        Then: Returns False
        """
        assert is_pr_url("https://gitlab.com/owner/repo/merge_requests/123") is False


class TestParsePrUrl:
    """
    Requirement: Extract owner, repo, and PR number from GitHub PR URLs
    Interface: parse_pr_url(url: str) -> tuple[str, str, int]
    """

    def test_parse_https_pr_url(self) -> None:
        """
        Given: A standard GitHub PR URL
        When: parse_pr_url is called
        Then: Returns (owner, repo, pr_number)
        """
        owner, repo, pr_num = parse_pr_url(
            "https://github.com/octocat/hello-world/pull/42"
        )
        assert owner == "octocat"
        assert repo == "hello-world"
        assert pr_num == 42

    def test_parse_pr_url_strips_fragment(self) -> None:
        """
        Given: A PR URL with fragment
        When: parse_pr_url is called
        Then: Fragment is ignored, correct values returned
        """
        owner, repo, pr_num = parse_pr_url(
            "https://github.com/owner/repo/pull/123#discussion_r456"
        )
        assert owner == "owner"
        assert repo == "repo"
        assert pr_num == 123

    def test_parse_schemeless_pr_url(self) -> None:
        """
        Given: A PR URL without https:// scheme
        When: parse_pr_url is called
        Then: Returns correct values
        """
        owner, repo, pr_num = parse_pr_url("github.com/owner/repo/pull/99")
        assert owner == "owner"
        assert repo == "repo"
        assert pr_num == 99

    def test_parse_invalid_url_raises(self) -> None:
        """
        Given: A URL that is not a valid PR URL
        When: parse_pr_url is called
        Then: Raises ValueError
        """
        with pytest.raises(ValueError, match="Invalid GitHub PR URL"):
            parse_pr_url("https://github.com/owner/repo")


class TestResolvePr:
    """
    Requirement: Resolve PR URL to repo URL and branch name using gh CLI
    Interface: resolve_pr(url: str) -> PRInfo
    """

    def test_resolve_pr_success(self) -> None:
        """
        Given: A valid PR URL and gh CLI available
        When: resolve_pr is called
        Then: Returns PRInfo with repo_url and branch
        """
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            '{"headRefName":"feature-branch",'
            '"headRepository":{"name":"repo"},'
            '"headRepositoryOwner":{"login":"owner"}}'
        )

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            info = resolve_pr("https://github.com/owner/repo/pull/42")

            assert info.repo_url == "https://github.com/owner/repo"
            assert info.branch == "feature-branch"
            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]
            assert "gh" in call_args
            assert "pr" in call_args
            assert "view" in call_args
            assert "https://github.com/owner/repo/pull/42" in call_args

    def test_resolve_pr_schemeless_url(self) -> None:
        """
        Given: A PR URL without https:// scheme
        When: resolve_pr is called
        Then: URL is normalized and resolved successfully
        """
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = (
            '{"headRefName":"my-branch",'
            '"headRepository":{"name":"repo"},'
            '"headRepositoryOwner":{"login":"owner"}}'
        )

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            info = resolve_pr("github.com/owner/repo/pull/99")

            assert info.branch == "my-branch"
            # URL should be normalized to include https://
            call_args = mock_run.call_args[0][0]
            assert "https://github.com/owner/repo/pull/99" in call_args

    def test_resolve_pr_gh_not_found(self) -> None:
        """
        Given: gh CLI is not installed
        When: resolve_pr is called
        Then: Raises RuntimeError with helpful message
        """
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            with pytest.raises(RuntimeError) as exc_info:
                resolve_pr("https://github.com/owner/repo/pull/42")

            assert "GitHub CLI (gh) is required" in str(exc_info.value)
            assert "https://cli.github.com" in str(exc_info.value)

    def test_resolve_pr_gh_error(self) -> None:
        """
        Given: gh CLI fails (e.g., PR not found, auth issue)
        When: resolve_pr is called
        Then: Raises RuntimeError with gh error message
        """
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Could not resolve to a PullRequest"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError) as exc_info:
                resolve_pr("https://github.com/owner/repo/pull/999")

            assert "Could not resolve to a PullRequest" in str(exc_info.value)

    def test_resolve_pr_invalid_json(self) -> None:
        """
        Given: gh CLI returns invalid JSON
        When: resolve_pr is called
        Then: Raises RuntimeError
        """
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not valid json"

        with patch("subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError) as exc_info:
                resolve_pr("https://github.com/owner/repo/pull/42")

            assert "Failed to parse" in str(exc_info.value)
