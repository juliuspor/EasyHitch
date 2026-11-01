# Backend

Two APIs and an MCP server, written once and run either as two AWS Lambda
functions or as one local server:

- **Ingest API** (`POST /v1/frames`): cameras upload pixelated frames. The
  backend reads each changed slot with Jev 1.14 through OpenRouter and keeps
  only the current state and a fingerprint of each slot. Frames never leave
  memory.
- **Availability API** (`GET /v1/stations`): stations, free slots and 3D
  models for the iOS app and any other client.
- **MCP server** (`/mcp`): the same answers as tools for AI agents.

On AWS, the Ingest function writes slot states to DynamoDB, and the
Availability function reads them for the API and the MCP server. The
architecture is in
[`documentation/architecture.md`](../../documentation/architecture.md), and
the API contracts are in [`documentation/api/`](../../documentation/api).

## Layout

Organised by feature. This folder is the import root, so modules import each
other as `from occupancy.decider import decide`.

| Folder | What it holds |
|---|---|
| `stations/` | The station catalog (`data/stations.json`) and the script that builds it from the campus map |
| `cameras/` | Camera calibration, the token registry, and a preview that draws slot boxes on a frame |
| `occupancy/` | Slot states, the rule that turns readings into states, and their storage in memory or DynamoDB |
| `classification/` | The classifier interface, `JevCropClassifier` and `StaticClassifier` |
| `ingest/` | Frame decoding, slot fingerprints, `IngestService`, the ingest route and its Lambda handler |
| `availability/` | `AvailabilityService`, its routes, the MCP server and its Lambda handler |
| `simulation/` | `OccupancySimulator`, which fills the slots no camera reports over a simulated day, and its scheduled Lambda handler |
| `tests/` | Tests, run with `.venv/bin/pip install -r requirements-dev.txt` and `.venv/bin/python -m pytest` |
| `data/` | Bundled data: stations, camera calibrations, fixed readings, development tokens |
| `composition.py` | The one place that picks implementations from the environment |

## Run locally

Needs Python 3.13 and nothing else: no AWS account, no OpenRouter key, no
Docker.

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

```bash
.venv/bin/uvicorn local:app --port 8000
```

Send frames with the [camera pipeline](../edge/README.md), then open
`http://localhost:8000/v1/stations` or the interactive API docs at
`http://localhost:8000/docs`. An AI agent such as Claude Code connects to the
MCP server with:

```bash
claude mcp add --transport http easy-hitch http://localhost:8000/mcp
```

Locally the backend reads slots with `StaticClassifier`, which answers from
`data/static-readings.json`, and keeps everything in memory. To read slots
with Jev instead:

```bash
OPENROUTER_API_KEY=<key> BACKEND_CLASSIFIER=jev .venv/bin/uvicorn local:app --port 8000
```

For a demo, or for stations without a camera yet, simulate the slots no camera
reports. A working day takes ten minutes, each station moves one slot every
eight seconds and always keeps one free, and a slot a camera reports stays the
camera's:

```bash
BACKEND_SIMULATION=on .venv/bin/uvicorn local:app --port 8000
```

## Configuration

| Variable | Local default | AWS default | Meaning |
|---|---|---|---|
| `BACKEND_PROFILE` | `local` | `aws` | Picks the defaults below |
| `BACKEND_CLASSIFIER` | `static` | `jev` | `static` answers from `data/static-readings.json` |
| `BACKEND_STORAGE` | `memory` | `dynamodb` | Where slot states and fingerprints live |
| `BACKEND_CAMERAS` | `file` | `ssm` | Where camera token hashes come from |
| `BACKEND_SIMULATION` | `off` | `off` | `on` simulates the slots no camera reports, in the local server. On AWS, use the template's `Simulation` parameter |
| `OPENROUTER_API_KEY` | | | The key itself, for `jev` on a laptop |
| `OPENROUTER_API_KEY_PARAMETER` | | `/easyhitch/openrouter-api-key` | SSM parameter with the key, on AWS |
| `CAMERA_TOKENS_PARAMETER` | | `/easyhitch/camera-tokens` | SSM parameter with the token hashes |
| `OCCUPANCY_TABLE`, `FINGERPRINT_TABLE` | | set by the template | DynamoDB tables |
| `JEV_MODEL` | `typesafe/jev-1.14` | same | OpenRouter model id |
| `DECISIONS_URL` | `https://openrouter.ai/api/alpha/decisions` | same | OpenRouter's Decisions API endpoint |
| `STALE_AFTER_SECONDS` | `600` | same | A slot no camera reported for this long reads `unknown` |

The backend checks the combination at start and refuses to run with a missing
piece, such as `jev` without a key.

## Deploy to AWS

Needs an AWS account with the AWS CLI signed in, the SAM CLI
(`brew install aws-sam-cli`) and an OpenRouter key. Docker is not needed:
`sam build` downloads Linux wheels for the Lambda runtime.

1. Store the OpenRouter key:

   ```bash
   aws ssm put-parameter --name /easyhitch/openrouter-api-key --type SecureString --value <key>
   ```

2. Give every camera a random token, and store only the SHA-256 of each
   (`openssl rand -hex 32`, then `printf %s <token> | shasum -a 256 | cut -d' ' -f1`):

   ```bash
   aws ssm put-parameter --name /easyhitch/camera-tokens --type SecureString --value '{"cam-south-a": "<sha256>"}'
   ```

   The tokens themselves go only into the camera pipeline's tokens file,
   which is not committed.

3. Build and deploy. The first deploy asks for a stack name and region:

   ```bash
   sam build && sam deploy --guided
   ```

   For a demo, or stations without a camera, add
   `--parameter-overrides Simulation=on`: a function that a schedule starts
   every minute then simulates the slots no camera reports. An account that
   caps Lambda memory, as some sandbox accounts do at 512 MB, also needs
   `IngestMemory=512`.

`sam deploy` prints `IngestUrl` for the cameras and `AvailabilityUrl` for
clients. Agents use `AvailabilityUrl` plus `mcp`. Both functions run Python
3.13 on arm64 behind Lambda Function URLs. The template creates the two
DynamoDB tables and gives each function only the permissions it needs.

Our deployment is the stack `easyhitch` in `eu-north-1`, deployed with
`--parameter-overrides Simulation=on IngestMemory=512`. The
[overview](../../documentation/overview.md#how-we-tested-it) lists the
end-to-end runs against it.

## Data

- **Stations**: `data/stations.json` is built from the campus map:

  ```bash
  .venv/bin/python -m stations.build ../../assets/campus-map/slots.json data/stations.json
  ```

- **Cameras**: one calibration per camera in `data/cameras/<camera_id>.json`,
  with the frame size and the pixel box of every slot it sees. Check a
  calibration by eye with:

  ```bash
  .venv/bin/python -m cameras.preview data/cameras/cam-south-a.json \
      ../../assets/camera-frames/cam-south-a/IMG_20261029_083909.jpg preview.png
  ```

- **3D models**: a station's model goes in `data/models/<station_id>.usdz`,
  with one node named `slot_<number>` per slot. The API reports `model_url`
  as `null` for a station without one.

After changing a route or a response model, regenerate the API contracts:

```bash
.venv/bin/python export_openapi.py
```
