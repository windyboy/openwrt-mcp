"""SSH connection manager for the OpenWRT router."""

import asyncio
import base64
import hashlib
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from openwrt_mcp.observability import get_request_id
from openwrt_mcp.tools.constants import (
    AUDIT_LOG_FILE,
    ENABLE_AUDIT_LOGGING,
    HOST_KEY_POLICY,
    OPENWRT_HOST,
    OPENWRT_KNOWN_HOSTS,
    OPENWRT_PASSWORD,
    OPENWRT_PORT,
    OPENWRT_SSH_KEY,
    OPENWRT_USER,
    SSH_TIMEOUT,
    TOFU_KNOWN_HOSTS_PATH,
)
from openwrt_mcp.validators import SecurityValidator

_AUDIT_LOG_MAX_BYTES = 5 * 1024 * 1024


def _host_pattern(host: str, port: int) -> str:
    """known_hosts host field for a host:port pair."""
    return f"[{host}]:{port}" if port != 22 else host


def _known_hosts_entry(host: str, port: int, public_key_line: str) -> str:
    """One known_hosts line: '<host pattern> ssh-ed25519 AAAA...'."""
    return f"{_host_pattern(host, port)} {public_key_line.strip()}"


def _key_fingerprint(public_key_line: str) -> str:
    """ssh-keygen style SHA256 fingerprint of an OpenSSH public key line."""
    parts = public_key_line.strip().split()
    blob = parts[1] if len(parts) >= 2 else public_key_line.strip()
    digest = hashlib.sha256(base64.b64decode(blob)).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


