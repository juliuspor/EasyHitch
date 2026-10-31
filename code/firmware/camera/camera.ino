// Bike slot camera for the Seeed Studio XIAO ESP32S3 Sense.
//
// The board is the camera of an edge computer on its USB cable, which runs
// code/edge with --source serial: the edge sends "c" (a fresh photo) or "f"
// (the buffered frame, for a live view), and the board answers
// "JPEG <length>\n" followed by the JPEG bytes. The board never sends a photo
// anywhere itself, so every frame passes the edge's pixelation before it
// leaves. Other lines on the port are the board's log.
//
// Board: XIAO_ESP32S3, Tools -> PSRAM -> OPI PSRAM.

#include "esp_camera.h"

bool startCamera() {
  camera_config_t config = {};
  config.pin_pwdn = -1;
  config.pin_reset = -1;
  config.pin_xclk = 10;
  config.pin_sccb_sda = 40;
  config.pin_sccb_scl = 39;
  config.pin_d7 = 48;
  config.pin_d6 = 11;
  config.pin_d5 = 12;
  config.pin_d4 = 14;
  config.pin_d3 = 16;
  config.pin_d2 = 18;
  config.pin_d1 = 17;
  config.pin_d0 = 15;
  config.pin_vsync = 38;
  config.pin_href = 47;
  config.pin_pclk = 13;
  config.xclk_freq_hz = 20000000;
  config.ledc_timer = LEDC_TIMER_0;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.pixel_format = PIXFORMAT_JPEG;
  config.frame_size = FRAMESIZE_VGA;  // 640x480
  config.jpeg_quality = 12;           // 0-63, lower is better
  config.fb_count = 1;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;  // only capture when asked, no overflow warnings
  return esp_camera_init(&config) == ESP_OK;
}

// A fresh frame. The buffered one was captured right after the last call, so
// it can be minutes old; drop it and take the next.
camera_fb_t *capture() {
  camera_fb_t *stale = esp_camera_fb_get();
  if (stale) esp_camera_fb_return(stale);
  return esp_camera_fb_get();
}

// "c" sends a fresh photo, "f" the buffered frame right away (for the live
// view, which asks back to back, so that frame is only milliseconds old).
void sendOverUsb() {
  if (!Serial.available()) return;
  char command = Serial.read();
  if (command != 'c' && command != 'f') return;
  camera_fb_t *frame = command == 'c' ? capture() : esp_camera_fb_get();
  if (!frame) {
    Serial.println("Capture failed");
    return;
  }
  Serial.printf("JPEG %u\n", frame->len);
  Serial.write(frame->buf, frame->len);
  Serial.flush();
  esp_camera_fb_return(frame);
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  if (!startCamera()) {
    Serial.println("Camera init failed, check the ribbon cable and PSRAM setting");
    while (true) delay(1000);
  }
  Serial.println("Camera ready");
}

void loop() {
  sendOverUsb();
  delay(5);
}
