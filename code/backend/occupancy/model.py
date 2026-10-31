"""The current state of every slot of a station. No images, nothing about people."""

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from enum import StrEnum


class SlotState(StrEnum):
    FREE = "free"
    TAKEN = "taken"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SlotOccupancy:
    number: int
    state: SlotState = SlotState.UNKNOWN
    confidence: float | None = None
    changed_at: datetime | None = None
    reported_at: datetime | None = None
    # An unsure reading waits here until a second reading agrees with it.
    pending_taken: bool | None = None
    # The last report came from the simulator (simulation/simulator.py), not from a camera.
    simulated: bool = False

    def current_state(self, now: datetime, stale_after: timedelta) -> SlotState:
        """The state, or unknown once no camera has reported the slot for stale_after."""
        if self.reported_at is None or now - self.reported_at > stale_after:
            return SlotState.UNKNOWN
        return self.state

    def reported(self, at: datetime, simulated: bool = False) -> "SlotOccupancy":
        return replace(self, reported_at=at, simulated=simulated)


@dataclass(frozen=True)
class StationOccupancy:
    station_id: str
    slots: Mapping[int, SlotOccupancy] = field(default_factory=dict)
    # Counts saves, so two writers cannot overwrite each other unnoticed.
    version: int = 0

    def slot(self, number: int) -> SlotOccupancy:
        return self.slots.get(number) or SlotOccupancy(number)

    def with_slots(self, updated: Mapping[int, SlotOccupancy]) -> "StationOccupancy":
        return replace(self, slots={**self.slots, **updated})

    def last_report(self) -> datetime | None:
        reports = [slot.reported_at for slot in self.slots.values() if slot.reported_at is not None]
        return max(reports, default=None)
