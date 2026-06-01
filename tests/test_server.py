"""Tests for representative MCP server tool behavior."""

from __future__ import annotations

import pytest

from garminconnect_mcp import strength
from garminconnect_mcp.client import GarminMCPError
from garminconnect_mcp.server import (
    create_strength_training_activity,
    get_daily_summary,
    get_device_settings,
    get_device_solar_data,
    list_saved_device_ids,
    match_strength_exercise,
    set_activity_self_evaluation,
    set_activity_name,
    set_activity_strength_exercise_sets,
    set_default_device_id,
    set_provider,
)


class FakeProvider:
    tokenstore = "fake-tokenstore"

    def __init__(self, client: FakeGarmin | None = None) -> None:
        self.client = client or FakeGarmin()

    def get(self) -> FakeGarmin:
        return self.client


class FakeGarmin:
    def __init__(self) -> None:
        self.exercise_sets: list[dict[str, object]] = []
        self.deleted_activity_ids: list[str] = []
        self.created_activities: list[dict[str, object]] = []
        self.self_evaluations: list[dict[str, object]] = []

    def get_user_summary(self, date: str) -> dict[str, object]:
        return {"calendarDate": date, "totalSteps": 1234}

    def get_device_solar_data(
        self, device_id: str, start_date: str, end_date: str | None = None
    ) -> dict[str, object]:
        return {
            "deviceId": device_id,
            "startDate": start_date,
            "endDate": end_date,
            "solarDailyDataDTOs": [],
        }

    def get_device_settings(self, device_id: str) -> dict[str, object]:
        return {"deviceId": device_id, "settings": {}}

    def set_activity_name(self, activity_id: str, title: str) -> dict[str, str]:
        return {"activityId": activity_id, "title": title}

    @staticmethod
    def build_strength_exercise_set(
        category: str,
        name: str,
        start_time: str,
        *,
        repetitions: int | None = None,
        weight_kg: float | None = None,
        duration_seconds: float = 30.0,
        set_type: str = "ACTIVE",
    ) -> dict[str, object]:
        return {
            "exercises": [{"category": category, "name": name, "probability": 100.0}],
            "duration": duration_seconds,
            "repetitionCount": repetitions,
            "weight": weight_kg * 1000 if weight_kg is not None else -1.0,
            "setType": set_type,
            "startTime": start_time,
            "wktStepIndex": None,
            "messageIndex": None,
        }

    def set_activity_exercise_sets(
        self, activity_id: str, exercise_sets: list[dict[str, object]]
    ) -> dict[str, object]:
        self.exercise_sets = exercise_sets
        return {"activityId": activity_id, "exerciseSets": exercise_sets}

    def set_activity_self_evaluation(
        self,
        activity_id: str,
        direct_workout_feel: int | None = None,
        direct_workout_rpe: int | None = None,
    ) -> dict[str, object]:
        payload = {
            "activityId": activity_id,
            "summaryDTO": {
                "directWorkoutFeel": direct_workout_feel,
                "directWorkoutRpe": direct_workout_rpe,
            },
        }
        self.self_evaluations.append(payload)
        return payload

    def delete_activity(self, activity_id: str) -> dict[str, object]:
        self.deleted_activity_ids.append(activity_id)
        return {"activityId": activity_id, "deleted": True}

    def create_manual_activity(
        self,
        start_datetime: str,
        time_zone: str,
        type_key: str,
        distance_km: float,
        duration_min: int,
        activity_name: str,
    ) -> dict[str, object]:
        self.created_activities.append(
            {
                "activityName": activity_name,
                "startTimeLocal": start_datetime,
                "timeZone": time_zone,
            }
        )
        return {
            "activityId": "manual-42",
            "activityName": activity_name,
            "startTimeLocal": start_datetime,
            "timeZone": time_zone,
            "typeKey": type_key,
            "distanceKm": distance_km,
            "durationMin": duration_min,
        }

    def get_activity_exercise_sets(self, activity_id: str) -> dict[str, object]:
        return {"activityId": activity_id, "exerciseSets": self.exercise_sets}

    def get_activity(self, activity_id: str) -> dict[str, object]:
        return {
            "activityId": activity_id,
            "summaryDTO": {"startTimeGMT": "2026-05-10T12:00:00.0"},
        }


