"""Tests for Garmin client helper behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

from garminconnect_mcp.client import (
    GarminMCPError,
    as_jsonable,
    get_default_device_id,
    get_tokenstore_path,
    list_known_device_ids,
    redact_secrets,
    remember_device_id,
    require_confirm,
)


def test_redact_secrets_removes_tokens_and_passwords() -> None:
    text = redact_secrets(
        'access_token="abc123", password="secret", Authorization=Bearer xyz'
    )
    assert "abc123" not in text
    assert "secret" not in text
    assert "xyz" not in text
    assert "[REDACTED]" in text


def test_require_confirm_blocks_mutation() -> None:
    with pytest.raises(GarminMCPError, match="confirm=true"):
        require_confirm(False, "Deleting an activity")


def test_require_confirm_allows_confirmed_mutation() -> None:
    require_confirm(True, "Deleting an activity")


def test_as_jsonable_converts_bytes_paths_and_sets(tmp_path: Path) -> None:
    value = {"payload": b"abc", "path": tmp_path, "items": {1, 2}}
    converted = as_jsonable(value)
    assert converted["payload"] == {"bytes": 3}
    assert converted["path"] == str(tmp_path)
    assert sorted(converted["items"]) == [1, 2]


def test_get_tokenstore_path_uses_argument(tmp_path: Path) -> None:
    assert get_tokenstore_path(tmp_path) == tmp_path.resolve()


def test_remember_device_id_tracks_default_and_known_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GARMINCONNECT_MCP_CONFIG", str(tmp_path / "config.json"))

    remember_device_id("123")
    remember_device_id("456")

    assert get_default_device_id() == "123"
    assert list_known_device_ids() == ["123", "456"]

    remember_device_id("456", make_default=True)
    assert get_default_device_id() == "456"
