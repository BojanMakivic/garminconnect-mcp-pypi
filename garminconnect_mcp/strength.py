"""Helpers for Garmin structured strength training payloads."""

import json
import re
from difflib import SequenceMatcher, get_close_matches
from functools import lru_cache
from importlib import resources
from typing import Any
from urllib.error import URLError
from urllib.request import Request, urlopen

GARMIN_EXERCISE_CATALOG_URL = (
    "https://connect.garmin.com/web-data/exercises/Exercises.json"
)
LOCAL_EXERCISE_CATALOG = "Exercises.json"

GARMIN_STRENGTH_EXERCISES: dict[str, tuple[str, str]] = {
    "back squat": ("SQUAT", "BARBELL_BACK_SQUAT"),
    "barbell back squat": ("SQUAT", "BARBELL_BACK_SQUAT"),
    "squat": ("SQUAT", "BARBELL_BACK_SQUAT"),
    "front squat": ("SQUAT", "BARBELL_FRONT_SQUAT"),
    "leg press": ("SQUAT", "LEG_PRESS"),
    "nordic curl": ("LEG_CURL", "LEG_CURL"),
    "nordic hamstring curl": ("LEG_CURL", "LEG_CURL"),
    "hamstring curl": ("LEG_CURL", "LEG_CURL"),
    "leg curl": ("LEG_CURL", "LEG_CURL"),
    "leg extension": ("BANDED_EXERCISES", "LEG_EXTENSION"),
    "single leg leg extension": ("BANDED_EXERCISES", "LEG_EXTENSION"),
    "one leg leg extension": ("BANDED_EXERCISES", "LEG_EXTENSION"),
    "calf raise": ("CALF_RAISE", "WEIGHTED_STANDING_CALF_RAISE"),
    "calf raises": ("CALF_RAISE", "WEIGHTED_STANDING_CALF_RAISE"),
    "standing calf raise": ("CALF_RAISE", "WEIGHTED_STANDING_CALF_RAISE"),
    "leg press calf raise": ("CALF_RAISE", "WEIGHTED_STANDING_CALF_RAISE"),
    "front lever": ("CORE", "MODIFIED_FRONT_LEVER"),
    "front lever bodyweight": ("CORE", "MODIFIED_FRONT_LEVER"),
    "bodyweight front lever": ("CORE", "MODIFIED_FRONT_LEVER"),
    "modified front lever": ("CORE", "MODIFIED_FRONT_LEVER"),
    "hanging leg raise": ("LEG_RAISE", "HANGING_LEG_RAISE"),
    "hanging leg raises": ("LEG_RAISE", "HANGING_LEG_RAISE"),
    "leg raise": ("LEG_RAISE", "LEG_RAISE"),
    "leg raises": ("LEG_RAISE", "LEG_RAISE"),
    "hip thrust": ("HIP_RAISE", "BARBELL_HIP_THRUST_WITH_BENCH"),
    "hip thrust machine": ("HIP_RAISE", "BARBELL_HIP_THRUST_WITH_BENCH"),
    "barbell hip thrust": ("HIP_RAISE", "BARBELL_HIP_THRUST_WITH_BENCH"),
    "adductor": ("HIP_STABILITY", "SLIDING_HIP_ADDUCTION"),
    "adductors": ("HIP_STABILITY", "SLIDING_HIP_ADDUCTION"),
    "adductor machine": ("HIP_STABILITY", "SLIDING_HIP_ADDUCTION"),
    "hip adduction": ("HIP_STABILITY", "SLIDING_HIP_ADDUCTION"),
    "hip adduction machine": ("HIP_STABILITY", "SLIDING_HIP_ADDUCTION"),
    "sliding hip adduction": ("HIP_STABILITY", "SLIDING_HIP_ADDUCTION"),
    "standing adduction": ("HIP_STABILITY", "STANDING_ADDUCTION"),
    "leg adduction": ("BANDED_EXERCISES", "LEG_ADDUCTION"),
    "sit up": ("SIT_UP", "WEIGHTED_SIT_UP"),
    "sit-up": ("SIT_UP", "WEIGHTED_SIT_UP"),
    "sit ups": ("SIT_UP", "WEIGHTED_SIT_UP"),
    "weighted sit up": ("SIT_UP", "WEIGHTED_SIT_UP"),
    "decline sit up": ("SIT_UP", "WEIGHTED_SIT_UP"),
    "bench press": ("BENCH_PRESS", "BARBELL_BENCH_PRESS"),
    "barbell bench press": ("BENCH_PRESS", "BARBELL_BENCH_PRESS"),
    "dumbbell bench press": ("BENCH_PRESS", "DUMBBELL_BENCH_PRESS"),
    "incline bench press smith machine": (
        "BENCH_PRESS",
        "INCLINE_SMITH_MACHINE_BENCH_PRESS",
    ),
    "incline smith machine bench press": (
        "BENCH_PRESS",
        "INCLINE_SMITH_MACHINE_BENCH_PRESS",
    ),
    "smith machine incline bench press": (
        "BENCH_PRESS",
        "INCLINE_SMITH_MACHINE_BENCH_PRESS",
    ),
    "shoulder press": ("SHOULDER_PRESS", "BARBELL_SHOULDER_PRESS"),
    "machine shoulder press": ("SHOULDER_PRESS", "BARBELL_SHOULDER_PRESS"),
    "dumbbell shoulder press": ("SHOULDER_PRESS", "DUMBBELL_SHOULDER_PRESS"),
    "overhead press": ("SHOULDER_PRESS", "BARBELL_SHOULDER_PRESS"),
    "shoulder flies": ("LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE"),
    "shoulder fly": ("LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE"),
    "lateral raise": ("LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE"),
    "lateral raises": ("LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE"),
    "dumbbell lateral raise": ("LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE"),
    "reverse flies": ("FLYE", "INCLINE_REVERSE_FLYE"),
    "reverse fly": ("FLYE", "INCLINE_REVERSE_FLYE"),
    "reverse flies on machine": ("FLYE", "INCLINE_REVERSE_FLYE"),
    "reverse fly machine": ("FLYE", "INCLINE_REVERSE_FLYE"),
    "rear delt fly": ("FLYE", "INCLINE_REVERSE_FLYE"),
    "rear delt flies": ("FLYE", "INCLINE_REVERSE_FLYE"),
    "pec fly": ("FLYE", "DUMBBELL_FLYE"),
    "pec fly machine": ("FLYE", "DUMBBELL_FLYE"),
    "chest fly": ("SUSPENSION", "CHEST_FLY"),
    "lat pulldown": ("PULL_UP", "LAT_PULLDOWN"),
    "pull down": ("PULL_UP", "LAT_PULLDOWN"),
    "pullup": ("PULL_UP", "PULL_UP"),
    "pull up": ("PULL_UP", "PULL_UP"),
    "row": ("ROW", "SEATED_CABLE_ROW"),
    "seated row": ("ROW", "SEATED_CABLE_ROW"),
    "cable row": ("ROW", "SEATED_CABLE_ROW"),
    "deadlift": ("DEADLIFT", "BARBELL_DEADLIFT"),
    "romanian deadlift": ("DEADLIFT", "BARBELL_STRAIGHT_LEG_DEADLIFT"),
    "biceps curl": ("CURL", "BARBELL_BICEPS_CURL"),
    "barbell curl": ("CURL", "BARBELL_BICEPS_CURL"),
    "dumbbell curl": ("CURL", "ALTERNATING_DUMBBELL_BICEPS_CURL"),
    "hammer curl": ("CURL", "DUMBBELL_HAMMER_CURL"),
    "dumbbell hammer curl": ("CURL", "DUMBBELL_HAMMER_CURL"),
    "triceps pushdown": ("TRICEPS_EXTENSION", "TRICEPS_PRESSDOWN"),
    "tricep pushdown": ("TRICEPS_EXTENSION", "TRICEPS_PRESSDOWN"),
    "plank": ("PLANK", "PLANK"),
}

