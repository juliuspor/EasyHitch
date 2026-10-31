# Judging criteria

BaselHack 2026 rates every project on these criteria:

| Criterion | What it means |
|---|---|
| Innovation | A value proposition that stands out |
| Impact | Social, economic, and technical relevance |
| Technical depth | How well it is built |
| AI code review | Quality of the code and the commit history |
| Fair play | Staying within the hackathon rules |
| Pitch | Clear story, confident delivery |
| Demo | It works, live |

This page maps each criterion to the code that meets it. Every claim links to
the code behind it, and [What we checked](#what-we-checked) lists the commands
we ran and their results. The sponsor's brief is summarised in
[`challenge.md`](challenge.md).

## At a glance

| Criterion | Easy+Hitch | Details |
|---|---|---|
| Innovation | Which exact slot is free, read from a camera image by a decision model without training data, for riders and for AI agents | [Innovation](#innovation) |
| Impact | Less searching at 7:45, low-cost cameras, model calls only for slots that changed, privacy by design | [Impact](#impact) |
| Technical depth | One pipeline from camera frame to slot states, with swappable parts, running on a laptop and on AWS Lambda | [Technical depth](#technical-depth) |
| AI code review | Every commit follows the format in `AGENTS.md`, and the code is organised by feature with one composition root | [AI code review](#ai-code-review) |
| Fair play | Built during the event, the challenge's rules enforced in code, third parties credited | [Fair play](#fair-play) |
| Pitch | Four slides, one story, speaker notes and a timer | [Pitch](#pitch) |
| Demo | A live pipeline, an offline mode in the app, and the deck | [Demo](#demo) |

## Innovation

**Spot level, not "the stand is full".** The API reports every slot, not just
a count ([`SlotDetail`](../code/backend/availability/views.py#L34-L38),
[`StationDetail`](../code/backend/availability/views.py#L41-L51)). The app
shows each station in a 3D model of the block, with every slot where the
station catalog measured it, a bike on every taken slot, and a grey pad where
no camera looked recently
([`SpotView`](../code/ios/BikeSlot/SpotView.swift#L10-L73)), above a card with
the free count
([`StatusCard`](../code/ios/BikeSlot/StationScreen.swift#L56-L98)).

**No training data.** The backend crops every slot and asks Jev 1.14, a
decision model, one yes or no question per crop
([`JevCropClassifier`](../code/backend/classification/jev.py#L34-L64)). Jev
answers with a calibrated probability, so the backend changes a slot only on a
sure answer or on two unsure answers that agree
([`decide`](../code/backend/occupancy/decider.py#L14-L25)). A new station
needs a calibration ([`load_camera`](../code/backend/cameras/camera.py#L51-L65)),
not a trained model.

**Built for agents as well as apps.** An MCP server answers the same questions
as the API, so an AI agent can tell a rider where to park
([`build_server`](../code/backend/availability/mcp_server.py#L31-L58)).

**Privacy at the source.** Faces and readable licence plates are pixelated
before a frame leaves the camera
([`EdgePipeline`](../code/edge/pipeline.py#L26-L53)), and the backend only
ever looks at slot crops.

**Found before you arrive.** Search for the building you are cycling to, and
the app opens the closest shelter that still has room
([`go`](../code/ios/BikeSlot/MapScreen.swift#L90-L100)).

## Impact

- **Social.** Riders stop circling full shelters at 7:45, which makes cycling
  to work easier to choose. Free and taken are green and red, and never by
  colour alone: pins and cards carry the free count, and in 3D a taken slot
  holds a bike ([`Brand`](../code/ios/BikeSlot/Theme.swift#L4-L16)). Nobody is watched: the
  backend keeps slot states only (see [Fair play](#fair-play)).
- **Economic.** The camera pipeline is designed for the low-cost ESP32 boards
  the challenge provides. A camera uploads only when its view changed
  ([`ChangeDetector`](../code/edge/change.py#L13-L31)), and the backend asks
  Jev only about the slots whose fingerprint changed
  ([`has_changed`](../code/backend/ingest/frame.py#L51-L57)). The model is paid
  for when a bike arrives or leaves, not per frame, and the serverless
  backend costs next to nothing while nobody parks.
- **Technical.** Every slot carries when it last changed and when a camera
  last saw it ([`SlotOccupancy`](../code/backend/occupancy/model.py#L16-L32)).
  The APIs are open contracts
  ([`availability.openapi.json`](api/availability.openapi.json),
  [`ingest.openapi.json`](api/ingest.openapi.json)), and the MCP server makes
  the data available to any AI agent.

## Technical depth

**One pipeline.** A camera posts a pixelated JPEG, the backend fingerprints
every slot, reads only the changed ones, applies the state rule and stores the
result ([`ingest`](../code/backend/ingest/service.py#L37-L52)). The
Availability API and the MCP server answer from the stored states
([`AvailabilityService`](../code/backend/availability/service.py#L33-L70)).

**Parts behind interfaces**, so the camera pipeline, the backend, the app and
the 3D scenes are built in parallel ([architecture.md](architecture.md)):

| Interface | Implementations |
|---|---|
| [`OccupancyClassifier`](../code/backend/classification/classifier.py#L27-L28) | [`JevCropClassifier`](../code/backend/classification/jev.py#L34-L64) and [`StaticClassifier`](../code/backend/classification/static.py#L25-L57) |
| [`OccupancyRepository`](../code/backend/occupancy/repository.py#L15-L21) | [`InMemoryOccupancyRepository`](../code/backend/occupancy/repository.py#L24-L44) and [`DynamoOccupancyRepository`](../code/backend/occupancy/dynamodb.py#L22-L58) |
| [`FingerprintStore`](../code/backend/ingest/fingerprints.py#L11-L14) | [`InMemoryFingerprintStore`](../code/backend/ingest/fingerprints.py#L17-L28) and [`DynamoFingerprintStore`](../code/backend/ingest/dynamodb.py#L9-L22) |
| [`FrameSource`](../code/edge/sources.py#L14-L15), [`PIIDetector`](../code/edge/pii.py#L27-L28), [`FrameUploader`](../code/edge/upload.py#L17-L19) on the camera | A camera with YOLO11n, PP-OCRv5 and HTTP, or recorded frames with marked regions and a dry run |
| [`StationService`](../code/ios/BikeSlot/APIClient.swift#L5-L8) in the app | [`APIClient`](../code/ios/BikeSlot/APIClient.swift#L19-L69) and [`DemoService`](../code/ios/BikeSlot/Demo/DemoService.swift#L6-L45) |

One place picks the implementations from the environment
([`classifier`](../code/backend/composition.py#L84-L98)), so the same code runs
on a laptop with nothing installed and on AWS Lambda with DynamoDB, as defined
in [`template.yaml`](../code/backend/template.yaml).

**Built for real conditions.**

- A person in view hides slots, so the camera sends person boxes and the
  backend leaves the slots behind them as they were
  ([`ingest`](../code/backend/ingest/service.py#L37-L52)).
- A slot no camera reported for 10 minutes reads `unknown` instead of an old
  state ([`current_state`](../code/backend/occupancy/model.py#L25-L29)).
- Jev's answers are checked. A missing answer or a probability outside 0 to 1
  fails the frame instead of being misread, and the camera sends it again
  ([`_reading`](../code/backend/classification/jev.py#L106-L109),
  [`_read`](../code/backend/ingest/service.py#L54-L61)).
- Two cameras of one station cannot overwrite each other: a save names the
  version it read, and a conflict is retried once
  ([`_save`](../code/backend/ingest/service.py#L63-L69),
  [`save`](../code/backend/occupancy/dynamodb.py#L51-L58)).
- Bad input fails cleanly, as problem details: unknown token 401, not a JPEG
  415, too large 413, wrong frame size or headers 422
  ([`create_router`](../code/backend/ingest/api.py#L33-L80)).
- A broken configuration stops the backend at start with a clear message
  ([`Settings`](../code/backend/settings.py#L33-L88)).
- The app runs from iOS 18 and uses Liquid Glass on iOS 26 or later
  ([`glassBackground`](../code/ios/BikeSlot/Glass.swift#L3-L31)).

## AI code review

**Commit history.** [`AGENTS.md`](../AGENTS.md) sets the rules: Conventional
Commits with a scope, small focused commits, linear history on `main`, and
only team members as authors. On 31 October 2026, at commit `7622cae`, all 18
commits on `main` matched the format, all were authored by three team members,
none carried AI attribution, and no keys or tokens were found anywhere in the
history. Anyone can rerun the checks:

```bash
git log --format=%s | grep -Ev '^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)\([a-z0-9]+(-[a-z0-9]+)*\)!?: \S(.*\S)?$'
git log --format='%an' | sort | uniq -c
git log --format=%B | grep -iE 'co-authored-by|generated with'
git log --all -p | grep -E 'sk-ant-[A-Za-z0-9_-]{8,}|sk-or-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16}|BEGIN [A-Z ]*PRIVATE KEY'
```

All but the second print nothing.

**Code quality.**

- The code is organised by feature, and one composition root picks every
  implementation ([composition.py](../code/backend/composition.py#L1-L8)).
  Services receive their dependencies through their constructors.
- The modules open with what they are for and how they fit in
  ([ingest/service.py](../code/backend/ingest/service.py#L1),
  [classification/jev.py](../code/backend/classification/jev.py#L1-L9)).
  Comments explain why rather than what, for example why a sure reading needs
  0.85 ([`CONFIDENT_READING`](../code/backend/occupancy/decider.py#L11)) or why
  every Lambda invocation gets a fresh app
  ([`handler`](../code/backend/availability/handler.py#L16-L20)).
- Keys come from the environment or AWS Systems Manager only
  ([`Settings`](../code/backend/settings.py#L33-L88)), and each Lambda
  function imports only the code its own service needs.
- Generated files stay out of git: the Python virtual environments and caches,
  SAM build output, YOLO and PP-OCRv5 weights, the scene generator's `out/`,
  Xcode build folders, and macOS Finder files
  ([backend](../code/backend/.gitignore),
  [edge](../code/edge/.gitignore),
  [scene generator](../code/scene-generator/.gitignore),
  [iOS](../code/ios/.gitignore), [root](../.gitignore)). The API specs are
  generated and committed on purpose
  ([`export_openapi.py`](../code/backend/export_openapi.py)).

## Fair play

- **Built at the event.** The repository starts from the BaselHack template
  (`f33cc57`: the readme, the licence, and empty `code/`, `documentation/`,
  and `assets/` folders), and every commit is dated 30 or 31 October 2026
  (`git log --all --format=%ad --date=short | sort -u`).
- **Template structure.** Code is in `code/`, documentation in
  `documentation/`, and media in `assets/`, as the template asks
  ([`AGENTS.md`](../AGENTS.md)).
- **The challenge's rules hold in code.**
  - Faces and readable licence plates are pixelated before a frame leaves the
    camera ([`pixelate`](../code/edge/pixelate.py#L12-L22)). YOLO11n finds
    people and the top fifth of each person box is treated as the face
    ([`face_region`](../code/edge/pii.py#L31-L33)). PP-OCRv5 finds readable
    text, so plates of every format count, the yellow e-bike plates included,
    and each text line grows by two line heights to cover the whole plate
    ([`TextPIIDetector`](../code/edge/text.py#L32-L52)). The sidecar of a
    recorded frame lists the same regions by hand
    ([`SidecarPIIDetector`](../code/edge/pii.py#L36-L54)).
  - No images are kept. The ingest service decodes each frame in memory and
    stores only slot states and times
    ([`ingest`](../code/backend/ingest/service.py#L37-L52)), and the state has
    no field for images or people
    ([`SlotOccupancy`](../code/backend/occupancy/model.py#L16-L32)). Jev only
    sees slot crops ([`JevCropClassifier`](../code/backend/classification/jev.py#L34-L64)),
    and no request path writes a file.
  - Nobody is identified or tracked. A classifier answers "taken or free" per
    slot ([`Reading`](../code/backend/classification/classifier.py#L18-L20)),
    and person boxes only decide which slots to skip. Nothing links a slot or
    a frame to a person.
- **Third parties credited.** Python packages are listed in the
  [backend](../code/backend/requirements.txt) and
  [edge](../code/edge/requirements.txt) requirements. YOLO11n and Ultralytics
  are AGPL-3.0 and only installed for a live camera
  ([`requirements-camera.txt`](../code/edge/requirements-camera.txt)).
  PaddlePaddle's PP-OCRv5 text detector is Apache-2.0, downloaded only for a
  live camera and checked against its pinned SHA-256
  ([`_pinned_model`](../code/edge/text.py#L64-L70)). The deck
  bundles canvas-confetti with its
  [ISC licence](../assets/pitch/vendor/LICENSE-canvas-confetti), and its
  architecture slide uses brand icons from Simple Icons under CC0. The marks
  belong to their owners. The campus map data comes from OpenStreetMap under
  the ODbL, attributed in the
  [readme](../readme.md#credits). The recorded frames are the hosts' photos.
  The Endress+Hauser symbol comes from endress.com and is used for the
  sponsor's own challenge. The diagrams are rendered with archify 3.2.0.
- **Sponsor resources.** The CHF 100 AI budget pays for Jev through
  OpenRouter. The fixed readings need no budget.
- **Authorship.** Only real team members appear as authors or co-authors, with
  no AI attribution ([`AGENTS.md`](../AGENTS.md#attribution)).

Jev receives slot crops through OpenRouter and TypeSafe for one answer each.
Easy+Hitch stores neither crops nor frames, and the fixed readings send
nothing anywhere.

## Pitch

The deck, [`assets/pitch/index.html`](../assets/pitch/index.html), has four
slides and one story: the 7:45 problem, the live demo, the pipeline, and a
finale. It runs offline in a browser, and only its web fonts need a
connection. Each slide has speaker notes
([`NOTES`](../assets/pitch/index.html#L323-L328), press N). Press T for a
three-minute timer that turns yellow at 2:30 and red at 3:00
([`setInterval`](../assets/pitch/index.html#L352-L356)).

| Time | Slide | Focus |
|---|---|---|
| 0:00 to 0:40 | Hello | Problem at 7:45, value proposition, impact |
| 0:40 to 2:00 | Demo | The app and the live pipeline |
| 2:00 to 2:45 | Tech | Pipeline, privacy by design |
| 2:45 to 3:00 | Finale | One-line close while the hamster lands: "You ride, we find the spot." |

## Demo

Three ways to show it:

1. **Live pipeline.** Start the backend and the recorded cameras
   ([backend README](../code/backend/README.md#run-locally),
   [edge README](../code/edge/README.md#run)), then watch the stations fill in
   at `/v1/stations`, or ask an AI agent through the MCP server where to park.
2. **The app.** With the **Demo data** setting, or launched with
   `-demoMode YES`, built-in stations change every four seconds without a
   backend ([`Backend`](../code/ios/BikeSlot/APIClient.swift#L10-L16),
   [`DemoService`](../code/ios/BikeSlot/Demo/DemoService.swift#L6-L45)).
3. **The deck.** The phone screen on slide 2 plays the app on its own.

A camera board uses the same route as the recorded cameras
([`IngestClient`](../code/edge/upload.py#L22-L58)), with a calibration in
`data/cameras/<camera_id>.json` for its view of the station.

## What we checked

On 31 October 2026, on macOS with Python 3.13.16:

| Check | How | Result |
|---|---|---|
| Pipeline, end to end | Local backend, then the recorded cameras for two rounds | All 7 cameras accepted. North: 26 free, 9 taken, 10 unknown. South: 10 free, 10 taken. The second round sent nothing |
| Bad input | No or wrong token, PNG body, 1.1 MB body, missing `X-Captured-At`, bad `X-Person-Boxes`, 640x480 frame | 401, 415, 413, 422, 422, 422, as problem details |
| ETag | `If-None-Match` with the station list's ETag | 304 |
| MCP | All three tools through the MCP Python SDK's client | Correct answers. An unknown station and a latitude of 120 return tool errors |
| AWS Lambda | `cfn-lint`, SAM's transform, `sam build` for arm64, and both handlers invoked with Function URL events against DynamoDB and SSM on moto | Valid template, each function gets only its own permissions, 81 MB package, frame ingested with the SSM token, stations listed, MCP answered on repeated invocations |
| DynamoDB and SSM code | The repositories and the parameter reader against moto | Versioned saves, conflicts rejected, 72-bit fingerprints kept |
| Jev request | `JevCropClassifier` against a stand-in for the Decisions API | Request as documented, crops within Jev's size limits, errors become `502` |
| YOLO11n | `YoloPIIDetector` on `IMG_20261029_084104` | Finds the person at the right edge |
| PP-OCRv5 | `TextPIIDetector` and `pixelate` on the seven recorded frames, sidecars ignored, each result checked by eye | The five readable plates in `cam-north-1`, `cam-north-2` and `cam-south-a` come out unreadable, the two yellow e-bike plates and a tilted motorbike plate among them. 2% of a frame is pixelated on average, 6% at most, in 0.1 s per frame |
| iOS app | Built for iOS 18, run in the iPhone 17 Pro simulator against the local backend with the recorded cameras, then in demo mode | Both stations on the map. North: 26 of 45 free, 10 not seen by a camera, grey in 3D. South: slots 1 to 10 and 11 to 20 as two racks on two sides of the building, and the 3D view flies between them. Demo counts change every four seconds |
