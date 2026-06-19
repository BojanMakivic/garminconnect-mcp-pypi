# Changelog

All notable changes to Garmin Connect MCP Server are documented here.

## 0.1.11

### Fixed

- Added Python-version-specific `garminconnect` constraints: Python 3.10 and
  3.11 use `garminconnect>=0.2.40,<0.3.3`, while Python 3.12+ uses
  `garminconnect>=0.3.3`.

## 0.1.10

### Changed

- Expanded the supported Python range to `>=3.10,<3.15`.
- Added package classifiers for Python 3.10, 3.11, and 3.14.

## 0.1.9

### Changed

- --

## 0.1.8

### Changed

- Few minor improvements. 

## 0.1.7

### Changed

- Few minor fixes. 

## 0.1.6

### Changed

- Bumped the package version after the `0.1.6` release workflow/tag correction.
- Updated README badge and package presentation details.

## 0.1.5

### Fixed

- Made structured Garmin strength-set uploads independent from a local
  `python-garminconnect` checkout.
- Added an internal fallback that writes Garmin exercise sets through the
  Garmin client HTTP endpoint when the installed `garminconnect` package does
  not expose `set_activity_exercise_sets`.

### Added

- Added regression coverage for the clean PyPI install case where
  `set_activity_exercise_sets` is missing from the upstream client.

## 0.1.4

### Fixed

- Fixed PyPI badges and README image links for the published package page.

## 0.1.3

### Changed

- Cleaned up the PyPI project heading and README presentation.

## 0.1.2

### Changed

- Reworked the README to focus on `uvx` usage for PyPI installs.
- Removed Windows `.exe` launcher instructions from the PyPI-focused setup.

## 0.1.1

### Changed

- Renamed the published package to `garmin-connect-mcp-server`.
- Added PyPI entry points for:
  - `garmin-connect-mcp-server`
  - `garmin-connect-mcp-server-auth`

## 0.1.0

### Added

- Initial Garmin Connect MCP Server package structure.
- Added Garmin authentication and stdio MCP server commands.
- Added Garmin health, activity, device, gear, workout, and strength-training
  MCP tools.
