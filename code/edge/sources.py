"""Where frames come from: a camera, or recorded frames on disk."""

import glob
import io
import logging
import os
import select
import termios
import time
import tty
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageOps

from frame import Frame

LOGGER = logging.getLogger("edge")
# Where macOS and Linux put a USB serial board such as the XIAO ESP32S3 Sense.
SERIAL_PORTS = ("/dev/cu.usbmodem*", "/dev/ttyACM*")


class FrameSource(Protocol):
    def frames(self) -> Iterator[Frame]: ...


class FolderFrameSource:
    """Replays recorded JPEGs, one subfolder per camera, each folder's frames in name order and looped.

    Every round yields one frame per camera, then waits `interval` seconds.
    """

    def __init__(self, root: Path, interval: float, rounds: int | None = None) -> None:
        folders = [folder for folder in sorted(root.iterdir()) if folder.is_dir()]
        self._cameras = {folder.name: sorted(folder.glob("*.jpg")) for folder in folders if any(folder.glob("*.jpg"))}
        if not self._cameras:
            raise ValueError(f"{root} has no camera folders with .jpg frames")
        self._interval = interval
        self._rounds = rounds

    @property
    def camera_ids(self) -> list[str]:
        return list(self._cameras)

    def frames(self) -> Iterator[Frame]:
        round_number = 0
        while self._rounds is None or round_number < self._rounds:
            if round_number:
                time.sleep(self._interval)
            for camera_id, photos in self._cameras.items():
                path = photos[round_number % len(photos)]
                image = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
                yield Frame(camera_id=camera_id, image=image, captured_at=datetime.now(UTC), path=path)
            round_number += 1


class WebcamFrameSource:
    """Captures from a camera attached to this computer, like a board's camera does."""

    def __init__(self, camera_id: str, device: int, size: tuple[int, int], interval: float) -> None:
        self._camera_id = camera_id
        self._device = device
        self._size = size
        self._interval = interval

    def frames(self) -> Iterator[Frame]:
        # OpenCV is an optional dependency (requirements-camera.txt), only needed here.
        import cv2

        capture = cv2.VideoCapture(self._device)
        if not capture.isOpened():
            raise RuntimeError(f"cannot open camera device {self._device}")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, self._size[0])
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self._size[1])
        try:
            while True:
                captured, bgr = capture.read()
                if not captured:
                    raise RuntimeError(f"camera device {self._device} returned no frame")
                image = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
                if image.size != self._size:
                    image = image.resize(self._size, Image.Resampling.LANCZOS)
                yield Frame(camera_id=self._camera_id, image=image, captured_at=datetime.now(UTC))
                time.sleep(self._interval)
        finally:
            capture.release()


class SerialFrameSource:
    """Captures from a XIAO ESP32S3 Sense on a USB cable, running code/firmware/camera.

    The board answers the command "c" with a line "JPEG <length>" and the JPEG's
    bytes. The frame goes into the pipeline from memory, never to disk. A pulled
    cable or a board that does not answer is logged, and the port is opened again
    on the next capture.
    """

    def __init__(self, camera_id: str, port: str | None, size: tuple[int, int], interval: float,
                 timeout: float = 10.0) -> None:
        self._camera_id = camera_id
        self._port = port
        self._size = size
        self._interval = interval
        self._timeout = timeout

    def frames(self) -> Iterator[Frame]:
        fd = None
        try:
            while True:
                try:
                    if fd is None:
                        fd = _open_raw(self._port or find_serial_port())
                    image = Image.open(io.BytesIO(_capture(fd, self._timeout))).convert("RGB")
                except (OSError, TimeoutError, ValueError) as error:  # an unreadable image is an OSError
                    LOGGER.warning("%s: no frame from the board (%s)", self._camera_id, error)
                    if fd is not None:
                        os.close(fd)
                        fd = None
                else:
                    if image.size != self._size:
                        image = image.resize(self._size, Image.Resampling.LANCZOS)
                    yield Frame(camera_id=self._camera_id, image=image, captured_at=datetime.now(UTC))
                time.sleep(self._interval)
        finally:
            if fd is not None:
                os.close(fd)


def find_serial_port() -> str:
    ports = sorted(port for pattern in SERIAL_PORTS for port in glob.glob(pattern))
    if not ports:
        raise OSError("no USB serial board found")
    return ports[0]


def _open_raw(port: str) -> int:
    fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
    tty.setraw(fd)  # bytes as they are: no echo, no line editing, no newline translation
    return fd


def _capture(fd: int, timeout: float) -> bytes:
    """Asks for a fresh photo and reads the answer. Lines before "JPEG <length>" are the board's log."""
    termios.tcflush(fd, termios.TCIFLUSH)  # drop anything left from an earlier, broken answer
    os.write(fd, b"c")
    deadline = time.monotonic() + timeout
    received = b""

    def read_more() -> bytes:
        left = deadline - time.monotonic()
        if left <= 0 or not select.select([fd], [], [], left)[0]:
            raise TimeoutError(f"the board did not answer within {timeout:.0f} s")
        data = os.read(fd, 65536)
        if not data:
            raise OSError("the board went away")
        return data

    while True:
        while b"\n" not in received:
            received += read_more()
        line, _, received = received.partition(b"\n")
        if line.startswith(b"JPEG "):
            break
    length = int(line.split()[1])
    while len(received) < length:
        received += read_more()
    return received[:length]
