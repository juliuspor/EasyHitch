"""Backend configuration, read once from the environment and checked at start.

A profile picks a complete set of implementations: `local` runs on a laptop
with nothing but this folder, `aws` uses DynamoDB, SSM and Jev. A single
setting overrides one choice, so the real classifier can run locally while
everything else stays local. BACKEND_SIMULATION=on lets the local server
simulate the slots no camera reports (simulation/simulator.py).
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

CHOICES = {
    "classifier": ("static", "jev"),
    "storage": ("memory", "dynamodb"),
    "cameras": ("file", "ssm"),
    "simulation": ("off", "on"),
}
PROFILES = {
    "local": {"classifier": "static", "storage": "memory", "cameras": "file", "simulation": "off"},
    "aws": {"classifier": "jev", "storage": "dynamodb", "cameras": "ssm", "simulation": "off"},
}


class SettingsError(ValueError):
    """The environment describes a setup the backend cannot run with."""


@dataclass(frozen=True)
class Settings:
    profile: str
    classifier: str
    storage: str
    cameras: str
    simulation: str
    stale_after: timedelta
    jev_model: str
    decisions_url: str
    openrouter_api_key: str | None
    openrouter_api_key_parameter: str | None
    camera_tokens_parameter: str | None
    occupancy_table: str | None
    fingerprint_table: str | None
    data_dir: Path = DATA_DIR

    def __post_init__(self) -> None:
        problems = []
        for name, allowed in CHOICES.items():
            if getattr(self, name) not in allowed:
                problems.append(f"BACKEND_{name.upper()} must be one of {', '.join(allowed)}")
        if self.classifier == "jev" and not (self.openrouter_api_key or self.openrouter_api_key_parameter):
            problems.append("the jev classifier needs OPENROUTER_API_KEY or OPENROUTER_API_KEY_PARAMETER")
        if self.storage == "dynamodb" and not (self.occupancy_table and self.fingerprint_table):
            problems.append("dynamodb storage needs OCCUPANCY_TABLE and FINGERPRINT_TABLE")
        if self.cameras == "ssm" and not self.camera_tokens_parameter:
            problems.append("ssm cameras need CAMERA_TOKENS_PARAMETER")
        if self.stale_after <= timedelta(0):
            problems.append("STALE_AFTER_SECONDS must be positive")
        if problems:
            raise SettingsError(". ".join(problems))

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] = os.environ) -> "Settings":
        profile = environ.get("BACKEND_PROFILE", "local")
        if profile not in PROFILES:
            raise SettingsError(f"BACKEND_PROFILE must be one of {', '.join(PROFILES)}, not {profile!r}")
        choices = {
            name: environ.get(f"BACKEND_{name.upper()}", default)
            for name, default in PROFILES[profile].items()
        }
        try:
            stale_after = timedelta(seconds=int(environ.get("STALE_AFTER_SECONDS", "600")))
        except ValueError as error:
            raise SettingsError("STALE_AFTER_SECONDS must be a whole number of seconds") from error
        return cls(
            profile=profile,
            **choices,
            stale_after=stale_after,
            jev_model=environ.get("JEV_MODEL", "typesafe/jev-1.14"),
            decisions_url=environ.get("DECISIONS_URL", "https://openrouter.ai/api/alpha/decisions"),
            openrouter_api_key=environ.get("OPENROUTER_API_KEY") or None,
            openrouter_api_key_parameter=environ.get("OPENROUTER_API_KEY_PARAMETER") or None,
            camera_tokens_parameter=environ.get("CAMERA_TOKENS_PARAMETER") or None,
            occupancy_table=environ.get("OCCUPANCY_TABLE") or None,
            fingerprint_table=environ.get("FINGERPRINT_TABLE") or None,
        )
