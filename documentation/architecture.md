# Architecture: parts and seams

Easy+Hitch is split into parts that are built and changed independently: the
camera pipeline, the backend, the iOS app and the 3D scenes. Each part talks
to the next through one small, written-down interface. The
[architecture diagram](diagrams/easy-hitch-architecture.html) and
[frame flow](diagrams/easy-hitch-flow.html) draw it.

One frame takes this path:

1. A camera captures a frame and compares it with the last frame the backend
   accepted. Nothing happens until the view changes, or five minutes pass.
2. The camera finds people and licence plates, pixelates faces and plates, and
   uploads the JPEG with the person boxes to `POST /v1/frames`.
3. The Ingest function fingerprints every slot and asks Jev 1.14 about the
   slots that changed, one yes or no question per slot crop.
4. The state rule turns the readings into slot states, which DynamoDB keeps.
   The frame is discarded.
5. The Availability function serves the states at `/v1/stations` and, for AI
   agents, through the MCP server at `/mcp`.

| Part | Folder | Interface it owns |
|---|---|---|
| Camera pipeline | `code/edge` | The Ingest API request: JPEG, token, person boxes |
| Backend | `code/backend` | Both API contracts, `OccupancyClassifier`, `OccupancyRepository`, `FingerprintStore` |
| iOS app | `code/ios` | `StationService`, with a client of the Availability API and built-in sample data |
| 3D scenes | `code/scene-generator` | Shelter models with one node per slot |

## Camera and backend: the Ingest API

