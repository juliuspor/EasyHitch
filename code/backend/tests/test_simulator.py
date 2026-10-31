"""The simulator fills the slots no camera reports, follows the time of day, and never overrides a camera."""

import random
from datetime import UTC, datetime, timedelta

import pytest

from occupancy.model import SlotOccupancy, SlotState, StationOccupancy
from occupancy.repository import InMemoryOccupancyRepository
from settings import Settings, SettingsError
from simulation.simulator import BUSY, DAY, QUIET, STEP, OccupancySimulator
from stations.catalog import Location, Slot, Station, StationCatalog

# Midday UTC is a whole number of simulated days since the epoch: the quiet start of a day.
NOW = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
STALE_AFTER = timedelta(minutes=10)


def simulate(slots: int, stored: StationOccupancy | None = None) -> tuple[OccupancySimulator, InMemoryOccupancyRepository]:
    here = Location(lat=47.4886, lon=7.5984)
    station = Station(id="garage", name="Garage", location=here,
                      slots=tuple(Slot(number=n, location=here) for n in range(1, slots + 1)))
    repository = InMemoryOccupancyRepository()
    if stored:
        repository.save(stored)
    return OccupancySimulator(StationCatalog([station]), repository, STALE_AFTER, rng=random.Random(7)), repository


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


def test_simulation_is_off_unless_asked_for():
    assert Settings.from_environment({}).simulation == "off"
    assert Settings.from_environment({"BACKEND_SIMULATION": "on"}).simulation == "on"
    with pytest.raises(SettingsError):
        Settings.from_environment({"BACKEND_SIMULATION": "sometimes"})