class SSHConnection:
    """SSH connection manager for the OpenWRT router."""

    def __init__(self) -> None:
        self._connection: Any = None
        self._last_activity: float = 0.0
        self._lock = asyncio.Lock()
        self._timeout: int = SSH_TIMEOUT
        self._cancelled = asyncio.Event()

    def set_timeout(self, seconds: int) -> None:
        """Override SSH timeout for the next command."""
        self._timeout = seconds

    def cancel(self) -> None:
        """Signal cancellation to in-flight operations."""
        self._cancelled.set()

    async def connect(self) -> bool:
        """Establish SSH connection to the router."""
        import asyncssh

        self._cancelled.clear()
        async with self._lock:
            if self._connection:
                try:
                    self._connection.close()
                    await self._connection.wait_closed()
                except Exception:
                    pass

            try:
                known_hosts_arg, tofu_pin = self._resolve_host_key_policy()
                connect_kwargs = {
                    "host": OPENWRT_HOST,
                    "port": OPENWRT_PORT,
                    "username": OPENWRT_USER,
                    "known_hosts": known_hosts_arg,
                    "connect_timeout": SSH_TIMEOUT,
                    "login_timeout": SSH_TIMEOUT,
                }

                if OPENWRT_SSH_KEY and Path(OPENWRT_SSH_KEY).exists():
                    connect_kwargs["client_keys"] = [OPENWRT_SSH_KEY]
                elif OPENWRT_PASSWORD:
                    connect_kwargs["password"] = OPENWRT_PASSWORD
                else:
                    raise ValueError("SSH authentication configuration missing.")

                self._connection = await asyncssh.connect(**connect_kwargs)
                self._last_activity = time.time()
                if tofu_pin:
                    await self._pin_host_key()
                logging.info(
                    "[openwrt] SSH connection established: %s@%s", OPENWRT_USER, OPENWRT_HOST
                )
                return True

            except Exception as e:
                msg = str(e)
                if "host key" in msg.lower() or "not verified" in msg.lower():
                    logging.error(
                        "[openwrt] HOST KEY VERIFICATION FAILED for %s:%s. "
                        "If this key change is intentional, update the known-hosts "
                        "store at %s (or set OPENWRT_HOST_KEY_POLICY=none to opt out). "
                        "Refusing to connect.",
                        OPENWRT_HOST,
                        OPENWRT_PORT,
                        TOFU_KNOWN_HOSTS_PATH,
                    )
                else:
                    logging.error("[openwrt] SSH connection error: %s", msg)
                return False

    @staticmethod
    def _resolve_host_key_policy() -> tuple[Any, bool]:
        """Return (asyncssh known_hosts argument, tofu_pin flag).

        - HOST_KEY_POLICY=none      -> (None, False): legacy accept-any behaviour
        - OPENWRT_KNOWN_HOSTS set   -> strict verification against that file
        - TOFU store exists         -> strict verification against the store
        - otherwise                 -> (None, True): pin key on first connect
        """
        if HOST_KEY_POLICY == "none":
            return None, False
        if OPENWRT_KNOWN_HOSTS:
            return OPENWRT_KNOWN_HOSTS, False
        if Path(TOFU_KNOWN_HOSTS_PATH).exists():
            return TOFU_KNOWN_HOSTS_PATH, False
        return None, True

    async def _pin_host_key(self) -> None:
        """Trust-on-first-use: pin the server host key to the TOFU store."""
        try:
            key = self._connection.get_server_host_key()
            if key is None:
                logging.warning("[openwrt] Server host key unavailable; TOFU pin skipped")
                return
            pub = key.export_public_key().decode().strip()
            entry = _known_hosts_entry(OPENWRT_HOST, OPENWRT_PORT, pub)
            store = Path(TOFU_KNOWN_HOSTS_PATH)
            store.parent.mkdir(parents=True, exist_ok=True)
            existing = store.read_text(encoding="utf-8") if store.exists() else ""
            if _host_pattern(OPENWRT_HOST, OPENWRT_PORT) not in existing:
                with open(store, "a", encoding="utf-8") as f:
                    f.write(entry + "\n")
                store.chmod(0o600)
            logging.warning(
                "[openwrt] Trust-on-first-use: pinned host key %s for %s:%s in %s",
                _key_fingerprint(pub),
                OPENWRT_HOST,
                OPENWRT_PORT,
                store,
            )
        except OSError as e:
            logging.warning("[openwrt] TOFU host-key pin failed: %s", e)

    async def execute(self, command: str) -> tuple[str, str, int]:
        """Execute a command on the router over SSH."""
        import asyncssh

        if not self._connection:
            if not await self.connect():
                return "", "No SSH connection", 1

        # SECURITY: Validate command before execution
        is_valid, msg = SecurityValidator.validate_command(command)
        if not is_valid:
            logging.warning("[openwrt] Command rejected: %s... - %s", command[:50], msg)
            return "", f"Security denial: {msg}", 1

        # SECURITY: Additional sanitation (defense in depth)
        safe_cmd = command.strip()

        if self._cancelled.is_set():
            return "", "Operation cancelled", 1

        if ENABLE_AUDIT_LOGGING:
            self._log_audit(safe_cmd)

        timeout = self._timeout

        try:
            result = await self._connection.run(safe_cmd, timeout=timeout)
            self._last_activity = time.time()
            return result.stdout, result.stderr, result.exit_status

        except (asyncssh.ConnectionLost, asyncssh.DisconnectError, OSError) as e:
            logging.warning("[openwrt] SSH connection lost (%s), attempting reconnect...", e)
            if await self.connect():
                try:
                    result = await self._connection.run(safe_cmd, timeout=timeout)
                    self._last_activity = time.time()
                    return result.stdout, result.stderr, result.exit_status
                except Exception as e2:
                    return "", f"Error after reconnect: {str(e2)}", 1
            return "", f"Failed to re-establish connection: {str(e)}", 1

        except asyncssh.TimeoutError:
            return "", f"Timeout after {timeout}s: {safe_cmd[:30]}...", 124

        except Exception as e:
            return "", f"Execution error: {str(e)}", 1

        finally:
            self._timeout = SSH_TIMEOUT  # always reset to default

    async def execute_write(self, command: str) -> tuple[str, str, int]:
        """Execute a write operation on the router over SSH.

        Uses ALLOWED_WRITE_PATTERNS instead of ALLOWED_PATTERNS for validation.
        Only used by write tools (restart_interface, uci_set, etc.).
        """
        import asyncssh

        if not self._connection:
            if not await self.connect():
                return "", "No SSH connection", 1

        is_valid, msg = SecurityValidator.validate_write_command(command)
        if not is_valid:
            logging.warning("[openwrt] Write command rejected: %s... - %s", command[:50], msg)
            return "", f"Security denial: {msg}", 1

        safe_cmd = command.strip()
        if self._cancelled.is_set():
            return "", "Operation cancelled", 1
        if ENABLE_AUDIT_LOGGING:
            self._log_audit(safe_cmd)
        timeout = self._timeout
        try:
            result = await self._connection.run(safe_cmd, timeout=timeout)
            self._last_activity = time.time()
            return result.stdout, result.stderr, result.exit_status
        except (asyncssh.ConnectionLost, asyncssh.DisconnectError, OSError) as e:
            logging.warning(
                "[openwrt] SSH connection lost during write (%s), attempting reconnect...", e
            )
            if await self.connect():
                try:
                    result = await self._connection.run(safe_cmd, timeout=timeout)
                    self._last_activity = time.time()
                    return result.stdout, result.stderr, result.exit_status
                except Exception as retry_err:
                    return "", str(retry_err), 1
            return "", str(e), 1
        except asyncssh.TimeoutError:
            return "", f"Timeout after {timeout}s: {safe_cmd[:30]}...", 124
        except Exception as e:
            return "", f"Execution error: {str(e)}", 1
        finally:
            self._timeout = SSH_TIMEOUT

    def _log_audit(self, command: str) -> None:
        """Append a command to the audit log, rotating at 5 MB.

        Audit failures are logged, never silently swallowed.
        """
        try:
            log_path = Path(AUDIT_LOG_FILE)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                size = log_path.stat().st_size
            except FileNotFoundError:
                size = 0
            if size > _AUDIT_LOG_MAX_BYTES:
                log_path.replace(log_path.with_suffix(log_path.suffix + ".1"))
                logging.info("[openwrt] Audit log rotated: %s.1", log_path)
            timestamp = datetime.now().isoformat()
            log_entry = (
                f"{timestamp} | {get_request_id()} | {OPENWRT_USER}@{OPENWRT_HOST} | {command}\n"
            )
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except OSError as e:
            logging.warning("[openwrt] Audit log write failed (%s): %s", AUDIT_LOG_FILE, e)

    async def close(self) -> None:
        async with self._lock:
            if self._connection:
                try:
                    self._connection.close()
                    await self._connection.wait_closed()
                except Exception:
                    pass
            self._connection = None
