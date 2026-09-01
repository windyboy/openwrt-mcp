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

Integration tests under `tests/integration/` require a real OpenWRT router and
are skipped by default — set `OPENWRT_INTEGRATION=1` and provide the same env
vars the server uses (`OPENWRT_HOST`, `OPENWRT_SSH_KEY`, ...).

## Running locally

```bash
# stdio — the MCP client owns the process
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