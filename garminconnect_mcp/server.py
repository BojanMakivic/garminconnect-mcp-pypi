"""FastMCP server exposing Garmin Connect through curated tools."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

from .client import (
    GarminClientProvider,
    GarminMCPError,
    as_jsonable,
    get_default_device_id,
    get_tokenstore_path,
    list_known_device_ids,
    remember_device_id,
    require_confirm,
)
from .strength import (
    display_strength_exercise_sets,
    is_known_strength_exercise,
    resolve_strength_exercise,
)

_LOGGER = logging.getLogger("garminconnect_mcp")
_provider = GarminClientProvider()
mcp = FastMCP("garminconnect")

ActivityDownloadFormat = Literal["fit", "tcx", "gpx", "kml", "csv"]

_DIRECT_WORKOUT_FEELINGS = {
    "very_weak": 0,
    "very weak": 0,
    "weak": 25,
    "normal": 50,
    "strong": 75,
    "very_strong": 100,
    "very strong": 100,
}


def _find_activity_id(value: Any) -> str | None:
    if isinstance(value, dict):
        for key in ("activityId", "activity_id", "id"):
            if value.get(key):
                return str(value[key])
        for child in value.values():
            found = _find_activity_id(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = _find_activity_id(child)
            if found:
                return found
    return None


def _parse_activity_datetime(start_datetime: str, time_zone: str) -> datetime:
    parsed = datetime.fromisoformat(start_datetime.replace("Z", "+00:00"))
    zone = ZoneInfo(time_zone)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=zone)
    return parsed.astimezone(zone)


def _format_garmin_local(value: datetime) -> str:
    return value.replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]


def _format_garmin_utc(value: datetime) -> str:
    return value.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%M:%S.0")


def _parse_clock_time(value: str) -> tuple[int, int, int] | None:
    parts = value.strip().split(":")
    if len(parts) not in {2, 3}:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
        second = int(parts[2]) if len(parts) == 3 else 0
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        return None
    return hour, minute, second


def _format_strength_set_start_time(value: Any, local_start: datetime) -> str:
    """Return a Garmin UTC timestamp for a strength set start time.

    Some MCP clients send user-friendly clock times like "07:04:00". Garmin's
    exercise-set endpoint needs a full timestamp, so interpret clock-only and
    naive date-times in the activity's local timezone.
    """
    start_time = str(value).strip()
    if not start_time:
        raise ValueError("start_time must be a non-empty string")
    clock_time = _parse_clock_time(start_time)
    if clock_time:
        hour, minute, second = clock_time
        return _format_garmin_utc(
            local_start.replace(
                hour=hour,
                minute=minute,
                second=second,
                microsecond=0,
            )
        )
    try:
        parsed = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(
            "start_time must be ISO date-time, HH:MM, or HH:MM:SS"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_start.tzinfo)
    else:
        parsed = parsed.astimezone(local_start.tzinfo)
    return _format_garmin_utc(parsed)


def _resolve_strength_set_spec(item: dict[str, Any]) -> dict[str, str]:
    exercise = item.get("exercise") or item.get("exercise_name")
    if exercise:
        match = resolve_strength_exercise(str(exercise))
    elif "category" not in item and item.get("name"):
        match = resolve_strength_exercise(str(item["name"]))
    else:
        if "category" not in item or "name" not in item:
            raise ValueError(
                "Each strength set must include exercise, name, or category/name"
            )
        category = str(item["category"])
        name = str(item["name"])
        if is_known_strength_exercise(category, name):
            match = {"category": category, "name": name, "match_type": "provided"}
        else:
            match = {
                **resolve_strength_exercise(f"{category} {name}"),
                "provided_category": category,
                "provided_name": name,
            }
    if "weight_kg" not in item and match["name"].startswith("WEIGHTED_"):
        bodyweight_name = match["name"].removeprefix("WEIGHTED_")
        if is_known_strength_exercise(match["category"], bodyweight_name):
            return {
                **match,
                "name": bodyweight_name,
                "weighted_name": match["name"],
                "match_type": f"{match['match_type']}_bodyweight",
            }
    return match


def _coerce_bool(value: bool | str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n", ""}:
            return False
    raise ValueError(f"Expected a boolean value, got: {value!r}")


def _coerce_positive_int(value: int | float | str, name: str) -> int:
    try:
        parsed = int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _coerce_strength_set_type(value: Any, index: int) -> str:
    if value is None or value == "":
        return "ACTIVE"
    if not isinstance(value, str):
        raise ValueError(f"sets[{index}].set_type must be ACTIVE or REST")
    normalized = value.strip().upper()
    if normalized in {"ACTIVE", "REST"}:
        return normalized
    raise ValueError(f"sets[{index}].set_type must be ACTIVE or REST")


def _coerce_direct_workout_feel(value: int | float | str | None) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        normalized = value.strip().lower().replace("-", "_")
        if normalized in _DIRECT_WORKOUT_FEELINGS:
            return _DIRECT_WORKOUT_FEELINGS[normalized]
        try:
            value = float(normalized)
        except ValueError as exc:
            allowed = ", ".join(
                ["very_weak", "weak", "normal", "strong", "very_strong"]
            )
            raise ValueError(
                f"subjective_feeling must be one of: {allowed}"
            ) from exc
    try:
        parsed = int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError("subjective_feeling must be a label or number") from exc
    if parsed not in {0, 25, 50, 75, 100}:
        raise ValueError(
            "numeric subjective_feeling must be one of 0, 25, 50, 75, or 100"
        )
    return parsed


def _coerce_direct_workout_rpe(value: int | float | str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("perceived_effort must be a number from 0 to 10") from exc
    if parsed < 0:
        raise ValueError("perceived_effort must be from 0 to 10")
    if parsed <= 10:
        return int(round(parsed * 10))
    if parsed <= 100:
        return int(round(parsed))
    raise ValueError("perceived_effort must be from 0 to 10")


def _set_activity_self_evaluation(
    activity_id: str,
    direct_workout_feel: int | None = None,
    direct_workout_rpe: int | None = None,
) -> Any:
    if direct_workout_feel is None and direct_workout_rpe is None:
        raise ValueError(
            "At least one of subjective_feeling or perceived_effort is required"
        )
    api = _api()
    if hasattr(api, "set_activity_self_evaluation"):
        return api.set_activity_self_evaluation(
            activity_id,
            direct_workout_feel=direct_workout_feel,
            direct_workout_rpe=direct_workout_rpe,
        )
    payload: dict[str, Any] = {
        "activityId": int(activity_id),
        "summaryDTO": {},
    }
    if direct_workout_feel is not None:
        payload["summaryDTO"]["directWorkoutFeel"] = direct_workout_feel
    if direct_workout_rpe is not None:
        payload["summaryDTO"]["directWorkoutRpe"] = direct_workout_rpe
    response = api.client.request(
        "PUT",
        "connectapi",
        f"/activity-service/activity/{activity_id}",
        json=payload,
        api=True,
    )
    return {
        "status_code": getattr(response, "status_code", None),
        "payload": payload,
    }


def _coerce_strength_sets(
    value: list[dict[str, Any]] | dict[str, Any] | str,
) -> list[dict[str, Any]]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "sets must be a JSON array of set objects, not plain text. "
                'Example: [{"exercise":"squat","repetitions":8,"weight_kg":70}]'
            ) from exc
    if isinstance(value, dict):
        value = [value]
    if not isinstance(value, list):
        raise ValueError("sets must be a list of set objects")
    expanded: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"sets[{index}] must be an object")
        item = dict(item)
        weight_kg = item.get("weight_kg")
        if isinstance(weight_kg, str):
            weight_kg = weight_kg.strip()
            try:
                weight_kg = float(weight_kg) if weight_kg else None
            except ValueError as exc:
                raise ValueError(f"sets[{index}].weight_kg must be a number") from exc
            item["weight_kg"] = weight_kg
        if weight_kg in ("", None) or (
            isinstance(weight_kg, int | float) and weight_kg <= 0
        ):
            item.pop("weight_kg", None)
        elif isinstance(weight_kg, int | float):
            item["weight_kg"] = float(weight_kg)
        item["set_type"] = _coerce_strength_set_type(item.get("set_type"), index)
        set_count = item.pop("sets", 1)
        try:
            set_count = int(set_count)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"sets[{index}].sets must be an integer") from exc
        if set_count <= 0:
            raise ValueError(f"sets[{index}].sets must be positive")
        expanded.extend(dict(item) for _ in range(set_count))
    return expanded


def _build_strength_exercise_sets(
    sets: list[dict[str, Any]],
    local_start: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    exercise_sets: list[dict[str, Any]] = []
    matches: list[dict[str, str]] = []
    next_offset = 0.0
    for item in sets:
        if item.get("start_time"):
            set_start = _format_strength_set_start_time(item["start_time"], local_start)
        else:
            offset = item.get("offset_seconds")
            if offset is None:
                offset = float(item.get("offset_minutes", next_offset / 60.0)) * 60.0
            set_start = _format_garmin_utc(local_start + timedelta(seconds=offset))
        duration_seconds = float(item.get("duration_seconds", 30.0))
        match = _resolve_strength_set_spec(item)
        matches.append(match)
        exercise_sets.append(
            _build_strength_exercise_set_payload(
                match["category"],
                match["name"],
                set_start,
                repetitions=item.get("repetitions"),
                weight_kg=item.get("weight_kg"),
                duration_seconds=duration_seconds,
                set_type=item.get("set_type", "ACTIVE"),
            )
        )
        next_offset += duration_seconds + float(item.get("rest_seconds", 90.0))
    return exercise_sets, matches


def _sets_need_activity_start(sets: list[dict[str, Any]]) -> bool:
    for item in sets:
        start_time = item.get("start_time")
        if not start_time:
            return True
        if _parse_clock_time(str(start_time).strip()):
            return True
    return False


def _activity_start_for_strength_sets(
    activity_id: str,
    sets: list[dict[str, Any]],
    activity_start_datetime: str | None = None,
    time_zone: str = "UTC",
) -> datetime:
    if activity_start_datetime:
        return _parse_activity_datetime(activity_start_datetime, time_zone)
    if not _sets_need_activity_start(sets):
        return datetime.now(tz=ZoneInfo("UTC"))

    activity = _call("get_activity", activity_id)
    if not isinstance(activity, dict):
        raise ValueError(
            "activity_start_datetime is required because the activity start "
            "time could not be read from Garmin"
        )
    summary = activity.get("summaryDTO")
    if not isinstance(summary, dict):
        summary = {}
    start = (
        summary.get("startTimeGMT")
        or activity.get("startTimeGMT")
        or summary.get("startTimeLocal")
        or activity.get("startTimeLocal")
    )
    if not start:
        raise ValueError(
            "activity_start_datetime is required because the activity start "
            "time could not be read from Garmin"
        )
    return _parse_activity_datetime(str(start).replace(" ", "T"), "UTC")


def _build_strength_exercise_set_payload(
    category: str,
    name: str,
    start_time: str,
    *,
    repetitions: int | None = None,
    weight_kg: float | None = None,
    duration_seconds: float = 30.0,
    set_type: str = "ACTIVE",
) -> dict[str, Any]:
    weight = float(weight_kg) * 1000.0 if weight_kg is not None else -1.0
    return {
        "exercises": [{"category": category, "name": name, "probability": 100.0}],
        "duration": float(duration_seconds),
        "repetitionCount": repetitions,
        "weight": weight,
        "setType": set_type,
        "startTime": start_time,
        "wktStepIndex": None,
        "messageIndex": None,
    }


def configure_logging(log_file: str | None = None, verbose: bool = False) -> None:
    """Configure logging without writing protocol-breaking text to stdout."""
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def set_provider(provider: GarminClientProvider) -> None:
    """Replace the global provider, mainly for tests."""
    global _provider
    _provider = provider


def _api() -> Any:
    return _provider.get()


def _activity_download_format(dl_fmt: str) -> Any:
    formats = _api().ActivityDownloadFormat
    normalized = dl_fmt.upper()
    if normalized == "FIT":
        normalized = "ORIGINAL"
    return formats[normalized]


def _extract_device_ids(devices: Any) -> list[str]:
    """Extract plausible Garmin device IDs from device payloads."""
    if not isinstance(devices, list):
        return []
    keys = ("deviceId", "device_id", "unitId", "unit_id", "id")
    found: list[str] = []
    for device in devices:
        if not isinstance(device, dict):
            continue
        for key in keys:
            value = device.get(key)
            if value:
                device_id = str(value)
                if device_id not in found:
                    found.append(device_id)
                break
    return found


def _resolve_device_id(device_id: str | None) -> str:
    if device_id:
        remember_device_id(device_id)
        return device_id
    default_device_id = get_default_device_id()
    if default_device_id:
        remember_device_id(default_device_id)
        return default_device_id
    raise GarminMCPError(
        "No device_id was provided and no default device ID is configured. "
        "Pass device_id once, set GARMIN_DEVICE_ID, or call "
        "set_default_device_id."
    )


def _call(method_name: str, *args: Any, **kwargs: Any) -> Any:
    try:
        return as_jsonable(_call_raw(method_name, *args, **kwargs))
    except GarminMCPError:
        raise
    except Exception as exc:
        _LOGGER.exception("Garmin method failed: %s", method_name)
        raise GarminMCPError(f"Garmin {method_name} failed: {exc}") from exc


def _call_raw(method_name: str, *args: Any, **kwargs: Any) -> Any:
    method = getattr(_api(), method_name)
    return method(*args, **kwargs)


@mcp.tool()
def garmin_status() -> dict[str, Any]:
    """Check whether saved Garmin tokens can initialize the client."""
    api = _api()
    return {
        "authenticated": True,
        "tokenstore": str(_provider.tokenstore),
        "full_name": api.get_full_name(),
        "unit_system": api.get_unit_system(),
    }


@mcp.tool()
def get_profile() -> dict[str, Any]:
    """Get the Garmin user profile."""
    return _call("get_user_profile")


@mcp.tool()
def get_user_settings() -> dict[str, Any]:
    """Get Garmin user profile settings."""
    return _call("get_userprofile_settings")


@mcp.tool()
def get_devices() -> list[dict[str, Any]]:
    """List registered Garmin devices."""
    devices = _call("get_devices")
    for device_id in _extract_device_ids(devices):
        remember_device_id(device_id)
    return devices


@mcp.tool()
def list_saved_device_ids() -> dict[str, Any]:
    """List device IDs remembered by this MCP server."""
    return {
        "default_device_id": get_default_device_id(),
        "known_device_ids": list_known_device_ids(),
        "config_hint": "Set GARMIN_DEVICE_ID or call set_default_device_id.",
    }


@mcp.tool()
def set_default_device_id(device_id: str) -> dict[str, Any]:
    """Remember a Garmin device ID and make it the default for device tools."""
    remember_device_id(device_id, make_default=True)
    return {
        "default_device_id": device_id,
        "known_device_ids": list_known_device_ids(),
    }


@mcp.tool()
def get_primary_training_device() -> dict[str, Any]:
    """Get the primary training device."""
    return _call("get_primary_training_device")


@mcp.tool()
def get_device_solar_data(
    start_date: str,
    end_date: str | None = None,
    device_id: str | None = None,
) -> dict[str, Any]:
    """Get device solar data, using the saved default device ID when omitted."""
    resolved_device_id = _resolve_device_id(device_id)
    return _call("get_device_solar_data", resolved_device_id, start_date, end_date)


@mcp.tool()
def get_device_settings(device_id: str | None = None) -> dict[str, Any]:
    """Get settings for a Garmin device, using the saved default when omitted."""
    return _call("get_device_settings", _resolve_device_id(device_id))


@mcp.tool()
def get_daily_summary(date: str) -> dict[str, Any]:
    """Get Garmin daily summary for YYYY-MM-DD."""
    return _call("get_user_summary", date)


@mcp.tool()
def get_daily_stats(date: str) -> dict[str, Any]:
    """Get Garmin daily stats for YYYY-MM-DD."""
    return _call("get_stats", date)


@mcp.tool()
def get_steps_data(date: str) -> list[dict[str, Any]]:
    """Get intraday steps for YYYY-MM-DD."""
    return _call("get_steps_data", date)


@mcp.tool()
def get_daily_steps(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Get daily steps between two YYYY-MM-DD dates."""
    return _call("get_daily_steps", start_date, end_date)


