"""Runs the camera pipeline on this computer.

Recorded frames against a local backend:
    .venv/bin/python main.py --source ../../assets/camera-frames --pii sidecar \\
        --upload http --url http://localhost:8000 --tokens dev-tokens.json

A camera on this computer, without a backend:
    .venv/bin/python main.py --source webcam --camera-id cam-south-a --pii yolo --upload dry-run

A XIAO ESP32S3 Sense on the USB cable (code/firmware/camera), without a backend:
    .venv/bin/python main.py --source serial --camera-id cam-xiao-1 --size 640x480 --pii yolo --upload dry-run
"""

import argparse
import logging

from composition import build_pipeline
from frame import parse_size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", required=True,
                        help="'webcam', 'serial' (a XIAO board on USB), or a folder with one subfolder of "
                             "recorded JPEGs per camera")
    parser.add_argument("--pii", choices=["sidecar", "yolo"], required=True,
                        help="sidecar: read people and regions from a JSON file next to each frame. "
                             "yolo: find people with YOLO11n, and text such as licence plates with PP-OCRv5")
    parser.add_argument("--upload", choices=["http", "dry-run"], required=True,
                        help="http: POST to the Ingest API. dry-run: only log what would be sent")
    parser.add_argument("--url", help="Ingest API base URL, e.g. http://localhost:8000")
    parser.add_argument("--tokens", help="JSON file of camera id to bearer token")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds between captures (default 5)")
    parser.add_argument("--rounds", type=int, help="recorded frames: stop after this many rounds")
    parser.add_argument("--camera-id", help="webcam, serial: the camera id its calibration and token belong to")
    parser.add_argument("--device", type=int, default=0, help="webcam: OpenCV device number (default 0)")
    parser.add_argument("--port", help="serial: the board's port (default: the first /dev/cu.usbmodem* or /dev/ttyACM*)")
    parser.add_argument("--size", type=parse_size, default=(1280, 960),
                        help="webcam, serial: frame size, as in the camera's calibration (default 1280x960)")
    parser.add_argument("--yolo-weights", default="yolo11n.pt", help="yolo: model weights (default yolo11n.pt)")
    options = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # each request is already logged once
    build_pipeline(options).run()


if __name__ == "__main__":
    main()
