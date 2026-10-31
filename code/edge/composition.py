"""The one place that picks implementations, from the command-line options."""

import argparse
import json
from pathlib import Path

import httpx

from pii import CombinedPIIDetector, PIIDetector, SidecarPIIDetector, YoloPIIDetector
from pipeline import EdgePipeline
from sources import FolderFrameSource, FrameSource, SerialFrameSource, WebcamFrameSource
from text import TextPIIDetector
from upload import DryRunUploader, FrameUploader, IngestClient

UPLOAD_TIMEOUT_SECONDS = 35  # the Ingest function may take up to 30 s


def build_pipeline(options: argparse.Namespace) -> EdgePipeline:
    source, camera_ids = _source(options)
    return EdgePipeline(source, _detector(options), _uploader(options, camera_ids))


def _source(options: argparse.Namespace) -> tuple[FrameSource, list[str]]:
    if options.source in ("webcam", "serial"):
        if not options.camera_id:
            raise SystemExit(f"--source {options.source} needs --camera-id")
        if options.pii == "sidecar":
            raise SystemExit("--pii sidecar needs recorded frames. Use --pii yolo with a live camera")
        if options.source == "serial":
            source = SerialFrameSource(options.camera_id, options.port, options.size, options.interval)
        else:
            source = WebcamFrameSource(options.camera_id, options.device, options.size, options.interval)
        return source, [options.camera_id]
    folder = FolderFrameSource(Path(options.source), options.interval, options.rounds)
    return folder, folder.camera_ids


def _detector(options: argparse.Namespace) -> PIIDetector:
    if options.pii == "yolo":
        return CombinedPIIDetector(YoloPIIDetector(options.yolo_weights), TextPIIDetector())
    return SidecarPIIDetector()


def _uploader(options: argparse.Namespace, camera_ids: list[str]) -> FrameUploader:
    if options.upload == "dry-run":
        return DryRunUploader()
    if not (options.url and options.tokens):
        raise SystemExit("--upload http needs --url and --tokens")
    tokens = json.loads(Path(options.tokens).read_text())
    missing = sorted(set(camera_ids) - set(tokens))
    if missing:
        raise SystemExit(f"{options.tokens} has no token for {', '.join(missing)}")
    return IngestClient(httpx.Client(timeout=UPLOAD_TIMEOUT_SECONDS), options.url, tokens)
