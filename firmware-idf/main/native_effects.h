#ifndef CONSTELLATION_LAMP_NATIVE_EFFECTS_H
#define CONSTELLATION_LAMP_NATIVE_EFFECTS_H

#include <stddef.h>
#include <stdint.h>
#include "constellation_compact.h"

namespace clp {

enum class Effect : uint8_t { Twinkle, Flow, Ripple, Breath, Aurora, Sparkle, GraphWave, Draw, Meteor };
enum class RenderError : uint8_t { Ok, InvalidParams, InvalidScene, InvalidRoute, NotInitialized,
                                  RequiresInit, OutputTooSmall, TimeOverflow };
constexpr size_t kNativeRouteCapacity = CONSTELLATION_COMPACT_STAR_COUNT * 2;

// Defaults match data/effects.json / the Python effect defaults. Source is a
// compact star index (-1 chooses the brightest star with HIP tie-breaking).
// Route count 0 requests the graph diameter path; custom routes may repeat.
struct NativeParams {
  Effect effect = Effect::Twinkle;
  uint32_t seed = 1;
  double brightness = 0.2;
  double speed = 1.0;
  double gamma = 2.2;
  int16_t source_star = -1;
  uint16_t route_count = 0;
  uint16_t route[kNativeRouteCapacity] = {};
  double pitch_mm = 5.0;
  bool custom_center = false;
  double center_x_mm = 0;
  double center_y_mm = 0;
  double flow_velocity_mm_s = 140;
  double flow_width_mm = 35;
  double flow_period_s = 0;  // Optional authoritative cycle from full scene.
  double wavelength_mm = 180;
  double ripple_velocity_mm_s = 90;
  double breath_period_s = 6;
  double breath_floor = 0.08;
  double aurora_wavelength_mm = 220;
  double aurora_velocity_mm_s = 22;
  double aurora_contrast = 0.65;
  double sparkle_period_s = 3.2;
  double sparkle_duration_s = 0.8;
  double sparkle_density = 0.85;
  double graph_velocity_mm_s = 100;
  double graph_width_mm = 25;
  double graph_period_s = 0;  // 0 means automatic.
  double draw_velocity_mm_s = 160;
  double draw_hold_s = 2.5;
  double draw_fade_s = 1.5;
  double draw_head_width_mm = 20;
  double draw_period_s = 0;  // Optional authoritative total draw/hold/fade cycle.
  double meteor_angle_deg = -35;
  double meteor_velocity_mm_s = 220;
  double meteor_tail_mm = 80;
  double meteor_width_mm = 45;
  double meteor_interval_s = 0;  // 0 means automatic.
};

// Caller-owned, independently reentrant, fixed-size workspace. No pointers to
// external mutable state and no dynamic allocation. Allocate this statically
// on the MCU rather than on a small FreeRTOS task stack.
struct RenderContext {
  bool initialized = false;
  uint32_t seed = 0;
  int16_t source_config = 0;
  uint16_t source = 0;
  uint16_t route_config_count = 0;
  uint16_t route_config[kNativeRouteCapacity] = {};
  double phase[CONSTELLATION_COMPACT_STAR_COUNT] = {};
  double rate[CONSTELLATION_COMPACT_STAR_COUNT] = {};
  double magnitude[CONSTELLATION_COMPACT_STAR_COUNT] = {};
  double seed_phase = 0;
  double center_x = 0, center_y = 0;
  double graph_distance[CONSTELLATION_COMPACT_LED_COUNT] = {};
  double graph_max = 0;
  double draw_distance[CONSTELLATION_COMPACT_LED_COUNT] = {};
  double draw_length = 0;
  uint16_t draw_edges[CONSTELLATION_COMPACT_EDGE_COUNT] = {};
  bool draw_reverse[CONSTELLATION_COMPACT_EDGE_COUNT] = {};
  uint16_t route_stars[kNativeRouteCapacity] = {};
  uint16_t route_edges[kNativeRouteCapacity] = {};
  bool route_reverse[kNativeRouteCapacity] = {};
  double route_offset[kNativeRouteCapacity] = {};
  uint16_t route_size = 0;
  double route_length = 0;
  double work[CONSTELLATION_COMPACT_LED_COUNT][3] = {};
};

const char* effectName(Effect effect);
const char* renderErrorName(RenderError error);
RenderError initNativeEffects(RenderContext& context, const NativeParams& params);
// Frames can be requested out of order. Output is RGB in serial LED order,
// with one gamma -> global-brightness transform and explicit ties-to-even.
// On error the caller's RGB buffer is left unchanged.
RenderError renderNativeEffects(RenderContext& context, uint64_t time_ms,
                                const NativeParams& params, uint8_t* rgb,
                                size_t capacity);

}  // namespace clp
#endif