def setup_module() -> None:
    set_provider(FakeProvider())  # type: ignore[arg-type]


def test_read_tool_calls_garmin_method() -> None:
    assert get_daily_summary("2026-05-10") == {
        "calendarDate": "2026-05-10",
        "totalSteps": 1234,
    }


def test_device_solar_uses_saved_default_device_id(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GARMINCONNECT_MCP_CONFIG", str(tmp_path / "config.json"))

    assert set_default_device_id("device-123")["default_device_id"] == "device-123"
    result = get_device_solar_data("2026-05-10")

    assert result["deviceId"] == "device-123"
    assert list_saved_device_ids()["known_device_ids"] == ["device-123"]


def test_device_settings_uses_saved_default_device_id(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GARMINCONNECT_MCP_CONFIG", str(tmp_path / "config.json"))

    set_default_device_id("device-settings-123")
    result = get_device_settings()

    assert result["deviceId"] == "device-settings-123"


def test_device_solar_remembers_explicit_device_id(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GARMINCONNECT_MCP_CONFIG", str(tmp_path / "config.json"))

    result = get_device_solar_data("2026-05-10", device_id="device-456")

    assert result["deviceId"] == "device-456"
    assert list_saved_device_ids()["default_device_id"] == "device-456"


def test_write_tool_requires_confirm() -> None:
    with pytest.raises(GarminMCPError, match="confirm=true"):
        set_activity_name("42", "Morning Run")


def test_write_tool_runs_when_confirmed() -> None:
    assert set_activity_name("42", "Morning Run", confirm=True) == {
        "activityId": "42",
        "title": "Morning Run",
    }


def test_set_activity_strength_exercise_sets_accepts_kg_specs() -> None:
    result = set_activity_strength_exercise_sets(
        "42",
        [
            {
                "exercise": "back squats",
                "start_time": "2026-05-10T12:10:00.0",
                "repetitions": 8,
                "weight_kg": 70,
            }
        ],
        confirm=True,
    )

    assert result["matches"][0]["name"] == "BARBELL_BACK_SQUAT"
    assert result["exercise_sets"]["exerciseSets"][0]["weightKg"] == 70
    assert result["exercise_sets"]["exerciseSets"][0]["weightUnit"] == "kg"
    assert "weight" not in result["exercise_sets"]["exerciseSets"][0]
    assert result["done"] is True


def test_set_activity_strength_exercise_sets_defaults_blank_set_type() -> None:
    result = set_activity_strength_exercise_sets(
        "42",
        [
            {
                "exercise": "hammer curl",
                "start_time": "2026-05-10T12:10:00.0",
                "repetitions": 10,
                "weight_kg": 12,
                "set_type": None,
            }
        ],
        confirm=True,
    )

    assert result["done"] is True
    assert result["matches"][0]["name"] == "DUMBBELL_HAMMER_CURL"
    assert result["exercise_sets"]["exerciseSets"][0]["setType"] == "ACTIVE"


def test_match_strength_exercise_finds_close_garmin_exercise() -> None:
    result = match_strength_exercise("nordic curls")

    assert result["category"] == "LEG_CURL"
    assert result["name"] == "LEG_CURL"


def test_match_strength_exercise_handles_shoulder_aliases() -> None:
    assert match_strength_exercise("shoulder flies") == {
        "category": "LATERAL_RAISE",
        "name": "DUMBBELL_LATERAL_RAISE",
        "matched_from": "shoulder flies",
        "match_type": "alias",
    }
    assert match_strength_exercise("reverse flies on machine")["name"] == (
        "INCLINE_REVERSE_FLYE"
    )


def test_match_strength_exercise_uses_catalog_for_varied_phrasing() -> None:
    cable_reverse = match_strength_exercise("reverse flys cable")
    back_dumbbells = match_strength_exercise("back flies with dumbbells")

    assert cable_reverse["category"] == "FLYE"
    assert cable_reverse["name"] == "SINGLE_ARM_STANDING_CABLE_REVERSE_FLYE"
    assert cable_reverse["match_type"] == "catalog"
    assert back_dumbbells["category"] == "FLYE"


def test_match_strength_exercise_has_common_gym_aliases() -> None:
    assert match_strength_exercise("lever front body weight")["name"] == (
        "MODIFIED_FRONT_LEVER"
    )
    assert match_strength_exercise("Front Lever (Bodyweight)")["name"] == (
        "MODIFIED_FRONT_LEVER"
    )
    assert match_strength_exercise("Hanging Leg Raises")["name"] == (
        "HANGING_LEG_RAISE"
    )
    assert match_strength_exercise("Hammer Curl")["name"] == "DUMBBELL_HAMMER_CURL"
    assert match_strength_exercise("Incline Bench Press (Smith Machine)")[
        "name"
    ] == "INCLINE_SMITH_MACHINE_BENCH_PRESS"
    assert match_strength_exercise("Pec Fly Machine")["name"] == "DUMBBELL_FLYE"
    assert match_strength_exercise("adductor machine") == {
        "category": "HIP_STABILITY",
        "name": "SLIDING_HIP_ADDUCTION",
        "matched_from": "adductor machine",
        "match_type": "alias",
    }
    assert match_strength_exercise("hip adduction machine")["name"] == (
        "SLIDING_HIP_ADDUCTION"
    )
    assert match_strength_exercise("Biceps curl")["name"] == "BARBELL_BICEPS_CURL"


def test_strength_aliases_are_in_packaged_catalog() -> None:
    local_catalog = strength._load_catalog_payload_exercises(
        strength._load_local_catalog_payload()
    )

    missing = {
        alias: exercise
        for alias, exercise in strength.GARMIN_STRENGTH_EXERCISES.items()
        if exercise not in local_catalog
    }

    assert missing == {}


def test_match_strength_exercise_rejects_low_confidence_matches() -> None:
    with pytest.raises(ValueError, match="No confident Garmin strength exercise match"):
        match_strength_exercise("completely imaginary moon press")


def test_match_strength_exercise_uses_packaged_catalog(monkeypatch: pytest.MonkeyPatch) -> None:
    strength._load_catalog_exercises.cache_clear()
    monkeypatch.setattr(strength, "_load_remote_catalog_payload", lambda: {})
    try:
        result = match_strength_exercise("alternating dumbbell chest press")
    finally:
        strength._load_catalog_exercises.cache_clear()

    assert result["category"] == "BENCH_PRESS"
    assert result["name"] == "ALTERNATING_DUMBBELL_CHEST_PRESS"


def test_create_strength_training_activity_is_api_only_and_kg_friendly() -> None:
    result = create_strength_training_activity(
        "Gym Strength",
        "2026-05-10T14:00:00.000",
        "Europe/Budapest",
        90,
        [
            {
                "exercise": "hip thrust machine",
                "repetitions": 8,
                "weight_kg": 70,
            }
        ],
        confirm=True,
    )

    assert result["activity_id"] == "manual-42"
    assert result["done"] is True
    assert result["activity"]["typeKey"] == "strength_training"
    assert result["matches"][0]["name"] == "BARBELL_HIP_THRUST_WITH_BENCH"
    assert result["exercise_sets"]["exerciseSets"][0]["weightKg"] == 70
    assert "weight" not in result["exercise_sets"]["exerciseSets"][0]


def test_set_activity_self_evaluation_maps_labels_and_rpe() -> None:
    fake = FakeGarmin()
    set_provider(FakeProvider(fake))  # type: ignore[arg-type]
    try:
        result = set_activity_self_evaluation(
            "manual-42",
            subjective_feeling="normal",
            perceived_effort=7,
            confirm=True,
        )
    finally:
        set_provider(FakeProvider())  # type: ignore[arg-type]

    assert result["done"] is True
    assert result["direct_workout_feel"] == 50
    assert result["direct_workout_rpe"] == 70
    assert fake.self_evaluations == [
        {
            "activityId": "manual-42",
            "summaryDTO": {
                "directWorkoutFeel": 50,
                "directWorkoutRpe": 70,
            },
        }
    ]


def test_set_activity_self_evaluation_returns_json_for_empty_garmin_response() -> None:
    class EmptyResponse:
        status_code = 204

    class FakeClient:
        def request(self, *args: object, **kwargs: object) -> EmptyResponse:
            return EmptyResponse()

    class NoHelperGarmin:
        client = FakeClient()

    fake = NoHelperGarmin()
    set_provider(FakeProvider(fake))  # type: ignore[arg-type]
    try:
        result = set_activity_self_evaluation(
            "23076983509",
            subjective_feeling="normal",
            perceived_effort=7,
            confirm=True,
        )
    finally:
        set_provider(FakeProvider())  # type: ignore[arg-type]

    assert result["done"] is True
    assert result["result"] == {
        "status_code": 204,
        "payload": {
            "activityId": 23076983509,
            "summaryDTO": {
                "directWorkoutFeel": 50,
                "directWorkoutRpe": 70,
            },
        },
    }


def test_create_strength_training_activity_sets_self_evaluation() -> None:
    fake = FakeGarmin()
    set_provider(FakeProvider(fake))  # type: ignore[arg-type]
    try:
        result = create_strength_training_activity(
            "Gym Strength",
            "2026-05-10T14:00:00.000",
            "Europe/Budapest",
            90,
            [{"exercise": "squat", "repetitions": 8, "weight_kg": 70}],
            subjective_feeling="strong",
            perceived_effort=8,
            confirm=True,
        )
    finally:
        set_provider(FakeProvider())  # type: ignore[arg-type]

    assert result["done"] is True
    assert result["self_evaluation"]["summaryDTO"] == {
        "directWorkoutFeel": 75,
        "directWorkoutRpe": 80,
    }
    assert fake.self_evaluations[0]["activityId"] == "manual-42"


def test_create_strength_training_activity_dry_run_does_not_write() -> None:
    fake = FakeGarmin()
    set_provider(FakeProvider(fake))  # type: ignore[arg-type]
    try:
        result = create_strength_training_activity(
            "Gym Strength",
            "2026-05-10T14:00:00.000",
            "Europe/Budapest",
            90,
            [{"exercise": "adductor machine", "repetitions": 10, "weight_kg": 30}],
            dry_run=True,
        )
    finally:
        set_provider(FakeProvider())  # type: ignore[arg-type]

    assert result["done"] is True
    assert result["dry_run"] is True
    assert result["matches"][0]["name"] == "SLIDING_HIP_ADDUCTION"
    assert result["exercise_sets"]["exerciseSets"][0]["weightKg"] == 30
    assert fake.created_activities == []
    assert fake.exercise_sets == []


def test_create_strength_training_activity_updates_existing_activity_id() -> None:
    fake = FakeGarmin()
    set_provider(FakeProvider(fake))  # type: ignore[arg-type]
    try:
        result = create_strength_training_activity(
            "Gym Strength",
            "2026-05-10T14:00:00.000",
            "Europe/Budapest",
            90,
            [{"exercise": "adductor machine", "repetitions": 10, "weight_kg": 30}],
            subjective_feeling="normal",
            perceived_effort=8,
            activity_id="existing-99",
            confirm=True,
        )
    finally:
        set_provider(FakeProvider())  # type: ignore[arg-type]

    assert result["done"] is True
    assert result["updated_existing"] is True
    assert result["activity_id"] == "existing-99"
    assert result["matches"][0]["name"] == "SLIDING_HIP_ADDUCTION"
    assert fake.created_activities == []
    assert fake.exercise_sets[0]["exercises"][0]["name"] == "SLIDING_HIP_ADDUCTION"
    assert fake.self_evaluations[0]["activityId"] == "existing-99"


def test_set_activity_strength_exercise_sets_dry_run_fills_missing_start_time() -> None:
    fake = FakeGarmin()
    set_provider(FakeProvider(fake))  # type: ignore[arg-type]
    try:
        result = set_activity_strength_exercise_sets(
            "existing-99",
            [{"exercise": "adductor machine", "repetitions": 10, "weight_kg": 30}],
            dry_run=True,
        )
    finally:
        set_provider(FakeProvider())  # type: ignore[arg-type]

    assert result["done"] is True
    assert result["dry_run"] is True
    assert result["matches"][0]["name"] == "SLIDING_HIP_ADDUCTION"
    assert result["exercise_sets"]["exerciseSets"][0]["startTime"] == (
        "2026-05-10T12:00:00.0"
    )
    assert fake.exercise_sets == []


def test_create_strength_training_activity_accepts_clock_time_set_starts() -> None:
    result = create_strength_training_activity(
        "Shoulder Strength",
        "2026-05-09T07:00:00.000",
        "Europe/Vienna",
        60,
        [
            {
                "exercise": "BARBELL_SHOULDER_PRESS",
                "repetitions": 10,
                "start_time": "07:04:00",
                "weight_kg": "50",
            }
        ],
        confirm=True,
    )

    exercise_set = result["exercise_sets"]["exerciseSets"][0]
    assert result["done"] is True
    assert exercise_set["startTime"] == "2026-05-09T05:04:00.0"
    assert result["exercise_sets"]["exerciseSets"][0]["weightKg"] == 50


def test_create_strength_training_activity_accepts_name_only_sets() -> None:
    result = create_strength_training_activity(
        "Morning Strength Training",
        "2026-05-09T07:00:00",
        "UTC",
        60,
        [
            {
                "name": "Shoulder press",
                "repetitions": 10,
                "sets": 4,
                "start_time": "07:00:00",
                "weight_kg": 50,
            },
            {
                "name": "Shoulder flies",
                "repetitions": 10,
                "sets": 3,
                "start_time": "07:15:00",
                "weight_kg": 14,
            },
            {
                "name": "Reverse flies on machine",
                "repetitions": 12,
                "sets": 3,
                "start_time": "07:30:00",
                "weight_kg": 20,
            },
            {
                "name": "Sit-ups",
                "repetitions": 25,
                "sets": 4,
                "start_time": "07:45:00",
                "weight_kg": 0,
            },
        ],
        confirm=True,
    )

    assert result["done"] is True
    assert len(result["exercise_sets"]["exerciseSets"]) == 14
    assert result["matches"][0]["name"] == "BARBELL_SHOULDER_PRESS"
    assert result["matches"][4]["name"] == "DUMBBELL_LATERAL_RAISE"
    assert result["matches"][7]["name"] == "INCLINE_REVERSE_FLYE"
    assert result["matches"][10]["name"] == "SIT_UP"


def test_create_strength_training_activity_preflights_set_validation() -> None:
    fake = FakeGarmin()
    set_provider(FakeProvider(fake))  # type: ignore[arg-type]
    try:
        result = create_strength_training_activity(
            "Broken Strength",
            "2026-05-09T07:00:00",
            "UTC",
            60,
            [{"repetitions": 10, "start_time": "07:00:00"}],
            confirm=True,
        )
    finally:
        set_provider(FakeProvider())  # type: ignore[arg-type]

    assert result["done"] is False
    assert "must include exercise, name, or category/name" in result["error"]
    assert fake.created_activities == []


def test_create_strength_training_activity_preflights_invalid_set_type() -> None:
    fake = FakeGarmin()
    set_provider(FakeProvider(fake))  # type: ignore[arg-type]
    try:
        result = create_strength_training_activity(
            "Broken Strength",
            "2026-05-09T07:00:00",
            "UTC",
            60,
            [
                {
                    "exercise": "squat",
                    "repetitions": 10,
                    "set_type": "workout",
                }
            ],
            confirm=True,
        )
    finally:
        set_provider(FakeProvider())  # type: ignore[arg-type]

    assert result["done"] is False
    assert "set_type must be ACTIVE or REST" in result["error"]
    assert fake.created_activities == []


def test_create_strength_training_activity_preflights_unknown_exercise() -> None:
    fake = FakeGarmin()
    set_provider(FakeProvider(fake))  # type: ignore[arg-type]
    try:
        result = create_strength_training_activity(
            "Broken Strength",
            "2026-05-09T07:00:00",
            "UTC",
            60,
            [{"exercise": "completely imaginary moon press", "repetitions": 10}],
            confirm=True,
        )
    finally:
        set_provider(FakeProvider())  # type: ignore[arg-type]

    assert result["done"] is False
    assert "No confident Garmin strength exercise match" in result["error"]
    assert fake.created_activities == []


def test_create_strength_training_activity_accepts_sets_json_string() -> None:
    result = create_strength_training_activity(
        "Gym Strength",
        "2026-05-10T14:00:00.000",
        "Europe/Budapest",
        90,
        '[{"exercise":"squat","repetitions":8,"weight_kg":70}]',
        confirm=True,
    )

    assert result["done"] is True
    assert result["matches"][0]["name"] == "BARBELL_BACK_SQUAT"
    assert result["exercise_sets"]["exerciseSets"][0]["weightKg"] == 70


def test_create_strength_training_activity_coerces_cloud_client_strings() -> None:
    result = create_strength_training_activity(
        "Gym Strength",
        "2026-05-10T14:00:00.000",
        "Europe/Budapest",
        "90",
        {"exercise": "squat", "repetitions": 8, "weight_kg": 70},
        confirm="true",
        rollback_on_failure="true",
    )

    assert result["done"] is True
    assert result["activity"]["durationMin"] == 90
    assert result["matches"][0]["name"] == "BARBELL_BACK_SQUAT"


def test_create_strength_training_activity_rejects_plain_string_sets() -> None:
    result = create_strength_training_activity(
        "Gym Strength",
        "2026-05-10T14:00:00.000",
        "Europe/Budapest",
        90,
        "3",
        confirm=True,
    )

    assert result["done"] is False
    assert "sets must be a list" in result["error"]


def test_create_strength_training_activity_returns_done_false_on_garmin_error() -> None:
    class ErrorGarmin(FakeGarmin):
        def create_manual_activity(
            self,
            start_datetime: str,
            time_zone: str,
            type_key: str,
            distance_km: float,
            duration_min: int,
            activity_name: str,
        ) -> dict[str, object]:
            return {"error": "Internal Server Error (ref: test)"}

    set_provider(FakeProvider(ErrorGarmin()))  # type: ignore[arg-type]
    try:
        result = create_strength_training_activity(
            "Gym Strength",
            "2026-05-10T14:00:00.000",
            "Europe/Budapest",
            90,
            [{"exercise": "squat", "repetitions": 8, "weight_kg": 70}],
            confirm=True,
        )
    finally:
        set_provider(FakeProvider())  # type: ignore[arg-type]

    assert result["done"] is False
    assert "activity id" in result["error"]
    assert result["activity"] == {"error": "Internal Server Error (ref: test)"}


def test_create_strength_training_activity_rolls_back_when_sets_fail() -> None:
    class ErrorOnSetsGarmin(FakeGarmin):
        def set_activity_exercise_sets(
            self, activity_id: str, exercise_sets: list[dict[str, object]]
        ) -> dict[str, object]:
            raise RuntimeError("ValueInstantiationException")

    fake = ErrorOnSetsGarmin()
    set_provider(FakeProvider(fake))  # type: ignore[arg-type]
    try:
        result = create_strength_training_activity(
            "Shoulder & Core Workout",
            "2026-05-09T08:00:00.000",
            "Europe/Budapest",
            60,
            [{"exercise": "shoulder flies", "repetitions": 10, "weight_kg": 14}],
            confirm=True,
        )
    finally:
        set_provider(FakeProvider())  # type: ignore[arg-type]

    assert result["done"] is False
    assert result["rolled_back"] is True
    assert fake.deleted_activity_ids == ["manual-42"]


def test_create_strength_training_activity_rematches_human_labels() -> None:
    result = create_strength_training_activity(
        "Shoulder & Core Strength",
        "2026-05-09T07:00:00.000",
        "Europe/Budapest",
        60,
        [
            {
                "category": "SHOULDER_PRESS",
                "name": "Shoulder Press",
                "repetitions": 10,
                "weight_kg": 50,
            },
            {
                "category": "SHOULDER_FLIES",
                "name": "Shoulder Flies",
                "repetitions": 10,
                "weight_kg": 14,
            },
            {
                "category": "REVERSE_FLYS",
                "name": "Reverse Flies on Machine",
                "repetitions": 12,
                "weight_kg": 20,
            },
            {"category": "SIT_UP", "name": "Sit Ups", "repetitions": 25},
        ],
        confirm=True,
    )

    assert result["done"] is True
    assert result["matches"][0]["category"] == "SHOULDER_PRESS"
    assert result["matches"][0]["name"] == "BARBELL_SHOULDER_PRESS"
    assert result["matches"][1]["category"] == "LATERAL_RAISE"
    assert result["matches"][2]["category"] == "FLYE"
    assert result["matches"][3]["name"] == "SIT_UP"


def test_create_strength_training_activity_expands_sets_and_zero_weight() -> None:
    result = create_strength_training_activity(
        "Core",
        "2026-05-09T07:35:00.000",
        "Europe/Budapest",
        20,
        [
            {
                "category": "SIT_UP",
                "name": "Sit Ups",
                "repetitions": 25,
                "sets": 4,
                "start_time": "2026-05-09T07:35:00",
                "weight_kg": 0,
            }
        ],
        confirm=True,
    )

    exercise_sets = result["exercise_sets"]["exerciseSets"]
    assert result["done"] is True
    assert len(exercise_sets) == 4
    assert result["matches"][0]["name"] == "SIT_UP"
    assert exercise_sets[0]["startTime"] == "2026-05-09T05:35:00.0"
    assert all("weight" not in item for item in exercise_sets)
    assert all("weightKg" not in item for item in exercise_sets)


def test_create_strength_training_activity_treats_zero_weight_as_bodyweight() -> None:
    result = create_strength_training_activity(
        "Core",
        "2026-05-09T07:35:00.000",
        "Europe/Budapest",
        20,
        [
            {
                "exercise": "WEIGHTED_SIT_UP",
                "repetitions": 25,
                "start_time": "07:40:00",
                "weight_kg": 0,
            }
        ],
        confirm=True,
    )

    exercise_set = result["exercise_sets"]["exerciseSets"][0]
    assert result["done"] is True
    assert result["matches"][0]["name"] == "SIT_UP"
    assert result["matches"][0]["weighted_name"] == "WEIGHTED_SIT_UP"
    assert exercise_set["exercises"][0]["name"] == "SIT_UP"
    assert "weight" not in exercise_set
    assert "weightKg" not in exercise_set
