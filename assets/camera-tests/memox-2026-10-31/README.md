# Camera test at memox, 31 October 2026

First footage from the real camera, a Seeed Studio XIAO ESP32S3 Sense
(OV2640, 640x480 JPEG), carried along the bike shelter at memox and read over
USB.

- `shelter-pan.mov`: 86 s of the 13:49 recording (QuickTime, Motion JPEG,
  about 12 fps), trimmed to 0:37–2:03 so no people are in it. The start
  showed team members and the end two passing cyclists who did not agree to be
  filmed.
- `photos/`: 23 stills taken during the same walk, 13:50:14–13:51:33.

We used it to aim the camera and check its image quality. On 1 November two
of the stills went through the whole pipeline, YOLO11n and PP-OCRv5 on the
edge and Jev in the backend, with the racks in view calibrated for the test
([How we tested it](../../../documentation/overview.md#how-we-tested-it)). The
backend never stores frames; these were saved on purpose for the team.
