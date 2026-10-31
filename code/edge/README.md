# Edge

The camera pipeline in Python. It runs on any computer with a camera, and it
replays recorded frames for development and demonstrations. Its design targets
the XIAO ESP32S3 Sense: a small person detector, coarse pixelation and an
HTTPS upload are all within reach of the board.

For each frame the pipeline:

1. skips the frame unless it differs from the last frame the backend accepted,
   or nothing was sent for 5 minutes (a heartbeat that keeps the camera's
   slots from turning `unknown`),
2. finds people and the regions to hide: each person's face and any readable
   text, licence plates of every format among it, or for a recorded frame the
   regions its sidecar lists,
3. pixelates those regions in 16x16 blocks,
4. uploads the JPEG with the person boxes, so the backend skips the slots
   behind people,
5. makes the frame the new baseline only once the backend accepted it, so a
   failed upload is retried with the next frame.

Frames stay in memory and are never written to disk. How the camera fits
into the whole system is in
[`documentation/architecture.md`](../../documentation/architecture.md).

## Implementations

`composition.py` builds the pipeline from the command line:

| Interface | Implementations |
|---|---|
| `FrameSource` | `WebcamFrameSource` captures from a camera attached to this computer. `FolderFrameSource` replays recorded JPEGs, one subfolder per camera, in a loop. |
| `PIIDetector` | `YoloPIIDetector` finds people with YOLO11n and takes the top fifth of each as the face. `TextPIIDetector` finds readable text with PP-OCRv5 and grows each line by two line heights, so it covers whole licence plates, also the small yellow e-bike plates and tilted motorbike plates that plate detectors trained on car plates miss. `CombinedPIIDetector` runs both for a live camera. `SidecarPIIDetector` reads people and regions from a JSON file next to each recorded frame. |
| `FrameUploader` | `IngestClient` posts to `/v1/frames` and retries while the backend is unavailable. `DryRunUploader` logs what would be sent. |

## Run

Needs Python 3.13 and a running backend (see the
[backend README](../backend/README.md)).

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

The recorded cameras against the local backend, one round every 5 seconds:

```bash
.venv/bin/python main.py --source ../../assets/camera-frames --pii sidecar --upload http --url http://localhost:8000 --tokens dev-tokens.json
```

`--rounds 1` sends each camera's frame once and stops. `dev-tokens.json` holds
the development tokens the local backend accepts. Against AWS, use the
deployment's `IngestUrl` and a tokens file with the real tokens, which is not
committed.

A live camera, with YOLO11n finding people and PP-OCRv5 finding text:

```bash
.venv/bin/pip install -r requirements-camera.txt
```

```bash
.venv/bin/python main.py --source webcam --camera-id cam-south-a --pii yolo --upload dry-run
```

A XIAO ESP32S3 Sense on the USB cable, running `code/firmware/camera` (see
[camera board](../../documentation/camera-firmware.md)):

```bash
.venv/bin/python main.py --source serial --camera-id cam-xiao-1 --size 640x480 --pii yolo --upload dry-run
```

The camera's frames must match its calibration in the backend (`--size`,
1280x960 by default), and `--upload http` needs the camera's token. The
weights of YOLO11n and PP-OCRv5 download on first use. PP-OCRv5's file is
pinned by its SHA-256, and any other file is refused.

## Recorded frames

`assets/camera-frames/<camera_id>/` holds the hosts' photos of the north
and south stations, one photo per camera, upright and scaled to 1280x960. Each frame has
a sidecar JSON file listing `people` and `pii_regions`: faces, readable
plates, and plates on parked cars.

| Camera | Photo | Station | Slots |
|---|---|---|---|
| `cam-south-a` | `IMG_20261029_083909` | `cmr-south-02` | 1 to 10 |
| `cam-south-b` | `IMG_20261029_083657` | `cmr-south-02` | 11 to 20 |
| `cam-north-1` to `cam-north-4` | `084154`, `084203`, `084213`, `084248` | `cmr-north-01` | 1 to 20, one bay each |
| `cam-north-5` | `IMG_20261029_084118` | `cmr-north-01` | 21 to 35 |

Each photo is its own camera, with its own calibration in
`code/backend/data/cameras/`. To add a photo as a camera:

```bash
.venv/bin/python prepare_photos.py <camera_id> <photo.jpg> --output ../../assets/camera-frames
```

Then fill in its sidecar, add its calibration and token in the backend, and
check the slot boxes with the backend's `cameras.preview`.
