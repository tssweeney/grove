# Agent Guidelines

## Development Requirements

**TDD with 100% coverage is mandatory.** Write tests first, then implementation. The CI will fail if coverage drops below 100%.

**All files must be under 150 lines.** Split into modules when approaching the limit. Add `# loc-skip` as the first line only if absolutely necessary.

## Commands

```bash
uv run pytest                       # Tests (must pass, 100% coverage)
uv run ruff format .                # Format
uv run ruff check .                 # Lint
uv run mypy src/grv                 # Type check
uv run python scripts/check_loc.py  # Line count check
uv run vulture src/grv              # Unused symbols
```

Run all before committing.

## Architecture

- `constants.py` - All magic strings/numbers as named constants
- `config.py` - Configuration and repo ID extraction
- `git.py` - Git operations (clone, worktree, etc.)
- `status.py` - Branch status detection
- `cli.py` - Click commands only

Keep modules focused. CLI should be thin, delegating to other modules.

## Testing

- Mock all git/subprocess calls
- Use `tmp_path` fixture for filesystem tests
- Use `monkeypatch.setenv` for environment variables
- Test edge cases (empty dirs, missing files, etc.)

## Style

- No unused imports or variables
- Type hints on all functions
- Minimal docstrings (code should be self-documenting)
- **No magic strings or numbers.** Define all constants at the top of the file or import from `constants.py`. The `PLR2004` lint rule enforces this for comparisons.
