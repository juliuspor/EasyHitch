"""Simulated occupancy for the slots no camera reports: a working day compressed into minutes.

For the demo, and for stations that have no camera yet. The simulator writes
through the same OccupancyRepository and decide() rule as the Ingest API, so
the Availability API, the MCP server and the app read a simulated slot like a
reported one. A slot that a camera has reported within stale_after belongs to
the camera, and the simulator leaves it alone until it goes stale. It always
leaves one of a station's slots free, so no station it fills reads full. Each slot
stores whether the simulator reported it last, so the simulator keeps no state
of its own and can run as a fresh Lambda invocation every minute.
"""

import math
import random
import threading
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from classification.classifier import Reading
from logs import log_event
from occupancy.decider import decide
from occupancy.model import SlotOccupancy, SlotState, StationOccupancy
from occupancy.repository import ConcurrentUpdate, OccupancyRepository
from stations.catalog import Station, StationCatalog

DAY = timedelta(minutes=10)  # one simulated working day, so a demo sees the racks fill and empty
STEP = timedelta(seconds=8)  # slow enough to follow each change on the map
QUIET, BUSY = 0.15, 0.9  # share of slots taken at night and at the busiest time of the day
CHURN = 0.3  # chance per step that one rider leaves while another arrives


class OccupancySimulator:
    def __init__(self, catalog: StationCatalog, occupancy: OccupancyRepository, stale_after: timedelta,
                 day: timedelta = DAY, rng: random.Random | None = None) -> None:
        self._catalog = catalog
        self._occupancy = occupancy
        self._stale_after = stale_after
        self._day = day
        self._rng = rng or random.Random()

    def target(self, station_index: int, now: datetime) -> float:
        """Share of a station's slots taken at `now`: quiet at night, busiest in the middle of the day.

        Each station runs a little ahead of the previous one, so they do not fill in lockstep.
        """
        time_of_day = (now.timestamp() / self._day.total_seconds() + station_index * 0.07) % 1
        return QUIET + (BUSY - QUIET) * math.sin(math.pi * time_of_day) ** 2

    def step(self, now: datetime) -> int:
        """Moves every station's simulated slots one step towards the time of day; returns how many changed."""
        now = now.replace(microsecond=0)
        changed = 0
        for index, station in enumerate(self._catalog.all()):
            # The Ingest API may save the same station meanwhile; retry once on what it wrote.
            try:
                changed += self._step_station(station, self.target(index, now), now)
            except ConcurrentUpdate:
                changed += self._step_station(station, self.target(index, now), now)
        return changed

    def run(self, stop: threading.Event, step: timedelta = STEP) -> None:
        while not stop.is_set():
            self.step(datetime.now(UTC))
            stop.wait(step.total_seconds())

    def start(self) -> threading.Event:
        """Runs the simulation in a background thread until the returned event is set."""
        stop = threading.Event()
        threading.Thread(target=self.run, args=(stop,), name="occupancy-simulator", daemon=True).start()
        log_event("simulation_started", day_seconds=int(self._day.total_seconds()))
        return stop

    def _step_station(self, station: Station, target: float, now: datetime) -> int:
        current = self._occupancy.get(station.id) or StationOccupancy(station.id)
        slots = {slot.number: current.slot(slot.number) for slot in station.slots}
        simulated = [number for number, slot in slots.items() if self._is_simulated(slot, now)]
        if not simulated:
            return 0

        taken = {number for number in simulated if slots[number].state is SlotState.TAKEN}
        for number in simulated:
            # A slot new to the simulation starts as the time of day suggests.
            if slots[number].state is SlotState.UNKNOWN and self._rng.random() < target:
                taken.add(number)
        wanted = min(round(target * len(simulated)), len(simulated) - 1)
        if len(taken) < wanted:
            taken.add(self._pick([n for n in simulated if n not in taken]))
        elif len(taken) > wanted:
            taken.discard(self._pick(sorted(taken)))
        elif taken and len(taken) < len(simulated) and self._rng.random() < CHURN:
            leaving = self._pick(sorted(taken))
            taken.add(self._pick([n for n in simulated if n not in taken]))
            taken.discard(leaving)

        updated = {}
        for number in simulated:
            reading = Reading(taken=number in taken, confidence=1.0)
            updated[number] = decide(slots[number], reading, now).reported(now, simulated=True)
        self._occupancy.save(current.with_slots(updated))
        return sum(1 for number in simulated if updated[number].state != slots[number].state)

    def _is_simulated(self, slot: SlotOccupancy, now: datetime) -> bool:
        """Never reported, gone stale, or last reported by the simulator, not by a camera."""
        return slot.reported_at is None or now - slot.reported_at > self._stale_after or slot.simulated

    def _pick(self, numbers: Sequence[int]) -> int:
        return self._rng.choice(numbers)
