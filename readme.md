# Easy+Hitch: Find my Bike Slot

Our entry for **Find my Bike Slot**, the Endress+Hauser challenge at BaselHack
2026. The [challenge brief](documentation/challenge.md) describes the problem,
the suggested features, the available resources and the privacy rules.

Easy+Hitch shows riders which bike slots are free at the Endress+Hauser site
in Reinach before they arrive. Cameras pixelate faces and licence plates and
send a frame only when their view changes. A serverless backend on AWS reads
every changed slot with Jev 1.14 and keeps only the current state of each slot,
never the images. Riders see the free slots in the iOS app, with a map,
cycling directions and a 3D view of every shelter, and AI agents get the same
answers through an MCP server.

## How it works

1. A camera compares each frame with the last one it sent. Nothing leaves the
   camera until the view changes, or five minutes pass.
2. The camera finds people and licence plates, pixelates faces and plates, and
   uploads the JPEG to the Ingest API.
3. The backend fingerprints every slot and asks Jev one yes or no question per
   changed slot. A state changes on a sure answer, or on two unsure answers
   that agree.
4. The Availability API and the MCP server answer from the current slot
   states, and a slot no camera saw for 10 minutes reads `unknown`.

## Run it

Python 3.13 is all it needs locally: no AWS account, no API key, no camera.

```bash
cd code/backend && python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/uvicorn local:app --port 8000
```

In a second terminal, start the recorded cameras, which replay the hosts'
photos of the north and south stations:

```bash
cd code/edge && python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python main.py --source ../../assets/camera-frames --pii sidecar --upload http --url http://localhost:8000 --tokens dev-tokens.json
```

For a demo in which every station keeps changing, start the backend with
simulated occupancy instead, and leave the recorded cameras off:

```bash
cd code/backend && BACKEND_SIMULATION=on .venv/bin/uvicorn local:app --port 8000
```

Then open `http://localhost:8000/v1/stations`, or let an AI agent such as
Claude Code ask where to park:

```bash
claude mcp add --transport http easy-hitch http://localhost:8000/mcp
```

Deploying to AWS, reading slots with Jev and connecting a live camera are
described in the [backend](code/backend/README.md) and
[edge](code/edge/README.md) READMEs.

## Repository

| Folder | Contents |
|---|---|
| [`code/backend`](code/backend) | Ingest API, Availability API and MCP server, for AWS Lambda or a laptop |
| [`code/edge`](code/edge) | The camera pipeline: change check, pixelation, upload |
| [`code/ios`](code/ios) | SwiftUI app: map, search, station cards, 3D view, and an offline demo mode |
| [`code/scene-generator`](code/scene-generator) | Blender scripts that build shelter models from layout files |
| [`documentation`](documentation) | Architecture, API contracts, and the judging criteria |
| [`assets`](assets) | Site photos, recorded camera frames, campus map data, and the pitch deck |

## Documentation

- [Architecture: parts and seams](documentation/architecture.md)
- [Judging criteria, with evidence from the code](documentation/judging.md)
- API contracts: [Availability API](documentation/api/availability.openapi.json), [Ingest API](documentation/api/ingest.openapi.json)
- [Pitch deck](assets/pitch/index.html)

## Credits

- **Map data.** The slot positions in `assets/campus-map/slots.json`, and the
  station catalog built from them, are mapped from OpenStreetMap, satellite
  imagery, the site photos and the team's site markings. OpenStreetMap data © OpenStreetMap
  contributors, available under the Open Database License. Keep this
  attribution wherever the data, or anything derived from it, is shown.
- **Photos.** The site photos in `assets/challenge-site-photos/` and the
  recorded camera frames made from them are the challenge hosts' reference
  photos of 29 October 2026.
- **Person detection.** YOLO11n through Ultralytics, under AGPL-3.0, installed
  only for a live camera.
- **Plate detection.** PP-OCRv5's mobile text detector by PaddlePaddle, under
  Apache-2.0, downloaded only for a live camera.
- **Pitch deck.** canvas-confetti, under the ISC licence.

## Licence

MIT, see [license.txt](license.txt).
