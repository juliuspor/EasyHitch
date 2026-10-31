"""Turns one camera frame into slot states. The frame never leaves memory."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from PIL import Image

from cameras.camera import Box, Camera, SlotView
from classification.classifier import ClassifierUnavailable, OccupancyClassifier, Reading
from ingest.fingerprints import FingerprintStore
from ingest.frame import decode_jpeg, fingerprint, has_changed
from occupancy.decider import decide
from occupancy.model import SlotOccupancy, SlotState, StationOccupancy
from occupancy.repository import ConcurrentUpdate, OccupancyRepository


class FrameSizeMismatch(ValueError):
    """The frame does not have the size the camera was calibrated for."""


@dataclass(frozen=True)
class IngestResult:
    camera_id: str
    station_id: str
    slots_checked: int
    slots_changed: int


class IngestService:
    def __init__(self, classifier: OccupancyClassifier, occupancy: OccupancyRepository,
                 fingerprints: FingerprintStore) -> None:
        self._classifier = classifier
        self._occupancy = occupancy
        self._fingerprints = fingerprints

    def ingest(self, camera: Camera, jpeg: bytes, person_boxes: Sequence[Box]) -> IngestResult:
        frame = decode_jpeg(jpeg)
        if frame.size != camera.frame_size:
            raise FrameSizeMismatch(f"frame is {frame.width}x{frame.height}, camera {camera.id} is calibrated "
                                    f"for {camera.frame_size[0]}x{camera.frame_size[1]}")
        # A slot behind a person cannot be seen, so it keeps its last state.
        visible = [slot for slot in camera.slots if not any(slot.overlaps(box) for box in person_boxes)]
        prints = {slot.number: fingerprint(frame, slot.box) for slot in visible}
        known = self._fingerprints.get(camera.id)
        occupancy = self._occupancy.get(camera.station_id) or StationOccupancy(camera.station_id)
        to_read = [slot for slot in visible
                   if _needs_reading(occupancy.slot(slot.number), known.get(slot.number), prints[slot.number])]
        readings = self._read(frame, to_read)
        changed = self._save(camera.station_id, visible, readings)
        self._fingerprints.put(camera.id, {**known, **prints})
        return IngestResult(camera.id, camera.station_id, slots_checked=len(to_read), slots_changed=changed)

    def _read(self, frame: Image.Image, slots: list[SlotView]) -> dict[int, Reading]:
        if not slots:
            return {}
        readings = self._classifier.classify(frame, slots)
        missing = {slot.number for slot in slots} - set(readings)
        if missing:
            raise ClassifierUnavailable(f"no reading for slots {sorted(missing)}")
        return readings

    def _save(self, station_id: str, visible: list[SlotView], readings: dict[int, Reading]) -> int:
        # Two cameras of one station may save at the same moment. The second
        # retries once on the state the first one wrote.
        try:
            return self._save_once(station_id, visible, readings)
        except ConcurrentUpdate:
            return self._save_once(station_id, visible, readings)

    def _save_once(self, station_id: str, visible: list[SlotView], readings: dict[int, Reading]) -> int:
        """Applies the readings, marks every visible slot as reported, and returns how many slots changed."""
        now = datetime.now(UTC).replace(microsecond=0)
        current = self._occupancy.get(station_id) or StationOccupancy(station_id)
        updated = {}
        for slot in visible:
            state = current.slot(slot.number)
            if state.simulated:
                # The camera takes the slot over. The simulator's guess is no reading, so start
                # from unknown: an unsure first reading then waits for a second, not on the guess.
                state = SlotOccupancy(slot.number)
            if slot.number in readings:
                state = decide(state, readings[slot.number], now)
            updated[slot.number] = state.reported(now)
        self._occupancy.save(current.with_slots(updated))
        return sum(1 for number, slot in updated.items() if slot.state != current.slot(number).state)


def _needs_reading(slot: SlotOccupancy, known_print: int | None, new_print: int) -> bool:
    """Read a slot that was never decided, waits for a confirming reading, was simulated, or looks different."""
    return (slot.state is SlotState.UNKNOWN or slot.pending_taken is not None or slot.simulated
            or has_changed(known_print, new_print))