@mcp.tool()
def get_floors(date: str) -> dict[str, Any]:
    """Get floors climbed for YYYY-MM-DD."""
    return _call("get_floors", date)


@mcp.tool()
def get_heart_rates(date: str) -> dict[str, Any]:
    """Get heart rate data for YYYY-MM-DD."""
    return _call("get_heart_rates", date)


@mcp.tool()
def get_sleep_data(date: str) -> dict[str, Any]:
    """Get sleep data for YYYY-MM-DD."""
    return _call("get_sleep_data", date)


@mcp.tool()
def get_stress_data(date: str) -> dict[str, Any]:
    """Get stress data for YYYY-MM-DD."""
    return _call("get_stress_data", date)


@mcp.tool()
def get_hrv_data(date: str) -> dict[str, Any] | None:
    """Get HRV data for YYYY-MM-DD."""
    return _call("get_hrv_data", date)


@mcp.tool()
def get_body_battery(
    start_date: str, end_date: str | None = None
) -> list[dict[str, Any]]:
    """Get body battery data between two YYYY-MM-DD dates."""
    return _call("get_body_battery", start_date, end_date)


@mcp.tool()
def get_body_battery_events(date: str) -> list[dict[str, Any]]:
    """Get body battery events for YYYY-MM-DD."""
    return _call("get_body_battery_events", date)


