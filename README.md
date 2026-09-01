# openwrt-mcp

A read-only-by-default [Model Context Protocol](https://modelcontextprotocol.io/)
server for OpenWRT routers. Speaks to the router over SSH (key auth) with a
default-deny command allowlist, so even a prompt-injected agent can only
request operations that have been explicitly whitelisted.

```text
MCP client ──► openwrt-mcp ──► SSH ──► OpenWRT router
                (whitelist + audit + host-key pin)
```

## Features

- **Default-deny command allowlist** — every SSH command is matched against
  a strict, anchored regex allowlist before it leaves the box.
- **24 tools** — system info, WiFi status, DHCP leases, firewall rules,
  OpenThread (when present), UCI read, log search, package list, ping /
  traceroute / nslookup, WiFi scan.
- **Write tools gated by `ENABLE_WRITE_OPERATIONS=1`** — `uci set`, `uci
  commit`, `ifdown`/`ifup`, `/etc/init.d/network reload|restart`,
  `ubus call system reboot`. Read-only by default. The write path uses
  the same metacharacter blocklist as reads; `uci set` values must match
  the regex `` `[A-Za-z0-9_.,:/@-]+` ``.
- **SSH host-key verification** with trust-on-first-use by default and a
  clear refusal on key change.
- **Audit log** with 5 MB rotation and timestamped request IDs.
- **stdio transport only** — the MCP client owns the process lifecycle.
  There is no HTTP sidecar.
- **Secret redaction** at the response boundary: WiFi PSKs, passwords, and
  tokens cannot leak even if a tool forgets to sanitise.

## Install

Install a **frozen** binary with [`uv`](https://docs.astral.sh/uv/). Do not
point an MCP client at `uv run` inside a git working tree — that couples the
agent to half-written source.

From a clone (or any local checkout of a tag you trust):

```bash
git clone https://github.com/windyboy/openwrt-mcp.git
cd openwrt-mcp
uv tool install .
```

Or from git without cloning:

```bash
uv tool install git+https://github.com/windyboy/openwrt-mcp.git
```

That puts `openwrt-mcp` on `PATH` (`~/.local/bin/openwrt-mcp` by default).
After you change the package, reinstall:

```bash
uv tool install --force .
# or: uv tool install --force git+https://github.com/windyboy/openwrt-mcp.git
```

Development (tests, lint) is a separate tree: `uv sync --extra dev` in the
clone. See [Development](#development).

## Configure

Router credentials and audit live under XDG, not in the MCP client config
and not in the git tree.

1. Authorise an SSH key on the router:

   ```bash
   ssh-copy-id -i ~/.ssh/openwrt_mcp_ed25519.pub root@192.168.1.1
   ```

2. Write env (mode `600`). Copy [`.env.example`](.env.example) or:

```bash
mkdir -p ~/.config/openwrt-mcp ~/.local/state/openwrt-mcp
cat > ~/.config/openwrt-mcp/env << 'EOF'
OPENWRT_HOST=192.168.1.1
OPENWRT_PORT=22
OPENWRT_USER=root
OPENWRT_SSH_KEY=/home/you/.ssh/openwrt_mcp_ed25519
ENABLE_WRITE_OPERATIONS=false
ENABLE_AUDIT_LOGGING=true
AUDIT_LOG_FILE=/home/you/.local/state/openwrt-mcp/audit.log
LOG_LEVEL=INFO
EOF
chmod 600 ~/.config/openwrt-mcp/env
```

3. Optional wrapper so the MCP client only execs one path (sources the env
   file, then the installed binary):

```bash
cat > ~/.config/openwrt-mcp/run << 'EOF'
#!/bin/sh
set -eu
ENV_FILE="${OPENWRT_MCP_ENV:-$HOME/.config/openwrt-mcp/env}"
if [ -f "$ENV_FILE" ]; then
  set -a
  . "$ENV_FILE"
  set +a
fi
exec "${OPENWRT_MCP_BIN:-$HOME/.local/bin/openwrt-mcp}"
EOF
chmod 755 ~/.config/openwrt-mcp/run
```

Host keys default to trust-on-first-use at `~/.config/openwrt-mcp/known_hosts`.

## Run

stdio only — the MCP client owns the process. Smoke-test:

```bash
~/.config/openwrt-mcp/run
# or, with the same env already exported: openwrt-mcp
```

`main()` takes no flags (`--transport` is gone).

### opencode

```jsonc
{
  "mcp": {
    "openwrt": {
      "type": "local",
      "command": ["/home/you/.config/openwrt-mcp/run"],
      "enabled": true
    }
  }
}
```

Do not put router env in `opencode.json`. Reload MCP (or restart the
client) after install or reinstall; a running child keeps the old binary.

## Configuration reference

| Variable | Default | Description |
|---|---|---|
| `OPENWRT_HOST` | — | Router IP or hostname |
| `OPENWRT_PORT` | `22` | SSH port |
| `OPENWRT_USER` | `root` | SSH username |
| `OPENWRT_SSH_KEY` | `~/.ssh/openwrt_mcp_ed25519` | Path to SSH private key |
| `OPENWRT_PASSWORD` | — | SSH password (discouraged — use keys) |
| `OPENWRT_KNOWN_HOSTS` | — | Path to an OpenSSH known_hosts file (strict mode) |
| `OPENWRT_HOST_KEY_POLICY` | `tofu` | `tofu` (default) or `none` |
| `ENABLE_WRITE_OPERATIONS` | `false` | Set to `true` to register write tools |
| `ENABLE_AUDIT_LOGGING` | `true` | Log every executed command |
| `AUDIT_LOG_FILE` | `~/.local/state/openwrt-mcp/audit.log` | Audit log path |
| `LOG_LEVEL` | `INFO` | Standard logging level |

## Security model

See [`docs/SECURITY.md`](docs/SECURITY.md) for the threat model and the
command allowlist in detail. The short version: **the router is root**, so
the server is built to refuse anything not explicitly whitelisted, verify
the router's identity, and leave an audit trail of every command.

`starlette` / `uvicorn` may still appear in the venv via FastMCP → `mcp`;
this process never binds TCP. See
[Known limitations](docs/SECURITY.md#known-limitations).

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the module map,
transport, and the security layers in execution order.

## Development

```bash
uv sync --extra dev
uv run pytest tests/unit -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src/openwrt_mcp --strict
```

See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Acknowledgements

Forked from [paulomac1000/openwrt-mcp](https://github.com/paulomac1000/openwrt-mcp),
which itself was forked from [jsebgiraldo/openwrt_ssh_mcp](https://github.com/jsebgiraldo/openwrt_ssh_mcp).
Both upstream projects are MIT-licensed.

## License

MIT — see [`LICENSE`](LICENSE).
