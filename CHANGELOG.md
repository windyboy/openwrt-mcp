# Changelog

## [Unreleased]

### Security
- Write-path commands now hit the same metacharacter blocklist as reads.
  `uci set` values are allowlisted (`[A-Za-z0-9_.,:/@-]+`) before SSH.

### Docs
- CHANGELOG 4.0.0 and SECURITY: `starlette`/`uvicorn` remain
  transitive via FastMCP/`mcp`; not a slim-install option for servers.
- Install via `uv tool install` (frozen binary). Router env and audit
  under XDG (`~/.config/openwrt-mcp/env`, `~/.local/state/openwrt-mcp/`).
  MCP clients should exec `~/.config/openwrt-mcp/run`, not `uv run` in
  the git working tree.

### Changed
- Default `AUDIT_LOG_FILE` is `~/.local/state/openwrt-mcp/audit.log`.
- Default `OPENWRT_SSH_KEY` is `~/.ssh/openwrt_mcp_ed25519`.
  Docker-era `/app/log` and `/app/keys` defaults are gone.

## [4.0.0] — 2026-09-01

### Breaking
- **SSE / Health / REST sidecars removed.** `openwrt-mcp` speaks MCP over
  stdio only. `main()` takes no `--transport` flag and binds no ports.
- **Environment variables removed:** `MCP_TRANSPORT`, `MCP_SSE_PORT`,
  `HEALTH_PORT`, `REST_API_PORT`, `MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED`.
- **Direct dependencies dropped:** `starlette` and `uvicorn` are no
  longer listed in `pyproject.toml`. `fastmcp` still pulls them in
  transitively (`fastmcp` → `fastmcp-slim[server]` → `mcp` →
  `sse-starlette` / `starlette` / `uvicorn`). `openwrt-mcp` itself
  imports neither and binds no ports. There is no FastMCP extra that
  runs a stdio server without those packages.
- **Docker packaging deleted:** `Dockerfile` and `docker-compose.yml` are
  gone from the repo. The GHCR publish workflow is gone with them.

### Migration
- SSE / HTTP MCP clients should sit behind a stdio→HTTP bridge; this
  process no longer serves an HTTP MCP endpoint.
- Docker / compose users should drop those files and
  `uv tool install` the package, then run `openwrt-mcp` (or
  `~/.config/openwrt-mcp/run`) with SSH key and env on the host.
- systemd units that `ExecStart=` the old SSE daemon should be stopped
  and disabled; the MCP client should spawn the process on demand.

## [3.5.0] — 2026-09-01

### Feature: local-stdio MCP transport
- `openwrt-mcp --transport stdio` runs MCP over stdin/stdout. Single-user
  setups no longer need a long-running daemon or SSE port — the MCP client
  (opencode, Claude Desktop, …) owns the process lifecycle.
- `main()` gains an `--transport {stdio,sse}` CLI flag and a `MCP_TRANSPORT`
  env override. The health (9094) and REST (9096) servers are skipped in
  stdio mode.

### Security: SSH host-key verification (TOFU)
- New `OPENWRT_HOST_KEY_POLICY` env (`tofu`|`none`, default `tofu`).
- On first connect, the server's host key is pinned to
  `~/.config/openwrt-mcp/known_hosts` (mode `0600`). Subsequent connections
  are strictly verified; a key change is refused with a clear log line.
- Set `OPENWRT_KNOWN_HOSTS` to point at an existing known_hosts file for
  strict mode from the first connect.
- A clear `HOST KEY VERIFICATION FAILED` log replaces the previous silent
  error on mismatch.

### Security: hardened audit logging
- Audit failures (`OSError`) are now logged as a warning, never silently
  swallowed.
- Files rotate at 5 MB (`.log` → `.log.1`) on next append.

### Security: validator cleanup
- Removed unreachable `>` carve-out in `validate_command()`.
- Added explicit `\n` and `\r` to `DANGEROUS_METACHARACTERS` for clarity.

### Tests
- New `tests/unit/test_security_hardening.py` — 16 cases covering
  TOFU policy resolution, audit write/rotation/failure, known_hosts
  formatting, fingerprint, and the validator hardening.

## [1.2.1] — 2026-05-21

### Fixed — Standards Compliance (MCP Server Architect Standard v1.1.0)

- **G1** `reboot_device` reclassified from `WRITE` → `DESTRUCTIVE` with correct manifest:
  `idempotent=false`, `retryable=false`, `reversible=false`, `impact=service_outage`
- **G2** Request ID changed from module-level global to `contextvars.ContextVar`
  (prevents concurrent-invocation ID corruption in async handlers)
- **G3** `build_meta()` now reads `request_id` from context instead of generating a fresh UUID
- **G4** `sanitizer.py` — `sanitize_log_line()` redacts credentials and IPs from log output
- **G5** `sanitize_response_data()` integrated into `_success_response()` boundary
- **G6** `RequestIdFilter` + `SanitizingFormatter` logging pipeline; manual `[{get_request_id()}]`
  prefixing removed from `ssh_client.py`