@mcp.tool()
def get_respiration_data(date: str) -> dict[str, Any]:
    """Get respiration data for YYYY-MM-DD."""
    return _call("get_respiration_data", date)


@mcp.tool()
def get_spo2_data(date: str) -> dict[str, Any]:
    """Get SpO2 data for YYYY-MM-DD."""
    return _call("get_spo2_data", date)


@mcp.tool()
def get_hydration_data(date: str) -> dict[str, Any]:
    """Get hydration data for YYYY-MM-DD."""
    return _call("get_hydration_data", date)


@mcp.tool()
def add_hydration_data(
    value_in_ml: float,
    timestamp: str | None = None,
    date: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Add hydration data. Requires confirm=true."""
    require_confirm(confirm, "Adding hydration data")
    return _call("add_hydration_data", value_in_ml, timestamp, date)


@mcp.tool()
def get_body_composition(start_date: str, end_date: str) -> dict[str, Any]:
    """Get body composition data between dates."""
    return _call("get_body_composition", start_date, end_date)


@mcp.tool()
def get_weigh_ins(start_date: str, end_date: str) -> dict[str, Any]:
    """Get weigh-ins between dates."""
    return _call("get_weigh_ins", start_date, end_date)


@mcp.tool()
def add_weigh_in(
    weight: float,
    unit_key: str = "kg",
    timestamp: str = "",
    confirm: bool = False,
) -> dict[str, Any] | None:
    """Add a weigh-in. Requires confirm=true."""
    require_confirm(confirm, "Adding a weigh-in")
    return _call("add_weigh_in", weight, unit_key, timestamp)


@mcp.tool()
def delete_weigh_in(weight_pk: str, date: str, confirm: bool = False) -> Any:
    """Delete a weigh-in. Requires confirm=true."""
    require_confirm(confirm, "Deleting a weigh-in")
    return _call("delete_weigh_in", weight_pk, date)


@mcp.tool()
def get_blood_pressure(start_date: str, end_date: str | None = None) -> dict[str, Any]:
    """Get blood pressure records between dates."""
    return _call("get_blood_pressure", start_date, end_date)


@mcp.tool()
def set_blood_pressure(
    systolic: int,
    diastolic: int,
    pulse: int,
    timestamp: str = "",
    notes: str = "",
    confirm: bool = False,
) -> dict[str, Any]:
    """Add a blood pressure record. Requires confirm=true."""
    require_confirm(confirm, "Adding a blood pressure record")
    return _call("set_blood_pressure", systolic, diastolic, pulse, timestamp, notes)


@mcp.tool()
def delete_blood_pressure(
    version: str, date: str, confirm: bool = False
) -> dict[str, Any]:
    """Delete a blood pressure record. Requires confirm=true."""
    require_confirm(confirm, "Deleting a blood pressure record")
    return _call("delete_blood_pressure", version, date)


@mcp.tool()
def get_training_readiness(date: str) -> dict[str, Any]:
    """Get training readiness for YYYY-MM-DD."""
    return _call("get_training_readiness", date)


@mcp.tool()
def get_training_status(date: str) -> dict[str, Any]:
    """Get training status for YYYY-MM-DD."""
    return _call("get_training_status", date)


@mcp.tool()
def get_endurance_score(start_date: str, end_date: str | None = None) -> dict[str, Any]:
    """Get endurance score between dates."""
    return _call("get_endurance_score", start_date, end_date)


@mcp.tool()
def get_hill_score(start_date: str, end_date: str | None = None) -> dict[str, Any]:
    """Get hill score between dates."""
    return _call("get_hill_score", start_date, end_date)


@mcp.tool()
def get_race_predictions(
    start_date: str | None = None,
    end_date: str | None = None,
    prediction_type: str | None = None,
) -> dict[str, Any]:
    """Get race predictions between dates."""
    return _call("get_race_predictions", start_date, end_date, prediction_type)


@mcp.tool()
def get_lactate_threshold(
    latest: bool = True,
    start_date: str | None = None,
    end_date: str | None = None,
    aggregation: str = "daily",
) -> dict[str, Any]:
    """Get lactate threshold data."""
    return _call(
        "get_lactate_threshold",
        latest=latest,
        start_date=start_date,
        end_date=end_date,
        aggregation=aggregation,
    )


@mcp.tool()
def count_activities() -> int:
    """Count Garmin activities."""
    return _call("count_activities")


@mcp.tool()
def list_activities(start: int = 0, limit: int = 20) -> list[dict[str, Any]]:
    """List Garmin activities."""
    return _call("get_activities", start, limit)


@mcp.tool()
def get_activities_by_date(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """List activities between YYYY-MM-DD dates."""
    return _call("get_activities_by_date", start_date, end_date)


@mcp.tool()
def get_activity(activity_id: str) -> dict[str, Any]:
    """Get a Garmin activity summary."""
    return _call("get_activity", activity_id)


@mcp.tool()
def get_activity_details(activity_id: str) -> dict[str, Any]:
    """Get detailed Garmin activity data."""
    return _call("get_activity_details", activity_id)


@mcp.tool()
def get_activity_splits(activity_id: str) -> dict[str, Any]:
    """Get Garmin activity splits."""
    return _call("get_activity_splits", activity_id)


@mcp.tool()
def get_activity_weather(activity_id: str) -> dict[str, Any]:
    """Get weather for a Garmin activity."""
    return _call("get_activity_weather", activity_id)


@mcp.tool()
def get_activity_gear(activity_id: str) -> dict[str, Any]:
    """Get gear attached to a Garmin activity."""
    return _call("get_activity_gear", activity_id)


@mcp.tool()
def download_activity(
    activity_id: str,
    output_path: str,
    dl_fmt: ActivityDownloadFormat = "fit",
) -> dict[str, Any]:
    """Download an activity to output_path and return file metadata."""
    data = _call_raw(
        "download_activity", activity_id, _activity_download_format(dl_fmt)
    )
    if not isinstance(data, bytes):
        raise GarminMCPError("Garmin download did not return bytes.")
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": str(path), "bytes": len(data), "format": dl_fmt}


@mcp.tool()
def set_activity_name(activity_id: str, title: str, confirm: bool = False) -> Any:
    """Rename an activity. Requires confirm=true."""
    require_confirm(confirm, "Renaming an activity")
    return _call("set_activity_name", activity_id, title)


@mcp.tool()
def delete_activity(activity_id: str, confirm: bool = False) -> Any:
    """Delete an activity. Requires confirm=true."""
    require_confirm(confirm, "Deleting an activity")
    return _call("delete_activity", activity_id)


@mcp.tool()
def upload_activity(activity_path: str, confirm: bool = False) -> Any:
    """Upload an activity file. Requires confirm=true."""
    require_confirm(confirm, "Uploading an activity")
    return _call("upload_activity", activity_path)


@mcp.tool()
def import_activity(activity_path: str, confirm: bool = False) -> dict[str, Any]:
    """Import an activity file. Requires confirm=true."""
    require_confirm(confirm, "Importing an activity")
    return _call("import_activity", activity_path)


@mcp.tool()
def set_activity_type(
    activity_id: str,
    type_id: int,
    type_key: str,
    parent_type_id: int,
    confirm: bool = False,
) -> Any:
    """Set an activity type. Requires confirm=true."""
    require_confirm(confirm, "Changing an activity type")
    return _call("set_activity_type", activity_id, type_id, type_key, parent_type_id)


@mcp.tool()
def set_activity_self_evaluation(
    activity_id: str,
    subjective_feeling: int | float | str | None = None,
    perceived_effort: int | float | str | None = None,
    confirm: bool | str = False,
) -> dict[str, Any]:
    """Set Garmin activity self-evaluation. Requires confirm=true.

    subjective_feeling accepts very_weak, weak, normal, strong, very_strong
    or Garmin's internal 0/25/50/75/100 values. perceived_effort accepts the
    user-facing 0-10 RPE scale and is stored by Garmin as directWorkoutRpe.
    """
    try:
        confirm = _coerce_bool(confirm)
        require_confirm(confirm, "Updating activity self evaluation")
        direct_workout_feel = _coerce_direct_workout_feel(subjective_feeling)
        direct_workout_rpe = _coerce_direct_workout_rpe(perceived_effort)
        result = _set_activity_self_evaluation(
            activity_id,
            direct_workout_feel,
            direct_workout_rpe,
        )
        return {
            "done": True,
            "activity_id": activity_id,
            "direct_workout_feel": direct_workout_feel,
            "direct_workout_rpe": direct_workout_rpe,
            "result": as_jsonable(result),
        }
    except Exception as exc:
        return {"done": False, "error": str(exc), "activity_id": activity_id}


@mcp.tool()
def get_activity_exercise_sets(activity_id: str) -> dict[str, Any]:
    """Get structured strength-training exercise sets for an activity.

    Returned exercise weights are always reported as weightKg in kilograms.
    Garmin's internal gram value is intentionally hidden from MCP/LLM callers.
    """
    return display_strength_exercise_sets(
        _call("get_activity_exercise_sets", activity_id)
    )


@mcp.tool()
def match_strength_exercise(exercise: str) -> dict[str, str]:
    """Match a dictated exercise name to the closest Garmin strength exercise."""
    return resolve_strength_exercise(exercise)


@mcp.tool()
def set_activity_strength_exercise_sets(
    activity_id: str,
    sets: list[dict[str, Any]] | dict[str, Any] | str,
    activity_start_datetime: str | None = None,
    time_zone: str = "UTC",
    confirm: bool | str = False,
    dry_run: bool | str = False,
) -> Any:
    """Replace strength sets from kg-friendly set specs. Requires confirm=true.

    Pass dictated/user-facing exercise names directly in exercise; this tool
    resolves them to Garmin's structured strength catalog internally. Each set
    should include either exercise, or category/name. If start_time is omitted,
    the server spaces sets from the existing activity start time. Optional
    fields: start_time, offset_seconds, offset_minutes, repetitions, weight_kg,
    duration_seconds, rest_seconds, and set_type. set_type defaults to ACTIVE
    and must be ACTIVE or REST when provided. Use dry_run=true to validate the
    resolved Garmin payload without writing to Garmin.
    Use weight_kg for input. Returned exercise weights are weightKg in kg only;
    Garmin's internal gram values are not returned to MCP/LLM callers.
    """
    try:
        dry_run = _coerce_bool(dry_run)
        confirm = _coerce_bool(confirm)
        if not dry_run:
            require_confirm(confirm, "Updating activity strength exercise sets")
        sets = _coerce_strength_sets(sets)
        local_start = _activity_start_for_strength_sets(
            activity_id,
            sets,
            activity_start_datetime,
            time_zone,
        )
        exercise_sets, matches = _build_strength_exercise_sets(sets, local_start)
        if dry_run:
            return {
                "done": True,
                "dry_run": True,
                "activity_id": activity_id,
                "matches": matches,
                "exercise_sets": display_strength_exercise_sets(
                    {"activityId": activity_id, "exerciseSets": exercise_sets}
                ),
            }
        result = _call("set_activity_exercise_sets", activity_id, exercise_sets)
        return {
            "done": True,
            "activity_id": activity_id,
            "result": result,
            "matches": matches,
            "exercise_sets": display_strength_exercise_sets(
                _call("get_activity_exercise_sets", activity_id)
            ),
        }
    except Exception as exc:
        return {"done": False, "error": str(exc), "activity_id": activity_id}


@mcp.tool()
def create_strength_training_activity(
    activity_name: str,
    start_datetime: str,
    time_zone: str,
    duration_minutes: int | float | str,
    sets: list[dict[str, Any]] | dict[str, Any] | str,
    subjective_feeling: int | float | str | None = None,
    perceived_effort: int | float | str | None = None,
    confirm: bool | str = False,
    rollback_on_failure: bool | str = True,
    activity_id: str | None = None,
    dry_run: bool | str = False,
) -> dict[str, Any]:
    """Create a Garmin strength activity and attach kg-friendly exercise sets.

    This API-only flow does not need generated Python, TCX, GPX, or FIT files.
    Pass dictated/user-facing exercise names directly in exercise; this tool
    resolves them to Garmin's structured strength catalog internally. Before
    calling this tool, ask the user for start_datetime and duration_minutes if
    they were not provided. Each set should include either exercise, or
    category/name. Optional fields: start_time, offset_seconds, offset_minutes,
    repetitions, weight_kg, duration_seconds, rest_seconds, and set_type.
    set_type defaults to ACTIVE and must be ACTIVE or REST when provided. Use
    dry_run=true to validate mappings and the Garmin exercise-set payload
    without creating an activity. For retries or corrections, pass activity_id
    to update that existing strength activity instead of creating another one.
    If attaching sets fails, rollback_on_failure deletes the just-created empty
    manual activity. Use weight_kg for input. Returned exercise weights are
    weightKg in kg only; Garmin's internal gram values are not returned to MCP
    callers.
    start_time can be a full ISO date-time or a clock time like HH:MM:SS,
    interpreted on the activity date/time zone. Optional subjective_feeling and
    perceived_effort set Garmin's activity-level self evaluation, not per-set
    exercise data.
    """
    try:
        dry_run = _coerce_bool(dry_run)
        confirm = _coerce_bool(confirm)
        rollback_on_failure = _coerce_bool(rollback_on_failure)
        duration_minutes = _coerce_positive_int(duration_minutes, "duration_minutes")
        direct_workout_feel = _coerce_direct_workout_feel(subjective_feeling)
        direct_workout_rpe = _coerce_direct_workout_rpe(perceived_effort)
        if not dry_run:
            require_confirm(
                confirm,
                (
                    "Updating a strength training activity"
                    if activity_id
                    else "Creating a strength training activity"
                ),
            )
        sets = _coerce_strength_sets(sets)
        local_start = _parse_activity_datetime(start_datetime, time_zone)
        exercise_sets, matches = _build_strength_exercise_sets(sets, local_start)
        if dry_run:
            return {
                "done": True,
                "dry_run": True,
                "activity_id": activity_id,
                "matches": matches,
                "exercise_sets": display_strength_exercise_sets(
                    {"activityId": activity_id, "exerciseSets": exercise_sets}
                ),
            }
        if activity_id:
            result = _call("set_activity_exercise_sets", activity_id, exercise_sets)
            self_evaluation = None
            if direct_workout_feel is not None or direct_workout_rpe is not None:
                self_evaluation = as_jsonable(
                    _set_activity_self_evaluation(
                        activity_id,
                        direct_workout_feel,
                        direct_workout_rpe,
                    )
                )
            return {
                "done": True,
                "activity_id": activity_id,
                "updated_existing": True,
                "result": result,
                "matches": matches,
                "self_evaluation": self_evaluation,
                "exercise_sets": display_strength_exercise_sets(
                    _call("get_activity_exercise_sets", activity_id)
                ),
            }
        activity = _call(
            "create_manual_activity",
            _format_garmin_local(local_start),
            time_zone,
            "strength_training",
            0,
            duration_minutes,
            activity_name,
        )
        activity_id = _find_activity_id(activity)
        if not activity_id:
            return {
                "done": False,
                "error": (
                    "Garmin created a manual activity response without an "
                    "activity id."
                ),
                "activity": activity,
            }

        try:
            _call("set_activity_exercise_sets", activity_id, exercise_sets)
            self_evaluation = None
            if direct_workout_feel is not None or direct_workout_rpe is not None:
                self_evaluation = as_jsonable(
                    _set_activity_self_evaluation(
                        activity_id,
                        direct_workout_feel,
                        direct_workout_rpe,
                    )
                )
        except Exception as exc:
            response: dict[str, Any] = {
                "done": False,
                "error": str(exc),
                "activity_id": activity_id,
                "activity": activity,
                "matches": matches,
            }
            if rollback_on_failure:
                try:
                    _call("delete_activity", activity_id)
                    response["rolled_back"] = True
                except Exception as rollback_exc:
                    response["rolled_back"] = False
                    response["rollback_error"] = str(rollback_exc)
            return response
        return {
            "done": True,
            "activity_id": activity_id,
            "activity": activity,
            "matches": matches,
            "self_evaluation": self_evaluation,
            "exercise_sets": display_strength_exercise_sets(
                _call("get_activity_exercise_sets", activity_id)
            ),
        }
    except Exception as exc:
        return {"done": False, "error": str(exc)}


@mcp.tool()
def get_workouts(start: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    """List Garmin workouts."""
    return _call("get_workouts", start, limit)


@mcp.tool()
def get_workout_by_id(workout_id: str) -> dict[str, Any]:
    """Get a Garmin workout by ID."""
    return _call("get_workout_by_id", workout_id)


@mcp.tool()
def download_workout(workout_id: str, output_path: str) -> dict[str, Any]:
    """Download a workout to output_path and return file metadata."""
    data = _call_raw("download_workout", workout_id)
    if not isinstance(data, bytes):
        raise GarminMCPError("Garmin workout download did not return bytes.")
    path = Path(output_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {"path": str(path), "bytes": len(data)}


@mcp.tool()
def upload_workout(
    workout_json: dict[str, Any] | list[Any] | str, confirm: bool = False
) -> dict[str, Any]:
    """Upload a workout JSON payload. Requires confirm=true."""
    require_confirm(confirm, "Uploading a workout")
    return _call("upload_workout", workout_json)


@mcp.tool()
def delete_workout(workout_id: str, confirm: bool = False) -> Any:
    """Delete a Garmin workout. Requires confirm=true."""
    require_confirm(confirm, "Deleting a workout")
    return _call("delete_workout", workout_id)


@mcp.tool()
def schedule_workout(
    workout_id: str, date: str, confirm: bool = False
) -> dict[str, Any]:
    """Schedule a workout for YYYY-MM-DD. Requires confirm=true."""
    require_confirm(confirm, "Scheduling a workout")
    return _call("schedule_workout", workout_id, date)


@mcp.tool()
def unschedule_workout(scheduled_workout_id: str, confirm: bool = False) -> Any:
    """Unschedule a workout. Requires confirm=true."""
    require_confirm(confirm, "Unscheduling a workout")
    return _call("unschedule_workout", scheduled_workout_id)


@mcp.tool()
def get_training_plans() -> dict[str, Any]:
    """List Garmin training plans."""
    return _call("get_training_plans")


@mcp.tool()
def get_goals(
    status: str = "active", start: int = 0, limit: int = 30
) -> list[dict[str, Any]]:
    """Get Garmin goals."""
    return _call("get_goals", status, start, limit)


@mcp.tool()
def get_gear(user_profile_number: str) -> dict[str, Any]:
    """Get Garmin gear for a user profile number."""
    return _call("get_gear", user_profile_number)


@mcp.tool()
def get_gear_stats(gear_uuid: str) -> dict[str, Any]:
    """Get Garmin gear stats."""
    return _call("get_gear_stats", gear_uuid)


@mcp.tool()
def add_gear_to_activity(
    gear_uuid: str, activity_id: str, confirm: bool = False
) -> dict[str, Any]:
    """Attach gear to an activity. Requires confirm=true."""
    require_confirm(confirm, "Adding gear to an activity")
    return _call("add_gear_to_activity", gear_uuid, activity_id)


@mcp.tool()
def remove_gear_from_activity(
    gear_uuid: str, activity_id: str, confirm: bool = False
) -> dict[str, Any]:
    """Remove gear from an activity. Requires confirm=true."""
    require_confirm(confirm, "Removing gear from an activity")
    return _call("remove_gear_from_activity", gear_uuid, activity_id)


@mcp.tool()
def set_gear_default(
    activity_type: str,
    gear_uuid: str,
    default_gear: bool = True,
    confirm: bool = False,
) -> Any:
    """Set or unset default gear for an activity type. Requires confirm=true."""
    require_confirm(confirm, "Changing default gear")
    return _call("set_gear_default", activity_type, gear_uuid, default_gear)


@mcp.tool()
def get_earned_badges() -> list[dict[str, Any]]:
    """Get earned Garmin badges."""
    return _call("get_earned_badges")


@mcp.tool()
def get_available_badges() -> list[dict[str, Any]]:
    """Get available Garmin badges."""
    return _call("get_available_badges")


@mcp.tool()
def get_badge_challenges(start: int = 0, limit: int = 100) -> dict[str, Any]:
    """Get Garmin badge challenges."""
    return _call("get_badge_challenges", start, limit)


@mcp.tool()
def get_nutrition_daily_food_log(date: str) -> dict[str, Any]:
    """Get nutrition food log for YYYY-MM-DD."""
    return _call("get_nutrition_daily_food_log", date)


@mcp.tool()
def get_nutrition_daily_meals(date: str) -> dict[str, Any]:
    """Get nutrition meals for YYYY-MM-DD."""
    return _call("get_nutrition_daily_meals", date)


@mcp.tool()
def get_golf_summary(start: int = 0, limit: int = 100) -> list[dict[str, Any]]:
    """Get golf scorecard summaries."""
    return _call("get_golf_summary", start, limit)


@mcp.tool()
def get_golf_scorecard(scorecard_id: str) -> dict[str, Any]:
    """Get a golf scorecard."""
    return _call("get_golf_scorecard", scorecard_id)


@mcp.tool()
def get_menstrual_data_for_date(date: str) -> dict[str, Any]:
    """Get menstrual data for YYYY-MM-DD."""
    return _call("get_menstrual_data_for_date", date)


@mcp.resource("garmin://profile")
def profile_resource() -> dict[str, Any]:
    """Garmin profile resource."""
    return get_profile()


@mcp.resource("garmin://devices")
def devices_resource() -> list[dict[str, Any]]:
    """Garmin devices resource."""
    return get_devices()


@mcp.resource("garmin://summary/{date}")
def daily_summary_resource(date: str) -> dict[str, Any]:
    """Garmin daily summary resource."""
    return get_daily_summary(date)


@mcp.resource("garmin://activity/{activity_id}")
def activity_resource(activity_id: str) -> dict[str, Any]:
    """Garmin activity resource."""
    return get_activity(activity_id)


@mcp.prompt()
def garmin_health_brief(date: str) -> str:
    """Create a prompt for summarizing Garmin health data for one day."""
    return (
        f"Use the Garmin MCP tools to build a concise health brief for {date}. "
        "Check daily summary, heart rate, sleep, stress, body battery, HRV, "
        "respiration, SpO2, and training readiness when available. Highlight "
        "notable changes, missing data, and practical recovery/training guidance."
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Garmin Connect MCP server.")
    parser.add_argument("--tokenstore", default=None, help="Tokenstore path.")
    parser.add_argument("--log-file", default=None, help="Optional log file path.")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging.")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    configure_logging(args.log_file, args.verbose)
    tokenstore = get_tokenstore_path(args.tokenstore)
    set_provider(GarminClientProvider(tokenstore))
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
