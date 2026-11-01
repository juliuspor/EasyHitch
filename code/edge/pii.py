"""Finds what must not leave the camera: people's faces and readable licence plates.

A detector keeps two lists apart:
- people: the backend skips slots behind them, as it cannot see those slots.
- pii_regions: faces and readable text such as licence plates, pixelated before upload.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from frame import Box, Frame

# The top fifth of a person box holds the head, from any side.
FACE_SHARE = 0.2
PERSON_CLASS = 0  # "person" in the COCO classes YOLO11n is trained on
PERSON_CONFIDENCE = 0.35


@dataclass(frozen=True)
class Detections:
    people: tuple[Box, ...] = ()
    pii_regions: tuple[Box, ...] = ()


class PIIDetector(Protocol):
    def detect(self, frame: Frame) -> Detections: ...


def face_region(person: Box) -> Box:
    x0, y0, x1, y1 = person
    return x0, y0, x1, y0 + max(1, round((y1 - y0) * FACE_SHARE))


class SidecarPIIDetector:
    """Reads the detections of a recorded frame from the JSON file next to it.

    The file is required: a recorded frame without one could carry an
    unblurred face, so it is refused instead of uploaded.
    """

    def detect(self, frame: Frame) -> Detections:
        if frame.path is None:
            raise ValueError("sidecar detections need recorded frames")
        sidecar = frame.path.with_suffix(".json")
        if not sidecar.is_file():
            raise FileNotFoundError(f"{sidecar} is missing. List people and pii_regions for {frame.path.name}")
        entry = json.loads(sidecar.read_text())
        width, height = frame.image.size
        return Detections(
            people=tuple(_box(box, width, height, sidecar) for box in entry.get("people", [])),
            pii_regions=tuple(_box(box, width, height, sidecar) for box in entry.get("pii_regions", [])),
        )


class YoloPIIDetector:
    """Finds people with YOLO11n and treats the top of each as a face."""

    def __init__(self, weights: str) -> None:
        # Ultralytics is an optional dependency (requirements-camera.txt), only needed here.
        from ultralytics import YOLO
        from ultralytics.utils.events import events

        # Ultralytics reports every prediction run to its usage analytics by default. Only the
        # pixelated frame is meant to leave the edge, so that is off for this process.
        events.enabled = False
        self._model = YOLO(weights)

    def detect(self, frame: Frame) -> Detections:
        result = self._model.predict(frame.image, classes=[PERSON_CLASS], conf=PERSON_CONFIDENCE, verbose=False)[0]
        people = tuple(tuple(round(value) for value in box) for box in result.boxes.xyxy.tolist())
        return Detections(people=people, pii_regions=tuple(face_region(person) for person in people))


class CombinedPIIDetector:
    """Runs several detectors on each frame and merges what they find."""

    def __init__(self, *detectors: PIIDetector) -> None:
        self._detectors = detectors

    def detect(self, frame: Frame) -> Detections:
        found = [detector.detect(frame) for detector in self._detectors]
        return Detections(people=tuple(box for detections in found for box in detections.people),
                          pii_regions=tuple(box for detections in found for box in detections.pii_regions))


def _box(values: list, width: int, height: int, source: Path) -> Box:
    x0, y0, x1, y1 = (int(value) for value in values)
    if not (0 <= x0 < x1 <= width and 0 <= y0 < y1 <= height):
        raise ValueError(f"{source}: box {values} does not fit a {width}x{height} frame")
    return x0, y0, x1, y1