- **G7** Risk Consistency Matrix test: `test_manifest_compliance.py`
- **G8** Health server (port 9094) now returns `tools` count and `tools_version`
- **G9** Version SSOT: `__init__.__version__` → imported by `observability.py`,
  `registration.py`, `server.py`
- **G10** `_log_audit()` now includes `request_id` for audit↔log correlation
- **G11** Smoke test: `test_response_contract.py` — contract verification for all 24 tools

### Added
- `_make_destructive_manifest()` factory (Canonical Template 5c) in `registration.py`
- `sanitizer.py` module — two trust boundaries (log lines vs response payloads)
- `test_manifest_compliance.py` — enforces Risk Consistency Matrix for all tools
- `test_response_contract.py` — smoke-level contract verification (`{"success": bool, ...}`)
- `test_sanitizer.py` — unit tests for log/response sanitization

### Changed
- `mock_mcp` fixture moved from test files to `conftest.py` (shared by all unit tests)
- `conftest.py` now exports `mock_mcp` fixture (removed duplicates from 2 test files)
- `server.py` — `setup_logging()` with `RequestIdFilter` + `SanitizingFormatter`

### Dependencies
- Bump `actions/checkout`: `@v4` → `@v6` (GitHub Actions)
- Bump `softprops/action-gh-release`: `@v2` → `@v3` (GitHub Actions)
- Bump `fastmcp`: `>=3.2.4,<4.0.0` → `>=3.3.1,<4.0.0`
- Bump `uvicorn`: `>=0.46.0` → `>=0.47.0`
- Bump `setuptools` (build-system): `>=68.0` → `>=82.0.1`
- Bump `mypy` (dev): `>=1.8.0` → `>=2.1.0`
- Bump `pytest-cov` (dev): `>=4.0.0` → `>=7.1.0`
- Bump `ruff` (dev): `>=0.4.0` → `>=0.15.13`
- Bump `bandit` (dev): `>=1.7.0` → `>=1.9.4`

### Metrics
- 296 tests (215 unit + 53 integration + 10 smoke + 18 e2e)
- 0 errors: ruff / mypy --strict / bandit -ll

### Post-Review Fixes (2026-05-21)
- **P0** `ci-cd-config.yaml`: fix `health_port` 9096 → 9094 (was REST API port)
- **P0** `pyproject.toml`: `requires-python` 3.13 → 3.14, ruff/mypy target updated to py314
- **P1** REST API `call_tool_endpoint`: set `request_id` context, apply sanitization, return `_meta`
- **P1** `_error_response()` variants: sanitize error messages (was asymmetric with success path)
- **P1** `server.py`: remove unused `_cache_lock` (declared but never acquired)
- **P1** `registration.py`: log exception on manifest failure instead of bare `pass`
- **P2** `Dockerfile`: non-root USER, audit log path `/app/log/` (was `/var/log/`)
- **P2** `dependabot.yml`: re-add Docker ecosystem for base image updates
- **P2** `constants.py`: `HEALTH_PORT` and `OPENWRT_KNOWN_HOSTS` env vars
- **P2** `test_response_contract.py`: reuse `conftest.py` `mock_mcp` fixture
- **P2** `.env.example`: remove `CODECOV_TOKEN` (CI-only), add `HEALTH_PORT`/`OPENWRT_KNOWN_HOSTS`
- **P2** `afds_config.yaml`: document `docs/meta` exclusion
- **P2** semgrep: 0 findings (307 rules, 111 files)

## [1.2.0] — 2026-05-12

### Added
- `get_router_context` — unified router context snapshot (system, wifi, DHCP, connectivity)
- `describe_router_capabilities` — server introspection with tool manifests
- `uci_set`, `uci_commit` — UCI write/commit tools (requires `ENABLE_WRITE_OPERATIONS=1`)
- `reboot_device` — router reboot (requires `ENABLE_WRITE_OPERATIONS=1`)
- `restart_interface` — restart network interface (requires `ENABLE_WRITE_OPERATIONS=1`)
- `reload_network` — reload network services (requires `ENABLE_WRITE_OPERATIONS=1`)
- `ping_host`, `traceroute_host`, `nslookup_host` — standalone network diagnostic tools
- `wifi_scan` — neighboring WiFi network survey
- `ENABLE_WRITE_OPERATIONS` environment variable (default: false)
- `SSHConnection.execute_write()` — separate write command validation path
- Write command validation in `SecurityValidator` (interface name, loopback protection)
- `_inject_risk_prefixes()` — dynamic risk prefix injection from manifest SSOT
- `UbusClient` — ubus JSON-RPC transport module
- `cat /proc/loadavg` added to allowed read-only patterns
- JSON Schema documentation (`schema/`)
- `RISKS_AND_CAVEATS` section in documentation (write tool risks, mock strategy)