NORMALIZED_GARMIN_STRENGTH_EXERCISES: dict[str, tuple[str, str]] = {}
SORTED_GARMIN_STRENGTH_EXERCISES: dict[str, tuple[str, str]] = {}
MATCH_NOISE_TOKENS = {
    "bodyweight",
    "body",
    "weight",
    "weighted",
    "exercise",
    "movement",
    "on",
    "rep",
    "reps",
    "the",
    "with",
}

FALLBACK_CATALOG_EXERCISES: tuple[tuple[str, str], ...] = tuple(
    sorted(
        {
            *GARMIN_STRENGTH_EXERCISES.values(),
            ("FLYE", "SINGLE_ARM_STANDING_CABLE_REVERSE_FLYE"),
            ("FLYE", "KNEELING_REAR_FLYE"),
            ("FLYE", "INCLINE_REVERSE_FLYE"),
            ("FLYE", "DUMBBELL_FLYE"),
            ("SUSPENSION", "CHEST_FLY"),
            ("CORE", "MODIFIED_FRONT_LEVER"),
            ("HIP_STABILITY", "SLIDING_HIP_ADDUCTION"),
            ("HIP_STABILITY", "STANDING_ADDUCTION"),
            ("BANDED_EXERCISES", "LEG_ADDUCTION"),
            ("LEG_RAISE", "HANGING_LEG_RAISE"),
            ("LEG_RAISE", "LEG_RAISE"),
            ("CURL", "DUMBBELL_HAMMER_CURL"),
            ("BENCH_PRESS", "INCLINE_SMITH_MACHINE_BENCH_PRESS"),
            ("SIT_UP", "SIT_UP"),
            ("LATERAL_RAISE", "DUMBBELL_LATERAL_RAISE"),
            ("LATERAL_RAISE", "BENT_OVER_LATERAL_RAISE"),
            ("LATERAL_RAISE", "SEATED_REAR_LATERAL_RAISE"),
            ("SHOULDER_PRESS", "SEATED_DUMBBELL_SHOULDER_PRESS"),
            ("SHOULDER_PRESS", "SMITH_MACHINE_OVERHEAD_PRESS"),
        }
    )
)


