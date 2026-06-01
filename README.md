# garmin-connect-mcp-server

[![PyPI - Version](https://img.shields.io/pypi/v/garmin-connect-mcp-server)](https://pypi.org/project/garmin-connect-mcp-server/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)

![garmin mcp](https://github.com/user-attachments/assets/7d7bd126-ff3d-45d1-9013-7db89b629a7c)

A local Model Context Protocol (MCP) server for Garmin Connect App.

This project wraps the Python `garminconnect` package and exposes Garmin
Connect data and selected account actions to MCP-capable clients such as Msty
Studio, Claude Desktop, and other local stdio MCP clients.

## Important auth note

Garmin authentication stays local on each user's machine. Do not commit or copy
Garmin tokens into this repository.

By default, tokens are stored in:

```text
C:\Users\YOUR_WINDOWS_USERNAME\.garminconnect
```

The MCP server uses those local tokens when your desktop AI app starts it.

## Install from a GitHub clone on Windows

Use this flow when you cloned the repository from GitHub and want to run the
local project in Msty Studio, Claude Desktop, or another stdio MCP client.

Open PowerShell and run:

```powershell
cd C:\Users\YOUR_WINDOWS_USERNAME
git clone https://github.com/BojanMakivic/garminconnect-mcp-pypi.git
cd garminconnect-mcp-pypi
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
```

Python 3.12 also works:

```powershell
py -3.12 -m venv .venv
```

Use the real folder where you cloned the project if it is not directly under
`C:\Users\YOUR_WINDOWS_USERNAME`.

## First-time Garmin authentication

Run this once in a normal PowerShell terminal:

```powershell
cd C:\Users\YOUR_WINDOWS_USERNAME\garminconnect-mcp-pypi
.\.venv\Scripts\garmin-connect-mcp-server-auth.exe
```

The auth command prompts for Garmin credentials and MFA if Garmin requires it.
It stores tokens in `GARMINTOKENS` or, by default, in:

```text
C:\Users\YOUR_WINDOWS_USERNAME\.garminconnect
```

The MCP server itself never prompts on stdin. For stdio MCP servers,
stdout/stdin are reserved for protocol messages.

## Test the local server

After authenticating, this command should start the MCP server:

```powershell
cd C:\Users\YOUR_WINDOWS_USERNAME\garminconnect-mcp-pypi
.\.venv\Scripts\garmin-connect-mcp-server.exe --tokenstore C:\Users\YOUR_WINDOWS_USERNAME\.garminconnect
```

It will wait for MCP protocol input. Stop it with `Ctrl+C`.

## Msty Studio setup

Msty Studio should launch the local virtual environment executable directly.
Do not rely on `garmin-connect-mcp-server` being available on PATH inside the desktop
app.

In Msty Studio, add a local stdio JSON tool with:

```json
{
  "command": "C:\\Users\\YOUR_WINDOWS_USERNAME\\garminconnect-mcp-pypi\\.venv\\Scripts\\garmin-connect-mcp-server.exe",
  "args": [
    "--tokenstore",
    "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect"
  ],
  "env": {
    "GARMINTOKENS": "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect",
    "GARMINCONNECT_MCP_CONFIG": "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect-mcp\\config.json"
  }
}
```

Replace `YOUR_WINDOWS_USERNAME` with your Windows username. If you cloned the
repo somewhere else, replace the project path too.

See [docs/msty-studio.md](docs/msty-studio.md) for the focused Msty setup page.

## Claude Desktop setup

Claude Desktop uses an `mcpServers` wrapper around the same command:

```json
{
  "mcpServers": {
    "garminconnect": {
      "command": "C:\\Users\\YOUR_WINDOWS_USERNAME\\garminconnect-mcp-pypi\\.venv\\Scripts\\garmin-connect-mcp-server.exe",
      "args": [
        "--tokenstore",
        "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect"
      ],
      "env": {
        "GARMINTOKENS": "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect",
        "GARMINCONNECT_MCP_CONFIG": "C:\\Users\\YOUR_WINDOWS_USERNAME\\.garminconnect-mcp\\config.json"
      }
    }
  }
}
```

See [docs/claude-desktop.md](docs/claude-desktop.md) for the focused Claude
Desktop setup page.

## Other stdio MCP clients

Use the same executable and tokenstore:

```text
command: C:\Users\YOUR_WINDOWS_USERNAME\garminconnect-mcp-pypi\.venv\Scripts\garmin-connect-mcp-server.exe
args: --tokenstore C:\Users\YOUR_WINDOWS_USERNAME\.garminconnect
```

If the client supports environment variables, set:

```text
GARMINTOKENS=C:\Users\YOUR_WINDOWS_USERNAME\.garminconnect
GARMINCONNECT_MCP_CONFIG=C:\Users\YOUR_WINDOWS_USERNAME\.garminconnect-mcp\config.json
```

## PyPI and uvx usage

If you are installing the published package instead of running from a clone,
you can use:

```powershell
pip install garmin-connect-mcp-server
garmin-connect-mcp-server-auth
garmin-connect-mcp-server
```

Or run it with `uvx`:

```powershell
uvx --from garmin-connect-mcp-server garmin-connect-mcp-server-auth
uvx garmin-connect-mcp-server
```

`uvx garmin-connect-mcp-server` works directly because the PyPI package and server
command have the same name. The auth command is provided by the same package,
so it uses `--from garmin-connect-mcp-server`.

For a GitHub clone, the full `.venv\Scripts\garmin-connect-mcp-server.exe` path is more
reliable in desktop apps because they often do not inherit your terminal PATH.

## Quick inspector test

To quickly test the published package using the Model Context Protocol
inspector tool, run:

```powershell
npx @modelcontextprotocol/inspector uvx garmin-connect-mcp-server
```

## Exposed tools

The MCP server exposes the following tools grouped by category.

### Status & Profile

| Tool | Description |
|------|-------------|
| `garmin_status` | Check authentication status and token info |
| `get_profile` | Fetch the athlete's Garmin profile |
| `get_user_settings` | Fetch user account settings |

### Devices

| Tool | Description |
|------|-------------|
| `get_devices` | List all connected Garmin devices |
| `list_saved_device_ids` | Show remembered device IDs |
| `set_default_device_id` | Set a default device for device tools |
| `get_primary_training_device` | Get the primary training device |
| `get_device_solar_data` | Get solar charging data for a device |
| `get_device_settings` | Get settings for a device |

### Daily Health & Wellness

| Tool | Description |
|------|-------------|
| `get_daily_summary` | Daily health summary for a date |
| `get_daily_stats` | Detailed daily stats for a date |
| `get_steps_data` | Step data for a date |
| `get_daily_steps` | Step data over a date range |
| `get_floors` | Floors climbed for a date |
| `get_heart_rates` | Heart rate data for a date |
| `get_sleep_data` | Sleep data for a date |
| `get_stress_data` | Stress level data for a date |
| `get_hrv_data` | HRV (heart rate variability) data for a date |
| `get_body_battery` | Body Battery energy data for a date range |
| `get_body_battery_events` | Body Battery events for a date |
| `get_respiration_data` | Respiration/breathing data for a date |
| `get_spo2_data` | Blood oxygen (SpO2) data for a date |

### Nutrition & Body Metrics

| Tool | Description |
|------|-------------|
| `get_hydration_data` | Hydration data for a date |
| `add_hydration_data` | Log hydration intake |
| `get_body_composition` | Body composition data for a date range |
| `get_weigh_ins` | Weight-in records for a date range |
| `add_weigh_in` | Add a weight entry |
| `delete_weigh_in` | Delete a weight entry (`confirm=true` required) |
| `get_blood_pressure` | Blood pressure records |
| `set_blood_pressure` | Log a blood pressure reading |
| `delete_blood_pressure` | Delete a blood pressure entry (`confirm=true` required) |
| `get_nutrition_daily_food_log` | Daily food log for a date |
| `get_nutrition_daily_meals` | Daily meals for a date |

### Training & Performance

| Tool | Description |
|------|-------------|
| `get_training_readiness` | Training readiness score for a date |
| `get_training_status` | Training status for a date |
| `get_endurance_score` | Endurance score for a date range |
| `get_hill_score` | Hill score for a date range |
| `get_race_predictions` | Race time predictions |
| `get_lactate_threshold` | Lactate threshold data |

### Activities

| Tool | Description |
|------|-------------|
| `count_activities` | Total number of recorded activities |
| `list_activities` | Paginated list of activities |
| `get_activities_by_date` | Activities in a date range |
| `get_activity` | Full details for a single activity |
| `get_activity_details` | Extended activity details |
| `get_activity_splits` | Lap/split data for an activity |
| `get_activity_weather` | Weather data for an activity |
| `get_activity_gear` | Gear used in an activity |
| `download_activity` | Download an activity file (FIT, TCX, GPX, KML, CSV) |
| `set_activity_name` | Rename an activity (`confirm=true` required) |
| `delete_activity` | Delete an activity (`confirm=true` required) |
| `upload_activity` | Upload an activity file (`confirm=true` required) |
| `import_activity` | Import an activity file (`confirm=true` required) |
| `set_activity_type` | Change the activity type (`confirm=true` required) |
| `set_activity_self_evaluation` | Set activity-level subjective feeling and perceived effort (`confirm=true` required) |

### Strength Training

| Tool | Description |
|------|-------------|
| `get_activity_exercise_sets` | Get exercise sets for a strength activity |
| `match_strength_exercise` | Look up a Garmin exercise by name |
| `set_activity_strength_exercise_sets` | Update exercise sets on a strength activity (`confirm=true` required unless `dry_run=true`) |
| `create_strength_training_activity` | Create a new strength training activity, or update `activity_id` when provided (`confirm=true` required unless `dry_run=true`) |

#### Strength exercise sets

Strength tools use Garmin's structured strength-training exercise-set API. You
can pass human-friendly exercise names such as `back squats`, `hip thrust
machine`, or `shoulder flies`; the server matches them to Garmin's exercise
catalog before sending the activity update.

This is handled inside the MCP server. MCP clients should call
`create_strength_training_activity` or `set_activity_strength_exercise_sets`
directly with structured JSON; no generated Python helper script is required.
For a new strength activity, the client should ask for `start_datetime` and
`duration_minutes` before calling the tool if the user did not provide them.
Use `dry_run=true` for mapping or payload checks; it returns the resolved Garmin
exercise sets without creating or changing an activity. If a create attempt
needs to be retried or corrected, pass the existing `activity_id` to
`create_strength_training_activity` or call `set_activity_strength_exercise_sets`
so the existing activity is updated instead of creating another activity.

The matcher normalizes punctuation, filler words, plural forms, common equipment
terms, and token order before comparing the user phrase with Garmin's catalog.
If it cannot find a confident match, the tool returns an error before creating
or changing an activity instead of guessing a random exercise.

The Garmin exercise catalog is packaged locally at
`garminconnect_mcp/data/Exercises.json`, so normal matching does not depend on
live network access. The source catalog is Garmin's public web data file at
`https://connect.garmin.com/web-data/exercises/Exercises.json`; refresh the
packaged file when Garmin adds or renames exercises.

Set input supports:

| Field | Description |
|-------|-------------|
| `exercise` | Human-friendly exercise name to match against Garmin's catalog |
| `category` / `name` | Exact or near-exact Garmin category/name pair |
| `sets` | Repeat the same set spec this many times |
| `start_time` | ISO date-time or clock time such as `07:04:00`; when omitted, sets are spaced from the activity start |
| `offset_seconds` / `offset_minutes` | Start offset from activity start when `start_time` is omitted |
| `repetitions` | Repetition count |
| `weight_kg` | Weight in kilograms; `0`, blank, or omitted is treated as bodyweight/no weight |
| `duration_seconds` | Set duration, defaulting to 30 seconds |
| `rest_seconds` | Rest before the next auto-offset set, defaulting to 90 seconds |
| `set_type` | Garmin set type, `ACTIVE` or `REST`; blank or omitted defaults to `ACTIVE` |

Example strength activity:

```json
{
  "activity_name": "Gym Strength",
  "start_datetime": "2026-05-29T20:45:00",
  "time_zone": "Europe/Budapest",
  "duration_minutes": 60,
  "sets": [
    {
      "exercise": "barbell row",
      "sets": 3,
      "repetitions": 10,
      "weight_kg": 60
    },
    {
      "exercise": "pull ups",
      "sets": 4,
      "repetitions": 8,
      "weight_kg": 0
    }
  ],
  "confirm": true
}
```

When updating an existing activity instead of creating a new one:

```json
{
  "activity_name": "Gym Strength",
  "activity_id": "23059996606",
  "start_datetime": "2026-05-29T20:45:00",
  "time_zone": "Europe/Budapest",
  "duration_minutes": 60,
  "sets": [
    {
      "exercise": "adductor machine",
      "sets": 3,
      "repetitions": 10,
      "weight_kg": 30
    }
  ],
  "confirm": true
}
```

#### Activity self evaluation

Garmin stores perceived effort and subjective feeling as activity-level self
evaluation fields, not as per-exercise or per-set data. The MCP exposes this in
two ways:

| Tool | Use |
|------|-----|
| `set_activity_self_evaluation` | Update self evaluation on an existing activity |
| `create_strength_training_activity` | Optionally set self evaluation immediately after creating the strength activity |

Use `subjective_feeling` for Garmin's five feeling choices:

| Input | Garmin value |
|-------|--------------|
| `very_weak` | 0 |
| `weak` | 25 |
| `normal` | 50 |
| `strong` | 75 |
| `very_strong` | 100 |

Use `perceived_effort` for the user-facing RPE scale from `0` to `10`. The
server converts it to Garmin's internal `directWorkoutRpe` scale from `0` to
`100`; for example, RPE `8` is stored as `80`.

Example self evaluation update:

```json
{
  "activity_id": "23059996606",
  "subjective_feeling": "normal",
  "perceived_effort": 8,
  "confirm": true
}
```

Example strength activity with self evaluation:

```json
{
  "activity_name": "Back Strength Training",
  "start_datetime": "2026-05-29T20:45:00",
  "time_zone": "Europe/Budapest",
  "duration_minutes": 60,
  "sets": [
    {
      "exercise": "bent over row",
      "sets": 3,
      "repetitions": 10,
      "weight_kg": 60
    }
  ],
  "subjective_feeling": "normal",
  "perceived_effort": 8,
  "confirm": true
}
```

### Workouts

| Tool | Description |
|------|-------------|
| `get_workouts` | List saved workouts |
| `get_workout_by_id` | Get a specific workout |
| `download_workout` | Download a workout file |
| `upload_workout` | Upload a workout (`confirm=true` required) |
| `delete_workout` | Delete a workout (`confirm=true` required) |
| `schedule_workout` | Schedule a workout for a date (`confirm=true` required) |
| `unschedule_workout` | Unschedule a workout (`confirm=true` required) |
| `get_training_plans` | List available training plans |

### Goals, Gear & Badges

| Tool | Description |
|------|-------------|
| `get_goals` | List goals |
| `get_gear` | Gear registered to a user profile |
| `get_gear_stats` | Stats for a specific gear item |
| `add_gear_to_activity` | Link gear to an activity (`confirm=true` required) |
| `remove_gear_from_activity` | Unlink gear from an activity (`confirm=true` required) |
| `set_gear_default` | Set default gear for an activity type (`confirm=true` required) |
| `get_earned_badges` | Badges the user has earned |
| `get_available_badges` | All available badges |
| `get_badge_challenges` | Active badge challenges |

### Golf & Other Sports

| Tool | Description |
|------|-------------|
| `get_golf_summary` | Golf round summary list |
| `get_golf_scorecard` | Scorecard for a specific golf round |
| `get_menstrual_data_for_date` | Menstrual cycle data for a date |

## Resources

The server also exposes the following MCP resources:

| Resource | Description |
|----------|-------------|
| `garmin://profile` | Current user profile |
| `garmin://devices` | List of connected devices |
| `garmin://summary/{date}` | Daily summary for a date |
| `garmin://activity/{activity_id}` | Activity details |

## Prompts

| Prompt | Description |
|--------|-------------|
| `garmin_health_brief` | Generate a natural-language health brief for a given date |

## Development install

For development tools and tests:

```powershell
cd C:\Users\YOUR_WINDOWS_USERNAME\garminconnect-mcp-pypi
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest --basetemp .pytest-tmp
```

If you are developing a local checkout of `python-garminconnect` too, install
that package into the same virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ..\python-garminconnect
```

## Safety

Tokens are used only inside the local server process. They are never returned
by tools or resources, and are redacted from error strings. All mutating tools
(write/delete operations) require an explicit `confirm=true` argument to prevent
accidental changes.

## Contributing

Contributions are welcome. Please open issues or pull requests that include a
clear description and tests where applicable.

## License

This project is licensed under the GNU General Public License v3.0 or later.
See the `LICENSE` file for details.
