# Contributing

## Development setup

```bash
git clone <repo-url> openwrt-mcp
cd openwrt-mcp
uv sync --extra dev
```

## Run the test suite

```bash
uv run pytest tests/unit -q        # offline unit tests
uv run pytest tests/unit --cov=openwrt_mcp   # with coverage
uv run ruff check .                 # lint
uv run ruff format --check .       # format check
uv run mypy src/openwrt_mcp --strict   # type check
```

Real-router tests under `tests/integration/test_real_router.py` skip unless
`OPENWRT_HOST` is set to a non-placeholder and `OPENWRT_SSH_KEY` exists.
Use the same XDG env as the server (`~/.config/openwrt-mcp/env` or a
project `.env`). Write tools are never run against a live router; they are
mocked in `tests/unit/test_write_tools_mocked.py`.

## Running locally

For a live MCP client, install a frozen binary (`uv tool install .`) and
follow the XDG + wrapper steps in [`README.md`](README.md#install). Do
not point opencode at `uv run` inside this working tree.

To smoke-test stdio from a clone during development:

```bash
uv run openwrt-mcp
```

## Pull request checklist

- [ ] Tests added/updated for behavioural changes
- [ ] `ruff check` and `ruff format --check` clean
- [ ] `mypy --strict` clean for `src/openwrt_mcp/`
- [ ] CHANGELOG.md updated under "Unreleased"
- [ ] No secrets, real IPs, or audit logs in the diff

## Security disclosures

Please email security issues privately rather than opening a public issue.