### Changed
- Registered tools: `13` → `24`
- Writer module (`writer.py`) now uses `execute_write()` for all write operations
- Integration tests now skip when `OPENWRT_HOST` is not set
- `MCPWrapper` uses shared event loop for persistent SSH connections
- `.env` loaded from `conftest.py` for consistent env var injection
- Integration tests with real OpenWRT router added (19 READ tools)
- Mock integration tests for dangerous write tools added (10 tests)
- `timeout_seconds: int | None = None` → `int = SSH_TIMEOUT` for all I/O tools (fixes MCP SSE transport)
- `request_id` (UUID) included in SSH connection log lines for traceability
- `ci.yml`: integration tests accept exit code 5 (skip when OPENWRT_HOST not set)
- `ci.yml`: docker smoke tool count check `13` → `24`
- Docker base image: `python:3.13-slim` → `python:3.14-slim`
- fastmcp: `>=2.0.0,<3.0.0` → `>=3.2.4,<4.0.0`
- `server.py`: `get_all_tools()` supports FastMCP 3.x (lazy cache via `list_tools`)
- `ci.yml`: lint/test unified to Python 3.14, `--tb=short` → `--tb=long`

### Fixed
- `MCPWrapper._discover_tools()` — added 4th probe `list_tools()` for FastMCP 3.x compatibility
  (all 5 mocked write tool wrappers now discoverable on FastMCP 3.2.4 / Python 3.14)

### Removed
- Device registry (`db/` package and related tools) — out of scope

### Metrics
- Coverage: 86%
- 279 tests (200 unit + 53 integration + 8 smoke + 18 e2e)
- 0 errors: ruff / mypy --strict / bandit -ll

## [1.1.0] — 2026-05-11

### Changed
- Repository structure refactored: `openwrt_explorer.py` split into 4 modules under `tools/`
  (`ssh_client.py`, `explorer.py`, `registration.py`, `response_helpers.py`)
- `constants.py` moved to `tools/constants.py` as SSOT
- Python base image: `python:3.11-slim` → `python:3.13-slim`
- `requires-python` upgraded from `>=3.11` to `>=3.13`
- `ruff target-version`: `py311` → `py313`
- `mypy python_version`: `3.11` → `3.13`

### Added
- `timeout_seconds: int | None = None` parameter to all 13 I/O tools
- `@since v1.0.0` annotations in all tool docstrings
- `MCPWrapper` (Canonical Template 8 from mcp_standards.md) for integration tests
- Per-tool integration tests: 7 no-arg + 7 param + 3 invalid args
- `SSHConnection.cancel()` — cancellation signal for long-running operations
- `_meta` envelope (`request_id`, `duration_ms`, `tool_version`) on all 13 tools
- `server.py` unit tests with 60%+ coverage (no longer excluded from coverage)

### Fixed
- `SSHConnection.execute()`: timeout reset moved to `finally` block
- `_error_dict_extended` no longer wrapped as `success: true` by tool wrappers
- Duplicate MAC validation in `get_device_dhcp_details()` removed
- Dead `hours_back` parameter removed from `search_dhcp_logs()`
- `concurrent_safe` changed from `true` to `false` in manifests (TOCTOU race)
- `HEALTH_STATE` now protected by `threading.Lock`
- `mypy` and `bandit` in CI no longer suppressed with `|| true` — errors block pipeline
- Latency manifest for `test_router_connection`: `"fast"` → `"moderate"`
- `tool_version` in `observability.py`: hardcoded → `TOOLS_VERSION` constant
- Hardcoded fallback gateway `192.168.0.1` in `diagnose_router_connectivity` removed
- `MCP_UNSAFE_PUBLIC_ACCESS_CONFIRMED=1` added to Docker deployment (port forwarding)

### Dependencies
- Bump `asyncssh`: `>=2.13.0,<3.0.0` → `>=2.23.0,<3.0.0`
- Bump `starlette`: `>=0.27.0` → `>=1.0.0`
- Bump `uvicorn`: `>=0.22.0` → `>=0.46.0`
- Bump `pytest`: `>=7.0.0` → `>=9.0.3`
- Bump `pytest-asyncio`: `>=0.21.0` → `>=1.3.0`
- Bump `pytest-mock`: `>=3.10.0` → `>=3.15.1`
- Bump `docker/build-push-action`: `@v6` → `@v7`
- Bump `docker/metadata-action`: `@v5` → `@v6`
- Bump `docker/login-action`: `@v3` → `@v4`
- Bump `actions/setup-python`: `@v5` → `@v6`
- Bump `docker/setup-buildx-action`: `@v3` → `@v4`

### Metrics
- Coverage: 80.34% (server.py included — 60% coverage)
- 137 tests (115 unit + 22 integration)
- 0 errors: ruff / mypy --strict / bandit -ll
- Docker build: Python 3.13, ~25s

## [1.0.0] — 2026-05-11

### Added
- Initial release with 13 read-only MCP tools for OpenWRT
- SSH command whitelist security validator
- REST API on port 9096
- Health endpoint on port 9094
- MCP SSE transport on port 9095
- Extended L2+ error responses with structured codes
- Tool manifest generation with capability descriptors
- Per-tool observability (request_id, _meta envelope, counters)
- Docker deployment with docker compose
- CI pipeline with ruff, mypy, bandit, coverage enforcement (83%)
- Smoke and E2E test suites
