"""Safe Garmin client loading and shared helpers for the MCP server."""

from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path
from typing import Any

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

_SECRET_PATTERNS = [
    re.compile(
        r'("?(?:access|refresh|di|jwt|oauth)?_?token"?\s*[:=]\s*)"?[^",}\s]+',
        re.I,
    ),
    re.compile(r"(Authorization\s*[:=]\s*)Bearer\s+[A-Za-z0-9._~+/-]+=*", re.I),
    re.compile(r'("?(?:password|authorization|cookie)"?\s*[:=]\s*)"?[^",}\s]+', re.I),
    re.compile(r'(Bearer\s+)[A-Za-z0-9._~+/-]+=*', re.I),
]


class GarminMCPError(RuntimeError):
    """Base error raised by the MCP adapter."""


class GarminTokenSetupError(GarminMCPError):
    """Raised when no usable saved Garmin tokens are available."""


def get_config_path() -> Path:
    """Return the MCP adapter config path."""
    raw = os.getenv("GARMINCONNECT_MCP_CONFIG")
    if raw:
        return Path(raw).expanduser().resolve()
    return Path("~/.garminconnect-mcp/config.json").expanduser().resolve()


def get_tokenstore_path(value: str | os.PathLike[str] | None = None) -> Path:
    """Resolve the Garmin tokenstore path used by both auth and server commands."""
    raw = value or os.getenv("GARMINTOKENS") or "~/.garminconnect"
    return Path(raw).expanduser().resolve()


def redact_secrets(value: object) -> str:
    """Return a string with obvious token/password material removed."""
    text = str(value)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(r"\1[REDACTED]", text)
    return text


def require_confirm(confirm: bool, action: str) -> None:
    """Guard account-changing tools."""
    if not confirm:
        raise GarminMCPError(f"{action} requires confirm=true.")


def load_config() -> dict[str, Any]:
    """Load local non-secret MCP preferences."""
    path = get_config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GarminMCPError(f"Invalid MCP config JSON at {path}") from exc
    if not isinstance(data, dict):
        raise GarminMCPError(f"Invalid MCP config shape at {path}")
    return data


def save_config(data: dict[str, Any]) -> None:
    """Save local non-secret MCP preferences."""
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def list_known_device_ids() -> list[str]:
    """Return remembered Garmin device IDs."""
    values = load_config().get("known_device_ids", [])
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value)]


def get_default_device_id() -> str | None:
    """Return the configured default device ID, if any."""
    env_device_id = os.getenv("GARMIN_DEVICE_ID")
    if env_device_id:
        return env_device_id
    value = load_config().get("default_device_id")
    return str(value) if value else None


def remember_device_id(device_id: str, *, make_default: bool = False) -> None:
    """Remember a Garmin device ID and optionally make it the default."""
    device_id = str(device_id).strip()
    if not device_id:
        return
    data = load_config()
    known = list_known_device_ids()
    if device_id not in known:
        known.append(device_id)
    data["known_device_ids"] = known
    if make_default or not data.get("default_device_id"):
        data["default_device_id"] = device_id
    save_config(data)


class GarminClientProvider:
    """Lazy Garmin client provider that authenticates only from saved tokens."""

    def __init__(self, tokenstore: str | os.PathLike[str] | None = None) -> None:
        self.tokenstore = get_tokenstore_path(tokenstore)
        self._client: Garmin | None = None
        self._lock = threading.Lock()

    def reset(self) -> None:
        with self._lock:
            self._client = None

    def get(self) -> Garmin:
        with self._lock:
            if self._client is not None:
                return self._client
            self._client = self._load()
            return self._client

    def _load(self) -> Garmin:
        if not self.tokenstore.exists():
            raise GarminTokenSetupError(
                "No Garmin tokens found. Run garminconnect-mcp-auth in a "
                "terminal first."
            )

        garmin = Garmin()
        try:
            garmin.login(str(self.tokenstore))
        except (GarminConnectAuthenticationError, GarminConnectConnectionError) as exc:
            raise GarminTokenSetupError(
                "Saved Garmin tokens could not be used. Run "
                "garminconnect-mcp-auth again. "
                f"Details: {redact_secrets(exc)}"
            ) from exc
        except GarminConnectTooManyRequestsError as exc:
            raise GarminMCPError(f"Garmin rate limit: {redact_secrets(exc)}") from exc
        except Exception as exc:
            raise GarminMCPError(
                f"Could not initialize Garmin client: {redact_secrets(exc)}"
            ) from exc
        return garmin


def as_jsonable(value: Any) -> Any:
    """Convert common non-JSON values returned by garminconnect into safe data."""
    if isinstance(value, bytes):
        return {"bytes": len(value)}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): as_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [as_jsonable(item) for item in value]
    return value