def _canonical_token(value: str) -> str:
    synonyms = {
        "flies": "flye",
        "flys": "flye",
        "fly": "flye",
        "flyes": "flye",
        "dumbbells": "dumbbell",
        "db": "dumbbell",
        "barbells": "barbell",
        "situps": "sit",
        "situp": "sit",
        "pulldown": "pull",
        "pull-down": "pull",
    }
    value = synonyms.get(value, value)
    if len(value) > 3 and value.endswith("s"):
        value = value[:-1]
    return value


def normalize_exercise_name(value: str) -> str:
    """Normalize a dictated exercise name for matching."""
    normalized = value.lower().replace("_", " ").replace("-", " ")
    normalized = re.sub(r"\bbody\s+weight\b", "bodyweight", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    tokens = [_canonical_token(token) for token in normalized.split()]
    return " ".join(tokens)


def _dedupe_tokens(value: str) -> str:
    seen: set[str] = set()
    tokens: list[str] = []
    for token in value.split():
        if token not in seen:
            seen.add(token)
            tokens.append(token)
    return " ".join(tokens)


def _sorted_tokens(value: str) -> str:
    return " ".join(sorted(value.split()))


def _without_noise_tokens(value: str) -> str:
    return " ".join(
        token for token in value.split() if token not in MATCH_NOISE_TOKENS
    )


def _query_variants(query: str) -> tuple[str, ...]:
    variants = {_dedupe_tokens(query)}
    stripped = _dedupe_tokens(_without_noise_tokens(query))
    if stripped:
        variants.add(stripped)
    return tuple(sorted(variants))


def _normalized_aliases() -> dict[str, tuple[str, str]]:
    if not NORMALIZED_GARMIN_STRENGTH_EXERCISES:
        NORMALIZED_GARMIN_STRENGTH_EXERCISES.update(
            {
                normalize_exercise_name(alias): exercise
                for alias, exercise in GARMIN_STRENGTH_EXERCISES.items()
            }
        )
    return NORMALIZED_GARMIN_STRENGTH_EXERCISES


def _sorted_aliases() -> dict[str, tuple[str, str]]:
    if not SORTED_GARMIN_STRENGTH_EXERCISES:
        SORTED_GARMIN_STRENGTH_EXERCISES.update(
            {
                _sorted_tokens(normalize_exercise_name(alias)): exercise
                for alias, exercise in GARMIN_STRENGTH_EXERCISES.items()
            }
        )
    return SORTED_GARMIN_STRENGTH_EXERCISES


def _catalog_label(category: str, name: str) -> str:
    return _dedupe_tokens(normalize_exercise_name(f"{category} {name}"))


def _catalog_labels(category: str, name: str) -> tuple[str, ...]:
    labels = {
        _catalog_label(category, name),
        _dedupe_tokens(normalize_exercise_name(name)),
        _dedupe_tokens(normalize_exercise_name(name.removeprefix("WEIGHTED_"))),
    }
    labels.update(_query_variants(_catalog_label(category, name)))
    labels.update(_query_variants(_dedupe_tokens(normalize_exercise_name(name))))
    return tuple(label for label in sorted(labels) if label)


@lru_cache(maxsize=1)
def _load_catalog_exercises() -> tuple[tuple[str, str], ...]:
    catalog = set(FALLBACK_CATALOG_EXERCISES)
    catalog.update(_load_catalog_payload_exercises(_load_local_catalog_payload()))
    if len(catalog) > len(FALLBACK_CATALOG_EXERCISES):
        return tuple(sorted(catalog))
    catalog.update(_load_catalog_payload_exercises(_load_remote_catalog_payload()))
    return tuple(sorted(catalog))


def _load_local_catalog_payload() -> dict[str, Any]:
    try:
        catalog = resources.files("garminconnect_mcp.data").joinpath(
            LOCAL_EXERCISE_CATALOG
        )
        return json.loads(catalog.read_text(encoding="utf-8"))
    except (FileNotFoundError, ModuleNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _load_remote_catalog_payload() -> dict[str, Any]:
    try:
        request = Request(
            GARMIN_EXERCISE_CATALOG_URL,
            headers={"User-Agent": "garminconnect-mcp/0.1"},
        )
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, TimeoutError, json.JSONDecodeError):
        return {}


def _load_catalog_payload_exercises(payload: dict[str, Any]) -> set[tuple[str, str]]:
    catalog: set[tuple[str, str]] = set()
    categories = payload.get("categories", {})
    if not isinstance(categories, dict):
        return catalog
    for category, category_payload in categories.items():
        if not isinstance(category_payload, dict):
            continue
        exercises = category_payload.get("exercises", {})
        if not isinstance(exercises, dict):
            continue
        for exercise_name in exercises:
            catalog.add((str(category), str(exercise_name)))
    return catalog


def _score_catalog_match(query: str, category: str, name: str) -> float:
    best = 0.0
    for variant in _query_variants(query):
        for label in _catalog_labels(category, name):
            best = max(best, _score_label_match(variant, label))
    return best


def _score_label_match(query: str, label: str) -> float:
    query_tokens = set(query.split())
    label_tokens = set(label.split())
    if not query_tokens:
        return 0.0
    shared = query_tokens & label_tokens
    if not shared:
        return 0.0
    query_overlap = len(shared) / len(query_tokens)
    jaccard = len(shared) / len(query_tokens | label_tokens)
    sequence = SequenceMatcher(
        None,
        _sorted_tokens(query),
        _sorted_tokens(label),
    ).ratio()
    subset_bonus = (
        0.2 if len(query_tokens) > 1 and query_tokens <= label_tokens else 0.0
    )
    score = (
        (query_overlap * 0.55)
        + (jaccard * 0.25)
        + (sequence * 0.2)
        + subset_bonus
    )
    return min(score, 1.0)


def _best_from_catalog(
    query: str, catalog: tuple[tuple[str, str], ...]
) -> tuple[float, str, str] | None:
    best: tuple[float, str, str] | None = None
    for category, name in catalog:
        score = _score_catalog_match(query, category, name)
        if best is None or score > best[0]:
            best = (score, category, name)
    return best


def _catalog_match_result(best: tuple[float, str, str] | None) -> dict[str, str] | None:
    if best is None or best[0] < 0.58:
        return None
    score, category, name = best
    return {
        "category": category,
        "name": name,
        "matched_label": _catalog_label(category, name),
        "match_score": f"{score:.3f}",
        "match_type": "catalog",
    }


def _best_catalog_match(query: str) -> dict[str, str] | None:
    query = _dedupe_tokens(query)
    fallback_best = _best_from_catalog(query, FALLBACK_CATALOG_EXERCISES)
    if fallback_best and fallback_best[0] >= 0.65:
        return _catalog_match_result(fallback_best)
    catalog_best = _best_from_catalog(query, _load_catalog_exercises())
    if catalog_best and (fallback_best is None or catalog_best[0] >= fallback_best[0]):
        return _catalog_match_result(catalog_best)
    return _catalog_match_result(fallback_best)


def resolve_strength_exercise(value: str) -> dict[str, str]:
    """Return the closest Garmin category/name pair for a dictated exercise."""
    normalized = _dedupe_tokens(normalize_exercise_name(value))
    aliases = _normalized_aliases()
    if normalized in aliases:
        category, name = aliases[normalized]
        return {
            "category": category,
            "name": name,
            "matched_from": value,
            "match_type": "alias",
        }
    sorted_aliases = _sorted_aliases()
    sorted_normalized = _sorted_tokens(normalized)
    if sorted_normalized in sorted_aliases:
        category, name = sorted_aliases[sorted_normalized]
        return {
            "category": category,
            "name": name,
            "matched_from": value,
            "matched_alias": sorted_normalized,
            "match_type": "alias_token_order",
        }

    catalog_match = _best_catalog_match(normalized)
    if catalog_match:
        return {
            **catalog_match,
            "matched_from": value,
        }

    candidates = get_close_matches(
        normalized, aliases.keys(), n=1, cutoff=0.55
    )
    if candidates:
        category, name = aliases[candidates[0]]
        return {
            "category": category,
            "name": name,
            "matched_from": value,
            "matched_alias": candidates[0],
            "match_type": "fuzzy",
        }

    raise ValueError(f"No confident Garmin strength exercise match for: {value}")


def is_known_strength_exercise(category: str, name: str) -> bool:
    """Return whether category/name is a Garmin catalog exercise pair."""
    pair = (category, name)
    return pair in set(_load_catalog_exercises()) or pair in set(
        FALLBACK_CATALOG_EXERCISES
    )


def display_strength_exercise_sets(value: Any) -> Any:
    """Return exercise sets with weights shown only as kilograms for LLMs.

    Garmin stores structured strength weights in grams internally, but MCP
    callers should see kg values only to avoid reporting Garmin internals back
    to users.
    """
    if isinstance(value, dict):
        converted = {
            str(key): display_strength_exercise_sets(item)
            for key, item in value.items()
        }
        weight = value.get("weight")
        converted.pop("weight", None)
        if isinstance(weight, int | float) and weight >= 0:
            converted["weightKg"] = weight / 1000.0
            converted["weightUnit"] = "kg"
        return converted
    if isinstance(value, list):
        return [display_strength_exercise_sets(item) for item in value]
    return value
