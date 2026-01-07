# grove

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

`grove` is an extremely minimalist worktree manager. Three commands:

```bash
grove shell <repo> [branch]  # Shell into a worktree (clones if needed)
grove list                    # Browse your worktrees
grove clean                   # Cleanup remotely-backed work
```

That's it. Use your favorite editor, CLI tools, whatever. But stay organized.

## Install

> **Alpha**: Not yet published to PyPI.

```bash
uvx git+https://github.com/tssweeney/grove [commands]
```

## Usage

```bash
# Open a shell in a worktree (clones repo if needed)
grove shell git@github.com:user/repo.git
grove shell git@github.com:user/repo.git feature-branch

# List all worktrees with status
grove list

# Clean up merged worktrees
grove clean
grove clean --dry-run
```

## How it works

`grove` manages git worktrees in `~/.grove/`:

```
~/.grove/repos/github_com_user_repo/
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

Set `GROVE_ROOT` to change the workspace location (default: `~/.grove`).

## License

MIT