The camera pipeline sends a frame only when it changed, or every five minutes
as a heartbeat ([`EdgePipeline`](../code/edge/pipeline.py#L26-L53)). It
first pixelates the faces and the readable text it finds, licence plates
among it, or in recorded frames the regions their sidecars list
([`pixelate`](../code/edge/pixelate.py#L12-L22)). It
sends the person boxes along, so the backend skips the slots behind people. The contract is
[`ingest.openapi.json`](api/ingest.openapi.json). The camera's bearer token
names the camera, and the camera's calibration names its station.

The same interfaces serve a live camera and recorded frames:

| Interface | With a camera | With recorded frames |
|---|---|---|
| [`FrameSource`](../code/edge/sources.py#L25-L26) | `WebcamFrameSource`, or [`SerialFrameSource`](../code/edge/sources.py#L91-L128) for a XIAO board on USB ([camera board](camera-firmware.md)) | [`FolderFrameSource`](../code/edge/sources.py#L29-L56) |
| [`PIIDetector`](../code/edge/pii.py#L27-L28) | [`YoloPIIDetector`](../code/edge/pii.py#L57-L73) for faces and [`TextPIIDetector`](../code/edge/text.py#L32-L52) for plates, merged by [`CombinedPIIDetector`](../code/edge/pii.py#L72-L81) | [`SidecarPIIDetector`](../code/edge/pii.py#L36-L54) |
| [`FrameUploader`](../code/edge/upload.py#L17-L19) | [`IngestClient`](../code/edge/upload.py#L22-L58) | [`DryRunUploader`](../code/edge/upload.py#L61-L67) |

## Backend and classifiers: `OccupancyClassifier`

A classifier gets the whole frame and the slots to read, and returns a reading
per slot number ([`OccupancyClassifier`](../code/backend/classification/classifier.py#L27-L28)).
How it looks at the frame is its own strategy:

- [`JevCropClassifier`](../code/backend/classification/jev.py#L34-L64) crops
  every slot and asks Jev 1.14, through OpenRouter's Decisions API, one yes or
  no question per crop, all in one request.
- [`StaticClassifier`](../code/backend/classification/static.py#L25-L57)
  answers from `data/static-readings.json` and needs no network access.

A new classifier is a class with `classify(frame, slots)`, picked in
[`classifier`](../code/backend/composition.py#L85-L99).

## State: `OccupancyRepository` and `FingerprintStore`

- [`OccupancyRepository`](../code/backend/occupancy/repository.py#L15-L21)
  keeps one `StationOccupancy` per station: each slot's state, confidence and
  report times. It holds no images and nothing about people. A save names the
  version it read, so two writers cannot overwrite each other.
- [`FingerprintStore`](../code/backend/ingest/fingerprints.py#L11-L14) keeps
  each camera's slot fingerprints, so unchanged slots skip the classifier.

Both have an in-memory version for a laptop and a DynamoDB version for AWS.
Only [`composition.py`](../code/backend/composition.py) picks implementations.

## Simulated occupancy

For the demo, and for stations without a camera, the local server simulates
the slots no camera reports
([`OccupancySimulator`](../code/backend/simulation/simulator.py#L32-L107)).
It writes through the same `OccupancyRepository` and state rule as the Ingest
API, so the Availability API, the MCP server and the app read a simulated slot
like a reported one. A working day takes ten minutes: the racks fill in the
morning and empty in the evening, each station a little ahead of the last
([`target`](../code/backend/simulation/simulator.py#L41-L47)). Every eight
seconds each station moves one slot towards that, always leaving one of its
slots free, so no station the simulator fills reads full
([`_step_station`](../code/backend/simulation/simulator.py#L73-L100)). A slot that a
camera reported within `STALE_AFTER_SECONDS` belongs to the camera
([`_is_simulated`](../code/backend/simulation/simulator.py#L102-L104)), so a
new camera takes over its slots without any change to the simulation, and a
camera always reads a slot the simulator reported instead of trusting it. Each
slot stores whether the simulator reported it last, so the simulator keeps no
state of its own. On a laptop it runs in the local server with
`BACKEND_SIMULATION=on`. On AWS, the template's `Simulation=on` parameter adds
a function that a schedule starts every minute, which steps the simulation
every eight seconds until its timeout
([`handler`](../code/backend/simulation/handler.py#L19-L27)).

## Backend and clients: the Availability API and MCP

[`AvailabilityService`](../code/backend/availability/service.py#L33-L70)
answers both the HTTP API ([`availability.openapi.json`](api/availability.openapi.json))
and the MCP server's tools
([`build_server`](../code/backend/availability/mcp_server.py#L31-L58)), with
the same response shapes ([`views.py`](../code/backend/availability/views.py)).
Fields are snake_case in JSON, and station responses carry an `ETag` for
cheap polling.

## iOS app

The app, Easy+Hitch on the home screen with the Endress+Hauser mark as its
icon ([`project.yml`](../code/ios/project.yml)), shows the site map with a pin
per station, a card with the free count and cycling directions, and a 3D view
of the station. The 3D view is three.js
in a web view (`code/ios/BikeSlot/Spot`): it builds the station's rack from the
slot positions in the station detail, lands in front of it, and shows a bike on
every taken slot. Given the rider's position, it navigates instead: it finds
the shortest way along the OpenStreetMap streets and rides it from the rider's
own view in the bike lane, without stopping, turning to face the rack as it
slows down, with low-poly street details only along that way. The 3D view lies
over the map instead of on a screen of its own: the map leans in behind the
rider and fades into it, and the page loads with the app and waits invisibly,
so the change of view never stalls on parsing three.js. The controls are
Liquid Glass on iOS 26 and materials on iOS 18. The live app never asks for
the phone's location; the rider that 3D Navigation starts from is the demo's,
on Christoph-Merian-Ring
([`Backend.rider`](../code/ios/BikeSlot/APIClient.swift#L17-L21)). It ships
sample stations in
`code/ios/BikeSlot/Demo/demo-stations.json`, a snapshot of the live pipeline
taken with `code/ios/refresh-demo.sh` (a station no camera covers gets fixed
sample states there), and in demo mode a random slot changes
every eight seconds, never a station's last free one, so the interface can be
shown and developed without a
backend. Turn it on with the **Demo data** switch in
the app's settings, or launch with `-demoMode YES` (in Xcode, as an argument
of the scheme's Run action). The backend client and the demo both implement
[`StationService`](../code/ios/BikeSlot/APIClient.swift#L5-L8), and
`Backend.current` picks one. A Debug build talks to the backend on the Mac
that built it. Built with the setting `BACKEND_URL=<AvailabilityUrl>`, the app
talks to a deployed backend instead (`code/ios/project.yml`), and the
**Backend URL** field in its settings overrides either.

## 3D scenes and station models

The Availability API serves a station's model from
`data/models/<station_id>.usdz`, and reports `model_url` as `null` for a
station without one. A station model has one node per slot, named
`slot_<number>`, so a client can place a bike on every taken slot and match it
with the slot states. The scene generator in `code/scene-generator` builds
shelter models from layout files in Blender. The app needs no model download:
its 3D view builds the racks itself, from the slot positions in the station
detail.

## Where it runs

| Part | On a laptop | Deployed |
|---|---|---|
| Camera pipeline | `main.py` on the computer the camera is plugged into | The same, on an edge computer at the shelter with a XIAO board on its USB cable, a Mac in our tests |
| Backend | `local:app`, one server that keeps everything in memory | The stack `easyhitch` in AWS's `eu-north-1` region ([`template.yaml`](../code/backend/template.yaml)): the Ingest and Availability functions behind Lambda Function URLs, with `Simulation=on` a Simulation function that a schedule starts every minute, two DynamoDB tables, and the OpenRouter key and the camera token hashes in SSM Parameter Store |
| App | A Debug build reads the backend on the Mac that built it | Built with `BACKEND_URL=<AvailabilityUrl>`, it reads the deployed backend |

[How we tested it](overview.md#how-we-tested-it) lists the runs on both.
