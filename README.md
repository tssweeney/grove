# grv

Git workspace manager using worktrees. Clone once, work on many branches simultaneously.

## The Problem

With LLM agents reshaping the software engineering workflow, a new pattern is emerging: **parallel feature development**. Instead of context-switching between branches, developers now spin up multiple workstreams simultaneously—one branch per agent, per experiment, per idea.

Git worktrees are the natural primitive for this workflow. But the standard `git worktree` flow has friction:

- You need the repo cloned locally first
- You have to decide where to put each worktree
- Worktrees scatter across your filesystem and get lost
- Cleanup is manual and error-prone

Meanwhile, countless tools are appearing daily—each bundling worktree management with CLI agents, dev containers, and other features. But sometimes you just want the primitive.

## The Solution

`grv` is an extremely minimalist worktree manager. Three commands:

```bash
grv shell <repo> [branch]  # Shell into a worktree (clones if needed)
grv list                    # Browse your worktrees
grv clean                   # Cleanup remotely-backed work
```

That's it. Use your favorite editor, CLI tools, whatever. But stay organized.

## Install

```bash
# Run directly (no install needed)
uvx grv [command]

# Or install globally
pip install grv
```

## Usage

```bash
# Open a shell in a worktree (clones repo if needed)
grv shell git@github.com:user/repo.git
grv shell git@github.com:user/repo.git feature-branch

# List all worktrees with status
grv list

# Clean up merged worktrees
grv clean
grv clean --dry-run
```

## How it works

`grv` manages git worktrees in `~/.grv/`:

```
~/.grv/repos/github_com_user_repo/
├── trunk/              # Base clone (blobless for speed)
└── tree_branches/
    ├── main/           # Worktree for main
    └── feature-branch/ # Worktree for feature-branch
```

Each branch gets its own directory. Switch between branches by switching directories.

## Commands

| Command | Description |
|---------|-------------|
| `shell REPO [BRANCH]` | Open shell in worktree |
| `list` | Show all worktrees with status |
| `clean` | Remove safe-to-clean worktrees |

## Configuration

Set `GRV_ROOT` to change the workspace location (default: `~/.grv`).

## License

MIT
