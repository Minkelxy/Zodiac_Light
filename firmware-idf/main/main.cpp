#include <stdio.h>
#include <string.h>

#include "sdkconfig.h"
#include "driver/gpio.h"
#include "driver/rmt_tx.h"
#include "driver/uart.h"
#include "esp_check.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "constellation_compact.h"
#include "frame_protocol.h"
#include "output_transform.h"
#include "ws2812_encoder.h"
#include "native_effects.h"
#if defined(__has_include)
#if __has_include("native_presets.h")
#include "native_presets.h"
#define CLP_HAS_NATIVE_PRESETS 1
#endif
#endif

namespace {
constexpr uint16_t kLedCount = CONFIG_CLP_LED_COUNT;
constexpr size_t kFrameBytes = static_cast<size_t>(kLedCount) * 3;
constexpr uint32_t kResolutionHz = 40000000;
constexpr uart_port_t kUart = UART_NUM_0;
static_assert(kLedCount == CONSTELLATION_COMPACT_LED_COUNT,
              "Menuconfig LED count must match the exported compact scene");
static_assert(kLedCount > 0 && kLedCount <= 1024, "Frame storage is bounded");
static_assert(static_cast<uint64_t>(CONFIG_CLP_CURRENT_LIMIT_MA) * 1000 >=
                  static_cast<uint64_t>(kLedCount) * CONFIG_CLP_IDLE_LED_UA,
              "Current budget cannot be below estimated idle current");
static_assert(CONFIG_CLP_DATA_GPIO != 1 && CONFIG_CLP_DATA_GPIO != 3,
              "WS2812 output must not reuse UART0 TX/RX");
constexpr bool validDataGpio(int pin) {
  return pin == 0 || pin == 2 || pin == 4 || pin == 5 ||
         (pin >= 12 && pin <= 19) || (pin >= 21 && pin <= 23) ||
         (pin >= 25 && pin <= 27) || pin == 32 || pin == 33;
}
static_assert(validDataGpio(CONFIG_CLP_DATA_GPIO),
              "Choose a classic ESP32 output GPIO outside flash/UART pins");
static_assert(CONFIG_CLP_LOCAL_MODE != 4 ||
                  CONFIG_CLP_NATIVE_FPS * (kLedCount * 30UL + CONFIG_CLP_RESET_US) <= 1000000,
              "Native FPS exceeds the WS2812 frame-time budget");

uint8_t rgbFrames[2][kFrameBytes];
uint8_t grb[kFrameBytes];
uint8_t rxChunk[256];
uint8_t front = 0;
uint8_t back = 1;
rmt_channel_handle_t channel = nullptr;
rmt_encoder_handle_t encoder = nullptr;
clp::FrameParser parser(kLedCount, rgbFrames[1], kFrameBytes, CONFIG_CLP_PACKET_TIMEOUT_MS);
clp::ValidFrameWatchdog watchdog(CONFIG_CLP_STREAM_TIMEOUT_MS);

#if CONFIG_CLP_LOCAL_MODE == 4
clp::RenderContext nativeContext;
clp::NativeParams nativeParams;
uint64_t nativeStartedUs = 0;
uint64_t nativeLastUs = 0;

void initializeNativeEffect() {
#ifdef CLP_HAS_NATIVE_PRESETS
  nativeParams = clp::generatedNativeParams(CONFIG_CLP_NATIVE_EFFECT);
#else
  nativeParams.effect = static_cast<clp::Effect>(CONFIG_CLP_NATIVE_EFFECT);
#endif
  ESP_ERROR_CHECK(clp::initNativeEffects(nativeContext, nativeParams) == clp::RenderError::Ok
                      ? ESP_OK : ESP_ERR_INVALID_ARG);
  nativeStartedUs = static_cast<uint64_t>(esp_timer_get_time());
}
#endif

uint32_t nowMs() { return static_cast<uint32_t>(esp_timer_get_time() / 1000); }

void showFront() {
  clp::rgbToGrbLimited(rgbFrames[front], grb, kLedCount,
                      CONFIG_CLP_CURRENT_LIMIT_MA, CONFIG_CLP_IDLE_LED_UA,
                      CONFIG_CLP_CHANNEL_UA);
  rmt_transmit_config_t config = {};
  config.loop_count = 0;
  config.flags.eot_level = 0;
  ESP_ERROR_CHECK(rmt_transmit(channel, encoder, grb, sizeof(grb), &config));
  // grb remains unchanged until the interrupt-driven encoder finishes. A
  // driver timeout aborts/restarts the firmware and cannot emit a false ACK.
  ESP_ERROR_CHECK(rmt_tx_wait_all_done(channel, 100));
}

void acknowledge(uint32_t sequence) {
  char text[128];
  // Publish readiness identity and its ACK together, without waiting for TX
  // capacity. A full queue drops both; the host will retry the black packet.
  const int length = sequence == 0
      ? snprintf(text, sizeof(text), "INFO CLP1 %u %s %d\nOK %lu\n",
                 static_cast<unsigned>(kLedCount), CONSTELLATION_COMPACT_SCENE_SHA256,
                 CONFIG_CLP_LOCAL_MODE, static_cast<unsigned long>(sequence))
      : snprintf(text, sizeof(text), "OK %lu\n", static_cast<unsigned long>(sequence));
  size_t freeBytes = 0;
  if (length > 0 && static_cast<size_t>(length) < sizeof(text) &&
      uart_get_tx_buffer_free_size(kUart, &freeBytes) == ESP_OK &&
      freeBytes >= static_cast<size_t>(length)) {
    uart_write_bytes(kUart, text, length);
  }
}


void publishPacket() {
  const uint8_t oldFront = front;
  front = back;
  back = oldFront;
  parser.setTarget(rgbFrames[back], kFrameBytes);
  showFront();
  watchdog.noteValid(nowMs());
  acknowledge(parser.sequence());
}

void receiveFrames() {
  parser.tick(nowMs());
  // Read at most 2048 available bytes per iteration, with no blocking UART
  // reads. Complete packets are displayed before any acknowledgement.
  for (unsigned total = 0; total < 2048;) {
    const int count = uart_read_bytes(kUart, rxChunk, sizeof(rxChunk), 0);
    if (count <= 0) break;
    total += count;
    for (int i = 0; i < count; ++i) {
      if (parser.feed(rxChunk[i], nowMs())) publishPacket();
    }
  }
  if (watchdog.mustBlank(nowMs())) {
    memset(rgbFrames[front], 0, kFrameBytes);
    showFront();
    watchdog.didBlank();
  }
}

void localWiringCheck() {
  static uint32_t lastUpdate = 0;
  static uint16_t position = 0;
  const uint32_t now = nowMs();
  if (static_cast<uint32_t>(now - lastUpdate) < 100) return;
  lastUpdate = now;
  memset(rgbFrames[front], 0, kFrameBytes);
  if (CONFIG_CLP_LOCAL_MODE == 1) {
    const size_t offset = static_cast<size_t>(position) * 3;
    rgbFrames[front][offset] = CONFIG_CLP_LOCAL_LEVEL;
    rgbFrames[front][offset + 1] = CONFIG_CLP_LOCAL_LEVEL;
    rgbFrames[front][offset + 2] = CONFIG_CLP_LOCAL_LEVEL;
    position = (position + 1) % kLedCount;
  } else if (CONFIG_CLP_LOCAL_MODE == 2) {
    const uint8_t color = (now / 1500) % 3;
    for (size_t led = 0; led < kLedCount; ++led)
      rgbFrames[front][led * 3 + color] = CONFIG_CLP_LOCAL_LEVEL;
  } else if (CONFIG_CLP_LOCAL_MODE == 3) {
    for (size_t led = 0; led < kLedCount; ++led) {
      const uint8_t owner = constellation_compact_led_owner_type[led];
      if (owner == CONSTELLATION_COMPACT_LED_STAR) {
        rgbFrames[front][led * 3] = CONFIG_CLP_LOCAL_LEVEL;
        rgbFrames[front][led * 3 + 1] = CONFIG_CLP_LOCAL_LEVEL / 2;
      } else if (owner == CONSTELLATION_COMPACT_LED_EDGE) {
        rgbFrames[front][led * 3 + 1] = CONFIG_CLP_LOCAL_LEVEL / 2;
        rgbFrames[front][led * 3 + 2] = CONFIG_CLP_LOCAL_LEVEL;
      }
    }
  }
  showFront();
}

void localNativeEffect() {
#if CONFIG_CLP_LOCAL_MODE == 4
  const uint64_t nowUs = static_cast<uint64_t>(esp_timer_get_time());
  if (nowUs - nativeLastUs < 1000000UL / CONFIG_CLP_NATIVE_FPS) return;
  nativeLastUs = nowUs;
  ESP_ERROR_CHECK(clp::renderNativeEffects(nativeContext, (nowUs - nativeStartedUs) / 1000,
                                         nativeParams, rgbFrames[front], kFrameBytes) == clp::RenderError::Ok
                      ? ESP_OK : ESP_ERR_INVALID_STATE);
  showFront();
#endif
}

void initializeUart() {
  uart_config_t config = {};
  config.baud_rate = CONFIG_CLP_BAUD;
  config.data_bits = UART_DATA_8_BITS;
  config.parity = UART_PARITY_DISABLE;
  config.stop_bits = UART_STOP_BITS_1;
  config.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
  config.source_clk = UART_SCLK_DEFAULT;
  ESP_ERROR_CHECK(uart_param_config(kUart, &config));
  ESP_ERROR_CHECK(uart_set_pin(kUart, GPIO_NUM_1, GPIO_NUM_3,
                             UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
  // TX ring must be strictly larger than the classic ESP32 128-byte FIFO.
  ESP_ERROR_CHECK(uart_driver_install(kUart, 4096, 256, 0, nullptr, 0));
}

void initializeLeds() {
  const gpio_num_t gpio = static_cast<gpio_num_t>(CONFIG_CLP_DATA_GPIO);
  ESP_ERROR_CHECK(gpio_set_direction(gpio, GPIO_MODE_OUTPUT));
  ESP_ERROR_CHECK(gpio_set_level(gpio, 0));
  rmt_tx_channel_config_t config = {};
  config.gpio_num = gpio;
  config.clk_src = RMT_CLK_SRC_DEFAULT;
  config.resolution_hz = kResolutionHz;
  config.mem_block_symbols = 64;
  config.trans_queue_depth = 1;
  ESP_ERROR_CHECK(rmt_new_tx_channel(&config, &channel));
  ESP_ERROR_CHECK(clp_new_ws2812_encoder(kResolutionHz, CONFIG_CLP_RESET_US, &encoder));
  ESP_ERROR_CHECK(rmt_enable(channel));
  memset(rgbFrames, 0, sizeof(rgbFrames));
  showFront();
}
}  // namespace

extern "C" void app_main() {
  esp_log_level_set("*", ESP_LOG_NONE);
  initializeUart();
  initializeLeds();
#if CONFIG_CLP_LOCAL_MODE == 4
  initializeNativeEffect();
#endif
  for (;;) {
    if (CONFIG_CLP_LOCAL_MODE == 0) receiveFrames();
    else if (CONFIG_CLP_LOCAL_MODE == 4) localNativeEffect();
    else localWiringCheck();
    vTaskDelay(pdMS_TO_TICKS(1));
  }
}
