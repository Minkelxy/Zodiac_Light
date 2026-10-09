#ifndef CONSTELLATION_LAMP_FIRMWARE_CONFIG_H
#define CONSTELLATION_LAMP_FIRMWARE_CONFIG_H

// The generated scene is optional for the streaming receiver. Its LED count
// must match the physical chain and the Python runtime used by the sender.
#if defined(__has_include)
#if __has_include("constellation_compact.h")
#include "constellation_compact.h"
#endif
#endif

#ifndef CLP_LED_COUNT
#ifdef CONSTELLATION_COMPACT_LED_COUNT
#define CLP_LED_COUNT CONSTELLATION_COMPACT_LED_COUNT
#else
#define CLP_LED_COUNT 268
#endif
#endif
#ifndef CLP_MAX_LEDS
#define CLP_MAX_LEDS 1024
#endif
#ifndef CLP_DATA_PIN
#define CLP_DATA_PIN 18
#endif
#ifndef CLP_BAUD
#define CLP_BAUD 460800
#endif
#ifndef CLP_CURRENT_LIMIT_MA
#define CLP_CURRENT_LIMIT_MA 2000
#endif
#ifndef CLP_STREAM_TIMEOUT_MS
#define CLP_STREAM_TIMEOUT_MS 1000
#endif
#ifndef CLP_PACKET_TIMEOUT_MS
#define CLP_PACKET_TIMEOUT_MS 250
#endif
#ifndef CLP_ENABLE_ACK
#define CLP_ENABLE_ACK 1
#endif
#ifndef CLP_MODE
#define CLP_MODE 0
#endif
#ifndef CLP_LOCAL_LEVEL
#define CLP_LOCAL_LEVEL 16
#endif

static_assert(CLP_LED_COUNT > 0 && CLP_LED_COUNT <= CLP_MAX_LEDS,
              "CLP_LED_COUNT must fit the configured maximum");
static_assert(CLP_LED_COUNT <= 65535 / 3, "CLP1 payload length is uint16");
static_assert(CLP_CURRENT_LIMIT_MA > 0, "The current estimate limit must be positive");
static_assert(CLP_STREAM_TIMEOUT_MS > 0 && CLP_STREAM_TIMEOUT_MS < 0x80000000UL,
              "Stream timeout must fit wrap-safe uint32 subtraction");
static_assert(CLP_PACKET_TIMEOUT_MS > 0 && CLP_PACKET_TIMEOUT_MS < 0x80000000UL,
              "Packet timeout must fit wrap-safe uint32 subtraction");
static_assert(CLP_MODE >= 0 && CLP_MODE <= 3, "Mode is stream(0), chase(1), RGB(2), parts(3)");
static_assert(CLP_LOCAL_LEVEL > 0 && CLP_LOCAL_LEVEL <= 32,
              "Wiring tests use a low level of 1..32");
#ifdef CONSTELLATION_COMPACT_LED_COUNT
static_assert(CLP_LED_COUNT == CONSTELLATION_COMPACT_LED_COUNT,
              "CLP_LED_COUNT disagrees with the exported compact scene");
#endif

#endif
