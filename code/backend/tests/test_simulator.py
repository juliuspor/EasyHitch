"""The simulator fills the slots no camera reports, follows the time of day, never overrides a camera,
and runs the same way as a scheduled Lambda function."""

import random
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

import composition
from ingest.service import _needs_reading
from occupancy.dynamodb import _item, _occupancy, _slot
from occupancy.model import SlotOccupancy, SlotState, StationOccupancy
from occupancy.repository import InMemoryOccupancyRepository
from settings import Settings, SettingsError
from simulation import handler
from simulation.simulator import BUSY, DAY, QUIET, STEP, OccupancySimulator
from stations.catalog import Location, Slot, Station, StationCatalog

# Midday UTC is a whole number of simulated days since the epoch: the quiet start of a day.
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
STALE_AFTER = timedelta(minutes=10)


def garage(slots: int) -> StationCatalog:
    here = Location(lat=47.4886, lon=7.5984)
    return StationCatalog([Station(id="garage", name="Garage", location=here,
                                   slots=tuple(Slot(number=n, location=here) for n in range(1, slots + 1)))])


def simulate(slots: int, stored: StationOccupancy | None = None) -> tuple[OccupancySimulator, InMemoryOccupancyRepository]:
    repository = InMemoryOccupancyRepository()
    if stored:
        repository.save(stored)
    return OccupancySimulator(garage(slots), repository, STALE_AFTER, rng=random.Random(7)), repository


def test_fills_every_slot_of_a_station_without_a_camera():
    simulator, repository = simulate(20)
    simulator.step(NOW)
    slots = repository.get("garage").slots
    assert sorted(slots) == list(range(1, 21))
    assert all(slot.state is not SlotState.UNKNOWN and slot.reported_at == NOW for slot in slots.values())


def test_follows_the_time_of_day():
    simulator, repository = simulate(40)
    busiest = NOW + DAY / 2
    assert simulator.target(0, NOW) == pytest.approx(QUIET)
    assert simulator.target(0, busiest) == pytest.approx(BUSY)
    for _ in range(60):  # one slot per step at most, so give it time to get there
        simulator.step(busiest)
    taken = [slot for slot in repository.get("garage").slots.values() if slot.state is SlotState.TAKEN]
    assert len(taken) == round(BUSY * 40)


def test_leaves_a_slot_a_camera_reports_alone():
    camera = SlotOccupancy(number=1, state=SlotState.TAKEN, confidence=0.9, changed_at=NOW, reported_at=NOW)
    simulator, repository = simulate(5, StationOccupancy("garage", {1: camera}))
    for step in range(20):
        simulator.step(NOW + step * STEP)
    assert repository.get("garage").slot(1) == camera


def test_takes_over_a_slot_the_camera_stopped_reporting():
    reported = NOW - STALE_AFTER - timedelta(seconds=1)
    camera = SlotOccupancy(number=1, state=SlotState.TAKEN, confidence=0.9, changed_at=reported, reported_at=reported)
    simulator, repository = simulate(5, StationOccupancy("garage", {1: camera}))
    simulator.step(NOW)
    assert repository.get("garage").slot(1).reported_at == NOW


def test_a_fresh_simulator_carries_on_with_the_slots_it_reported():
    # On AWS every scheduled run builds a new simulator on the same table.
    first, repository = simulate(5)
    first.step(NOW)
    second = OccupancySimulator(garage(5), repository, STALE_AFTER, rng=random.Random(8))
    second.step(NOW + STEP)
    assert all(slot.simulated and slot.reported_at == NOW + STEP for slot in repository.get("garage").slots.values())


def test_a_camera_reads_a_simulated_slot_instead_of_trusting_it():
    simulated = SlotOccupancy(number=1, state=SlotState.FREE, reported_at=NOW, simulated=True)
    assert _needs_reading(simulated, known_print=7, new_print=7)
    assert not _needs_reading(replace(simulated, simulated=False), known_print=7, new_print=7)


def test_dynamodb_keeps_who_reported_a_slot():
    slot = SlotOccupancy(number=3, state=SlotState.TAKEN, confidence=1.0, changed_at=NOW, reported_at=NOW,
                         simulated=True)
    stored = _occupancy(_item(StationOccupancy("garage", {3: slot}), version=1))
    assert stored.slot(3) == slot
    assert not _slot(3, {"state": "free"}).simulated  # an item from before the simulator


def test_a_scheduled_run_steps_until_shortly_before_its_timeout(monkeypatch):
    simulator, repository = simulate(5)
    monkeypatch.setattr(composition, "simulator", lambda: simulator)
    monkeypatch.setattr(handler.time, "sleep", lambda seconds: None)

    class Context:  # a minute-long Lambda run whose clock moves one step per call
        remaining = 60_000

        def get_remaining_time_in_millis(self) -> int:
            self.remaining -= 3_000
            return self.remaining

    result = handler.handler({}, Context())
    assert result["steps"] == 17
    assert repository.get("garage").slot(1).simulated


def test_simulation_is_off_unless_asked_for():
    assert Settings.from_environment({}).simulation == "off"
    assert Settings.from_environment({"BACKEND_SIMULATION": "on"}).simulation == "on"
    with pytest.raises(SettingsError):
        Settings.from_environment({"BACKEND_SIMULATION": "sometimes"})
