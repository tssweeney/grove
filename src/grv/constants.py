"""Constants for grv - no magic strings/numbers allowed elsewhere."""

# Directory names within GRV workspace
DEFAULT_GRV_ROOT = "~/.grv"
REPOS_DIR = "repos"
TRUNK_DIR = "trunk"
TREE_BRANCHES_DIR = "tree_branches"

# Git constants
GIT_DIR = ".git"
GIT_SUFFIX = ".git"
GIT_SSH_PREFIX = "git@"
GIT_REMOTE_NAME = "origin"
GIT_CLONE_FILTER = "--filter=blob:none"
GIT_REF_REMOTE_HEAD = "refs/remotes/origin/HEAD"
GIT_REF_HEADS_FMT = "refs/heads/{branch}"

# Shell environment
SHELL_ENV_VAR = "SHELL"
DEFAULT_SHELL = "/bin/sh"

# Tree display characters
TREE_LAST_ITEM = "└── "
TREE_ITEM = "├── "
TREE_LAST_INDENT = "    "
TREE_INDENT = "│   "
TREE_LAST_BRANCH = "└─"
TREE_BRANCH = "├─"

# Regex patterns for git diff parsing
INSERTION_PATTERN = r"(\d+) insertion"
DELETION_PATTERN = r"(\d+) deletion"

# Menu styling
MENU_CURSOR_STYLE = ("fg_cyan", "bold")

# GitHub PR URL patterns
GITHUB_PR_PATH_PATTERN = r"^/?([^/]+)/([^/]+)/pull/(\d+)"
GITHUB_HOST = "github.com"

# GitHub CLI
GH_CLI_INSTALL_URL = "https://cli.github.com"
GH_PR_JSON_FIELDS = "headRefName,headRepository,headRepositoryOwner"
GITHUB_REPO_URL_FMT = "https://github.com/{owner}/{repo}"

# Error messages
ERR_GH_NOT_FOUND = (
    "GitHub CLI (gh) is required for PR URLs. Install from https://cli.github.com"
)
ERR_INVALID_PR_URL = "Invalid GitHub PR URL"
ERR_PR_PARSE_FAILED = "Failed to parse gh output"
