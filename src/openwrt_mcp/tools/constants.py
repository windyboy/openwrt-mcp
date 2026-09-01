"""Centralized constants — Single Source of Truth for all environment variables."""

import os

OPENWRT_HOST = os.getenv("OPENWRT_HOST", "192.168.1.1")
OPENWRT_PORT = int(os.getenv("OPENWRT_PORT", "22"))
OPENWRT_USER = os.getenv("OPENWRT_USER", "root")
OPENWRT_SSH_KEY = os.getenv("OPENWRT_SSH_KEY", "/app/keys/openwrt_id_ed25519")
OPENWRT_PASSWORD = os.getenv("OPENWRT_PASSWORD", None)
SSH_TIMEOUT = int(os.getenv("SSH_TIMEOUT", "30"))
ENABLE_AUDIT_LOGGING = os.getenv("ENABLE_AUDIT_LOGGING", "true").lower() in (
    "1",
    "true",
    "yes",
)
AUDIT_LOG_FILE = os.getenv("AUDIT_LOG_FILE", "/app/log/openwrt_mcp.log")

# Host-key verification policy:
#   - OPENWRT_HOST_KEY_POLICY=none        -> accept any host key (legacy behaviour)
#   - OPENWRT_KNOWN_HOSTS set             -> strict verification against that file
#   - TOFU store exists                   -> strict verification against the store
#   - otherwise                           -> trust-on-first-use: pin key on first connect
_TOFU_STORE_DEFAULT = os.path.join(os.path.expanduser("~"), ".config", "openwrt-mcp", "known_hosts")
TOFU_KNOWN_HOSTS_PATH = os.getenv("OPENWRT_KNOWN_HOSTS", "") or _TOFU_STORE_DEFAULT
OPENWRT_KNOWN_HOSTS = os.getenv("OPENWRT_KNOWN_HOSTS", "") or (
    _TOFU_STORE_DEFAULT if os.path.exists(_TOFU_STORE_DEFAULT) else None
)
HOST_KEY_POLICY = os.getenv("OPENWRT_HOST_KEY_POLICY", "tofu").lower()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
ENABLE_WRITE_OPERATIONS = os.getenv("ENABLE_WRITE_OPERATIONS", "false").lower() in (
    "1",
    "true",
    "yes",
)
