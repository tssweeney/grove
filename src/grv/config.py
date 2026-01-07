import os
from pathlib import Path
from urllib.parse import urlparse

from grv.constants import DEFAULT_GRV_ROOT, GIT_SSH_PREFIX, GIT_SUFFIX


def get_grv_root() -> Path:
    """Get the GRV_ROOT directory, defaulting to ~/.grv."""
    root = os.environ.get("GRV_ROOT", os.path.expanduser(DEFAULT_GRV_ROOT))
    return Path(root)


def extract_repo_id(repo: str) -> str:
    """Extract a unique repository identifier from a git URL.

    Returns a flat string like 'github_com_user_repo' that uniquely identifies
    the repository across different hosts and users.
    """
    if repo.startswith(GIT_SSH_PREFIX):
        host_and_path = repo[len(GIT_SSH_PREFIX) :]
        host, path = host_and_path.split(":", 1)
        path = path.rstrip("/").removesuffix(GIT_SUFFIX)
        raw_id = f"{host}/{path}"
    elif (parsed := urlparse(repo)).netloc:
        path = parsed.path.rstrip("/").removesuffix(GIT_SUFFIX).lstrip("/")
        raw_id = f"{parsed.netloc}/{path}"
    else:
        raw_id = repo.rstrip("/").removesuffix(GIT_SUFFIX).lstrip("/")

    return raw_id.replace(".", "_").replace("/", "_").replace(":", "_")
