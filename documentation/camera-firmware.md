# Camera board: XIAO ESP32S3 Sense

`code/firmware/camera` turns a Seeed Studio XIAO ESP32S3 Sense into the camera
of an edge computer, such as a laptop or a Raspberry Pi, on its USB cable. The
board takes 640x480 JPEGs
([`startCamera`](../code/firmware/camera/camera.ino#L14-L42)) and sends one
whenever the edge asks
([`sendOverUsb`](../code/firmware/camera/camera.ino#L54-L67)):

- `c` asks for a fresh photo, `f` for the frame already in the buffer.
- The board answers `JPEG <length>\n`, then the JPEG bytes. Any other line on
  the port is the board's log.

The board sends nothing on its own, and has no network connection. Every
frame reaches the backend through the edge pipeline, which pixelates faces
and plates first (see [architecture](architecture.md)).

## The edge pipeline reads the board

[`SerialFrameSource`](../code/edge/sources.py#L91-L128) speaks this protocol
over the serial port, with nothing but Python's standard library. It keeps the
JPEG in memory, scales it to the calibrated size, and opens the port again
when the cable was pulled. Without a backend:

```bash
cd code/edge
.venv/bin/pip install -r requirements-camera.txt
.venv/bin/python main.py --source serial --camera-id cam-xiao-1 --size 640x480 --pii yolo --upload dry-run
```

`--port` picks the board's port. By default it is the first
`/dev/cu.usbmodem*` (macOS) or `/dev/ttyACM*` (Linux).

## Feeding the backend

The backend accepts a camera once it knows which slots the camera sees:

1. **Calibration.** Add `code/backend/data/cameras/<camera_id>.json` with the
   station, `"frame_size": [640, 480]` and the pixel box of every slot in view,
   as for the recorded cameras. Check the boxes on a frame with the preview in
   `code/backend/cameras/`.
2. **Token.** Add the camera's token to `code/backend/data/local-cameras.json`,
   and to the tokens file the edge pipeline gets with `--tokens`. On AWS the
   token hashes live in SSM.
3. **Classifier.** Run the backend with Jev (`BACKEND_CLASSIFIER=jev` and an
   OpenRouter key), so the camera's slots are actually read. The local
   `StaticClassifier` needs a fixed reading for every calibrated slot in
   `data/static-readings.json` and ignores the frame.

Then send frames with `--upload http --url http://<backend>:8000 --tokens <file>`.
While the camera reports a slot, it owns it: the
[simulator](../code/backend/simulation/simulator.py) only fills slots no camera
has reported recently.

## On site

On 31 October the board filmed the memox bike shelter in Basel, carried along
the shelter and read over USB
([`assets/camera-tests/memox-2026-10-31`](../assets/camera-tests/memox-2026-10-31)).
On 1 November two of its stills went through the whole pipeline, YOLO11n and
PP-OCRv5 on the edge and Jev in the backend
([How we tested it](overview.md#how-we-tested-it)).

## Flashing (macOS)

1. Arduino IDE: add
   `https://espressif.github.io/arduino-esp32/package_esp32_index.json` under
   Settings → Additional boards manager URLs, install **esp32 by Espressif**,
   pick board **XIAO_ESP32S3** and **PSRAM → OPI PSRAM**. On Apple Silicon the
   build needs Rosetta (`softwareupdate --install-rosetta`), because Arduino's
   bundled `ctags` is an Intel binary.
2. Plug the board in with a USB-C data cable and upload. If no
   `/dev/cu.usbmodem…` port appears, hold **B** (boot) while plugging in.

From the command line, with the CLI bundled in the Arduino IDE:

```bash
CLI="/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli"
FQBN=esp32:esp32:XIAO_ESP32S3:PSRAM=opi
"$CLI" compile --fqbn $FQBN code/firmware/camera
"$CLI" upload --fqbn $FQBN -p /dev/cu.usbmodem* code/firmware/camera
```
