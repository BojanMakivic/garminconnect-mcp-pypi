"""Garmin Connect authentication setup CLI for garminconnect-mcp."""

from __future__ import annotations

import argparse
import os
import sys
from getpass import getpass
from pathlib import Path

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from .client import get_tokenstore_path, redact_secrets


def _prompt_mfa() -> str:
    return input("MFA code: ").strip()


def authenticate(email: str, password: str, tokenstore: Path) -> None:
    """Authenticate with Garmin and write reusable tokens."""
    garmin = Garmin(email=email, password=password, prompt_mfa=_prompt_mfa)
    garmin.login(str(tokenstore))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create Garmin Connect tokens for garminconnect-mcp."
    )
    parser.add_argument(
        "--tokenstore",
        default=None,
        help="Token directory or file. Defaults to GARMINTOKENS or ~/.garminconnect.",
    )
    parser.add_argument("--email", default=None, help="Garmin account email.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    tokenstore = get_tokenstore_path(args.tokenstore)
    email = args.email or os.getenv("EMAIL") or input("Garmin email: ").strip()
    password = os.getenv("PASSWORD") or getpass("Garmin password: ")

    if not email or not password:
        print("Email and password are required.", file=sys.stderr)
        return 2

    try:
        authenticate(email, password, tokenstore)
    except GarminConnectTooManyRequestsError as exc:
        print(f"Garmin rate limited the login: {redact_secrets(exc)}", file=sys.stderr)
        return 3
    except GarminConnectAuthenticationError as exc:
        print(f"Garmin authentication failed: {redact_secrets(exc)}", file=sys.stderr)
        return 4
    except GarminConnectConnectionError as exc:
        print(f"Garmin connection failed: {redact_secrets(exc)}", file=sys.stderr)
        return 5

    print(f"Garmin tokens saved to: {tokenstore}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
