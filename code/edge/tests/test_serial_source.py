"""The serial source reads photos the way code/firmware/camera sends them, from a pseudo-terminal standing in for the board."""

import io
import os
import threading

import pytest
from PIL import Image

from sources import SerialFrameSource, _capture, _open_raw


def jpeg(size: tuple[int, int]) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (90, 120, 150)).save(buffer, "JPEG")
    return buffer.getvalue()


def answer_once(board: int, photo: bytes) -> None:
    """What the firmware does on "c": a line of its log may come first, then the photo."""
    assert os.read(board, 1) == b"c"
    reply = b"Camera ready\nJPEG %d\n" % len(photo) + photo
    while reply:
        reply = reply[os.write(board, reply):]


def test_reads_a_photo_and_scales_it_to_the_calibrated_size():
    board, port = os.openpty()
    threading.Thread(target=answer_once, args=(board, jpeg((640, 480))), daemon=True).start()
    frames = SerialFrameSource("cam-xiao-1", os.ttyname(port), size=(1280, 960), interval=0).frames()
    frame = next(frames)
    frames.close()
    assert frame.camera_id == "cam-xiao-1"
    assert frame.image.size == (1280, 960)
    assert frame.path is None  # straight from memory, never a file


def test_gives_up_on_a_board_that_does_not_answer():
    board, port = os.openpty()
    fd = _open_raw(os.ttyname(port))
    with pytest.raises(TimeoutError):
        _capture(fd, timeout=0.2)
    os.close(fd)
    os.close(board)
