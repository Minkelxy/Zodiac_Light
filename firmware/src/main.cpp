#include <Arduino.h>
#include <FastLED.h>
#include <stdio.h>

#include "config.h"
#include "frame_protocol.h"

namespace {
constexpr uint16_t kLedCount = CLP_LED_COUNT;
constexpr size_t kPayloadSize = static_cast<size_t>(kLedCount) * 3;
static_assert(sizeof(CRGB) == 3, "CLP1 requires packed RGB byte storage");

CRGB frameBuffers[2][kLedCount];
uint8_t front = 0;
uint8_t back = 1;
CLEDController* ledController = nullptr;
clp::FrameParser parser(kLedCount,
                       reinterpret_cast<uint8_t*>(frameBuffers[1]),
                       kPayloadSize, CLP_PACKET_TIMEOUT_MS);
clp::ValidFrameWatchdog watchdog(CLP_STREAM_TIMEOUT_MS);

void acknowledge(uint32_t sequence) {
#if CLP_ENABLE_ACK
  char text[128];
#ifdef CONSTELLATION_COMPACT_SCENE_SHA256
  const int count = sequence == 0
      ? snprintf(text, sizeof(text), "INFO CLP1 %u %s %d\nOK %lu\n",
                 static_cast<unsigned>(kLedCount), CONSTELLATION_COMPACT_SCENE_SHA256,
                 CLP_MODE, static_cast<unsigned long>(sequence))
      : snprintf(text, sizeof(text), "OK %lu\n", static_cast<unsigned long>(sequence));
#else
  const int count = snprintf(text, sizeof(text), "OK %lu\n", static_cast<unsigned long>(sequence));
#endif
  if (count > 0 && static_cast<size_t>(count) < sizeof(text) &&
      Serial.availableForWrite() >= count) {
    Serial.write(reinterpret_cast<const uint8_t*>(text), count);
  }
#else
  (void)sequence;
#endif
}


void publishPacket(uint32_t now) {
  const uint8_t previousFront = front;
  front = back;
  back = previousFront;
  ledController->setLeds(frameBuffers[front], kLedCount);
  parser.setTarget(reinterpret_cast<uint8_t*>(frameBuffers[back]), kPayloadSize);
  FastLED.show();
  watchdog.noteValid(now);
  acknowledge(parser.sequence());
}

void receiveFrames(uint32_t now) {
  parser.tick(now);
  // A bounded drain keeps the display watchdog and scheduler responsive even
  // while the sender writes noise continuously.
  for (uint16_t count = 0; count < 2048 && Serial.available() > 0; ++count) {
    const int byte = Serial.read();
    if (byte < 0) break;
    if (parser.feed(static_cast<uint8_t>(byte), millis())) publishPacket(millis());
  }
  if (watchdog.mustBlank(millis())) {
    fill_solid(frameBuffers[front], kLedCount, CRGB::Black);
    FastLED.show();
    watchdog.didBlank();
  }
}

void localWiringCheck(uint32_t now) {
  static uint32_t lastUpdate = 0;
  static uint16_t position = 0;
  if (static_cast<uint32_t>(now - lastUpdate) < 100) return;
  lastUpdate = now;
  fill_solid(frameBuffers[front], kLedCount, CRGB::Black);
#if CLP_MODE == 1
  frameBuffers[front][position] = CRGB(CLP_LOCAL_LEVEL, CLP_LOCAL_LEVEL, CLP_LOCAL_LEVEL);
  position = (position + 1) % kLedCount;
#elif CLP_MODE == 2
  const uint8_t channel = (now / 1500) % 3;
  const CRGB color(channel == 0 ? CLP_LOCAL_LEVEL : 0,
                   channel == 1 ? CLP_LOCAL_LEVEL : 0,
                   channel == 2 ? CLP_LOCAL_LEVEL : 0);
  fill_solid(frameBuffers[front], kLedCount, color);
#elif CLP_MODE == 3
#ifdef CONSTELLATION_COMPACT_LED_COUNT
  for (uint16_t index = 0; index < kLedCount; ++index) {
    const uint8_t owner = constellation_compact_led_owner_type[index];
    if (owner == CONSTELLATION_COMPACT_LED_STAR)
      frameBuffers[front][index] = CRGB(CLP_LOCAL_LEVEL, CLP_LOCAL_LEVEL / 2, 0);
    else if (owner == CONSTELLATION_COMPACT_LED_EDGE)
      frameBuffers[front][index] = CRGB(0, CLP_LOCAL_LEVEL / 2, CLP_LOCAL_LEVEL);
  }
#else
  // Without a scene header, show dim white solely to test electrical continuity.
  fill_solid(frameBuffers[front], kLedCount,
             CRGB(CLP_LOCAL_LEVEL, CLP_LOCAL_LEVEL, CLP_LOCAL_LEVEL));
#endif
#else
  (void)position;
#endif
  FastLED.show();
}
}  // namespace

void setup() {
  pinMode(CLP_DATA_PIN, OUTPUT);
  digitalWrite(CLP_DATA_PIN, LOW);
  Serial.setRxBufferSize(4096);
  Serial.setTxBufferSize(128);
  Serial.begin(CLP_BAUD, SERIAL_8N1);

  // Protocol bytes are RGB. FastLED changes their wire order to WS2812 GRB.
  ledController = &FastLED.addLeds<WS2812B, CLP_DATA_PIN, GRB>(frameBuffers[front], kLedCount);
  FastLED.setBrightness(255);
  FastLED.setCorrection(UncorrectedColor);
  FastLED.setTemperature(UncorrectedTemperature);
  FastLED.setDither(0);
  // Library power estimation is a second defensive cap, not a current sensor.
  FastLED.setMaxPowerInVoltsAndMilliamps(5, CLP_CURRENT_LIMIT_MA);
  fill_solid(frameBuffers[0], kLedCount, CRGB::Black);
  fill_solid(frameBuffers[1], kLedCount, CRGB::Black);
  FastLED.show();
}

void loop() {
#if CLP_MODE == 0
  receiveFrames(millis());
#else
  localWiringCheck(millis());
#endif
  delay(1);
}
