#include "native_effects.h"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <limits>

namespace clp {
namespace {
constexpr size_t N = CONSTELLATION_COMPACT_STAR_COUNT;
constexpr size_t E = CONSTELLATION_COMPACT_EDGE_COUNT;
constexpr size_t L = CONSTELLATION_COMPACT_LED_COUNT;
constexpr double pi = 3.1415926535897932384626433832795;
constexpr double tau = 2 * pi;
constexpr double infinity = std::numeric_limits<double>::infinity();

uint32_t mix32(uint32_t value) {
  value ^= value >> 16;
  value *= 0x7feb352du;
  value ^= value >> 15;
  value *= 0x846ca68bu;
  return value ^ (value >> 16);
}
double unit(uint32_t value) { return value / 4294967296.0; }
double x(size_t led) { return constellation_compact_led_x_dm[led] / 10.0; }
double y(size_t led) { return constellation_compact_led_y_dm[led] / 10.0; }
double edgeLength(size_t edge) { return constellation_compact_edge_length_dm[edge] / 10.0; }
double u(size_t led) { return constellation_compact_led_u16[led] / 65535.0; }
double clip(double value) { return std::max(0.0, std::min(1.0, value)); }
double mod(double value, double period) {
  const double result = std::fmod(value, period);
  return result < 0 ? result + period : result;
}
double gaussian(double value) { return std::exp(-0.5 * value * value); }
bool visible(size_t led) { return constellation_compact_led_owner_type[led] != CONSTELLATION_COMPACT_LED_HIDDEN; }
bool star(size_t led) { return constellation_compact_led_owner_type[led] == CONSTELLATION_COMPACT_LED_STAR; }

bool validParams(const NativeParams& p) {
  const double positive[] = {p.speed, p.gamma, p.pitch_mm, p.flow_velocity_mm_s, p.flow_width_mm,
    p.wavelength_mm, p.ripple_velocity_mm_s, p.breath_period_s, p.aurora_wavelength_mm,
    p.aurora_velocity_mm_s, p.sparkle_period_s, p.sparkle_duration_s, p.graph_velocity_mm_s,
    p.graph_width_mm, p.draw_velocity_mm_s, p.draw_fade_s, p.draw_head_width_mm,
    p.meteor_velocity_mm_s, p.meteor_tail_mm, p.meteor_width_mm};
  for (double value : positive) if (!std::isfinite(value) || value <= 0) return false;
  const double bounded[] = {p.brightness, p.breath_floor, p.aurora_contrast, p.sparkle_density};
  for (double value : bounded) if (!std::isfinite(value) || value < 0 || value > 1) return false;
  return static_cast<unsigned>(p.effect) <= static_cast<unsigned>(Effect::Meteor) &&
    p.source_star >= -1 && p.source_star < static_cast<int>(N) &&
    p.route_count <= kNativeRouteCapacity && p.route_count != 1 &&
    std::isfinite(p.draw_hold_s) && p.draw_hold_s >= 0 &&
    std::isfinite(p.graph_period_s) && p.graph_period_s >= 0 &&
    std::isfinite(p.flow_period_s) && p.flow_period_s >= 0 &&
    std::isfinite(p.draw_period_s) && p.draw_period_s >= 0 &&
    std::isfinite(p.meteor_interval_s) && p.meteor_interval_s >= 0 &&
    std::isfinite(p.meteor_angle_deg) && std::abs(p.meteor_angle_deg) <= 1e9 &&
    (!p.custom_center || (std::isfinite(p.center_x_mm) && std::isfinite(p.center_y_mm) &&
      p.center_x_mm >= -1e9 && p.center_y_mm >= -1e9)) &&
    p.sparkle_duration_s < p.sparkle_period_s;
}

bool sceneValid() {
  if (N == 0 || E == 0 || L == 0) return false;
  for (size_t led = 0; led < L; ++led) {
    const uint8_t owner = constellation_compact_led_owner_type[led];
    const uint16_t index = constellation_compact_led_owner_index[led];
    if (owner > CONSTELLATION_COMPACT_LED_EDGE ||
        (owner == CONSTELLATION_COMPACT_LED_STAR && index >= N) ||
        (owner == CONSTELLATION_COMPACT_LED_EDGE && index >= E)) return false;
  }
  for (size_t edge = 0; edge < E; ++edge)
    if (constellation_compact_edge_start_star[edge] >= N ||
        constellation_compact_edge_end_star[edge] >= N || edgeLength(edge) <= 0) return false;
  return true;
}

// Python orders star IDs lexicographically. Numeric HIP ordering alone would
// disagree when digit counts differ, so compare their exact "hip_<n>" IDs.
bool starLess(uint16_t a, uint16_t b) {
  char left[20], right[20];
  std::snprintf(left, sizeof(left), "hip_%lu", static_cast<unsigned long>(constellation_compact_star_hip[a]));
  std::snprintf(right, sizeof(right), "hip_%lu", static_cast<unsigned long>(constellation_compact_star_hip[b]));
  return std::strcmp(left, right) < 0;
}

bool pathLess(const uint16_t* a, size_t aSize, const uint16_t* b, size_t bSize) {
  for (size_t i = 0; i < std::min(aSize, bSize); ++i)
    if (a[i] != b[i]) return starLess(a[i], b[i]);
  return aSize < bSize;
}

void sortedStars(uint16_t order[N]) {
  for (size_t i = 0; i < N; ++i) order[i] = static_cast<uint16_t>(i);
  for (size_t i = 1; i < N; ++i) {
    const uint16_t value = order[i];
    size_t j = i;
    while (j && starLess(value, order[j - 1])) { order[j] = order[j - 1]; --j; }
    order[j] = value;
  }
}

void shortestPaths(uint16_t source, double distance[N], uint16_t paths[N][N], uint16_t sizes[N]) {
  bool done[N] = {};
  for (size_t i = 0; i < N; ++i) { distance[i] = infinity; sizes[i] = 0; }
  distance[source] = 0;
  paths[source][0] = source;
  sizes[source] = 1;
  for (size_t step = 0; step < N; ++step) {
    size_t node = N;
    for (size_t i = 0; i < N; ++i) {
      if (done[i] || !std::isfinite(distance[i])) continue;
      if (node == N || distance[i] < distance[node] ||
          (distance[i] == distance[node] && pathLess(paths[i], sizes[i], paths[node], sizes[node]))) node = i;
    }
    if (node == N) break;
    done[node] = true;
    for (size_t edge = 0; edge < E; ++edge) {
      const uint16_t a = constellation_compact_edge_start_star[edge], b = constellation_compact_edge_end_star[edge];
      if (a != node && b != node) continue;
      const uint16_t neighbor = a == node ? b : a;
      const double candidate = distance[node] + edgeLength(edge);
      uint16_t path[N];
      if (sizes[node] >= N) continue;
      std::memcpy(path, paths[node], sizes[node] * sizeof(uint16_t));
      path[sizes[node]] = neighbor;
      const size_t size = sizes[node] + 1;
      if (candidate < distance[neighbor] - 1e-9 ||
          (std::abs(candidate - distance[neighbor]) <= 1e-9 &&
           (sizes[neighbor] == 0 || pathLess(path, size, paths[neighbor], sizes[neighbor])))) {
        distance[neighbor] = candidate;
        sizes[neighbor] = static_cast<uint16_t>(size);
        std::memcpy(paths[neighbor], path, size * sizeof(uint16_t));
      }
    }
  }
}

void drawingVisit(uint16_t node, bool visited[E], uint16_t order[E], bool reverse[E], size_t& size) {
  // Explicit DFS stack avoids recursion on small FreeRTOS task stacks. Each
  // push marks a previously unused edge, so depth is bounded by E+1.
  uint16_t stack[E + 1];
  size_t depth = 1;
  stack[0] = node;
  while (depth) {
    const uint16_t current = stack[depth - 1];
    size_t chosen = E; uint16_t next = 0; bool direction = false;
    for (size_t edge = 0; edge < E; ++edge) {
      if (visited[edge]) continue;
      const uint16_t a = constellation_compact_edge_start_star[edge], b = constellation_compact_edge_end_star[edge];
      if (a != current && b != current) continue;
      const uint16_t candidate = a == current ? b : a;
      if (chosen == E || starLess(candidate, next) || (candidate == next && edge < chosen)) {
        chosen = edge; next = candidate; direction = b == current;
      }
    }
    if (chosen == E) { --depth; continue; }
    visited[chosen] = true;
    order[size] = static_cast<uint16_t>(chosen); reverse[size] = direction; ++size;
    stack[depth++] = next;
  }
}

void color(double work[3], double r, double g, double b, double level = 1) {
  work[0] = r * level; work[1] = g * level; work[2] = b * level;
}
void maximum(double work[3], double r, double g, double b, double level = 1) {
  work[0] = std::max(work[0], r * level);
  work[1] = std::max(work[1], g * level);
  work[2] = std::max(work[2], b * level);
}
uint8_t roundEven(double value) {
  const double low = std::floor(value), fraction = value - low;
  return static_cast<uint8_t>(low + (fraction > 0.5 || (fraction == 0.5 && std::fmod(low, 2.0) != 0) ? 1 : 0));
}
}  // namespace

const char* effectName(Effect effect) {
  static const char* names[] = {"twinkle", "flow", "ripple", "breath", "aurora", "sparkle", "graph_wave", "draw", "meteor"};
  const unsigned i = static_cast<unsigned>(effect);
  return i < 9 ? names[i] : "unknown";
}
const char* renderErrorName(RenderError error) {
  static const char* names[] = {"ok", "invalid_params", "invalid_scene", "invalid_route", "not_initialized",
                              "requires_init", "output_too_small", "time_overflow"};
  const unsigned i = static_cast<unsigned>(error);
  return i < 8 ? names[i] : "unknown";
}

RenderError initNativeEffects(RenderContext& c, const NativeParams& p) {
  c.initialized = false;
  if (!validParams(p)) return RenderError::InvalidParams;
  if (!sceneValid()) return RenderError::InvalidScene;
  c.seed = p.seed; c.source_config = p.source_star;
  c.route_config_count = p.route_count;
  std::memcpy(c.route_config, p.route, sizeof(c.route_config));
  c.seed_phase = unit(mix32(p.seed));
  c.center_x = 0; c.center_y = 0;
  c.source = p.source_star < 0 ? 0 : static_cast<uint16_t>(p.source_star);
  for (size_t i = 0; i < N; ++i) {
    const uint32_t mixed = mix32(p.seed ^ constellation_compact_star_hip[i]);
    c.phase[i] = unit(mixed) * tau;
    c.rate[i] = 0.45 + unit(mix32(mixed)) * 0.5;
    const double mag = constellation_compact_star_mag_centi[i] == CONSTELLATION_COMPACT_MAG_MISSING ?
        3.5 : constellation_compact_star_mag_centi[i] / 100.0;
    c.magnitude[i] = std::max(0.55, std::min(1.0, 1 - 0.07 * (mag - 2)));
    c.center_x += constellation_compact_star_x_dm[i] / 10.0 / N;
    c.center_y += constellation_compact_star_y_dm[i] / 10.0 / N;
    if (p.source_star < 0) {
      const int16_t candidate = constellation_compact_star_mag_centi[i];
      const int16_t old = constellation_compact_star_mag_centi[c.source];
      if (candidate != CONSTELLATION_COMPACT_MAG_MISSING &&
          (old == CONSTELLATION_COMPACT_MAG_MISSING || candidate < old ||
           (candidate == old && constellation_compact_star_hip[i] < constellation_compact_star_hip[c.source]))) c.source = i;
    }
  }

  double distance[N]; uint16_t paths[N][N], sizes[N];
  shortestPaths(c.source, distance, paths, sizes);
  c.graph_max = 0;
  for (size_t led = 0; led < L; ++led) {
    c.graph_distance[led] = infinity;
    const size_t owner = constellation_compact_led_owner_index[led];
    if (star(led)) c.graph_distance[led] = distance[owner];
    else if (visible(led)) {
      c.graph_distance[led] = std::min(distance[constellation_compact_edge_start_star[owner]] + u(led) * edgeLength(owner),
          distance[constellation_compact_edge_end_star[owner]] + (1 - u(led)) * edgeLength(owner));
    }
    if (std::isfinite(c.graph_distance[led])) c.graph_max = std::max(c.graph_max, c.graph_distance[led]);
  }

  bool visited[E] = {}; size_t drawn = 0; uint16_t starOrder[N];
  sortedStars(starOrder);
  drawingVisit(c.source, visited, c.draw_edges, c.draw_reverse, drawn);
  for (size_t i = 0; i < N; ++i) drawingVisit(starOrder[i], visited, c.draw_edges, c.draw_reverse, drawn);
  double arrivals[N]; double offsets[E]; bool reversals[E];
  for (double& arrival : arrivals) arrival = infinity;
  arrivals[c.source] = 0; c.draw_length = 0;
  for (size_t i = 0; i < drawn; ++i) {
    const size_t edge = c.draw_edges[i];
    const uint16_t a = constellation_compact_edge_start_star[edge], b = constellation_compact_edge_end_star[edge];
    const uint16_t start = c.draw_reverse[i] ? b : a, end = c.draw_reverse[i] ? a : b;
    arrivals[start] = std::min(arrivals[start], c.draw_length);
    arrivals[end] = std::min(arrivals[end], c.draw_length + edgeLength(edge));
    offsets[edge] = c.draw_length; reversals[edge] = c.draw_reverse[i];
    c.draw_length += edgeLength(edge);
  }
  for (size_t led = 0; led < L; ++led) {
    const size_t owner = constellation_compact_led_owner_index[led];
    c.draw_distance[led] = infinity;
    if (star(led)) c.draw_distance[led] = std::isfinite(arrivals[owner]) ? arrivals[owner] : c.draw_length;
    else if (visible(led)) c.draw_distance[led] = offsets[owner] + (reversals[owner] ? 1 - u(led) : u(led)) * edgeLength(owner);
  }

  c.route_size = p.route_count;
  if (p.route_count) {
    for (size_t i = 0; i < p.route_count; ++i) {
      if (p.route[i] >= N) return RenderError::InvalidRoute;
      c.route_stars[i] = p.route[i];
    }
  } else {
    double longest = -1;
    for (size_t i = 0; i < N; ++i) {
      shortestPaths(starOrder[i], distance, paths, sizes);
      for (size_t j = 0; j < N; ++j) {
        const size_t end = starOrder[j];
        if (end != starOrder[i] && std::isfinite(distance[end]) && distance[end] > longest + 1e-9) {
          longest = distance[end]; c.route_size = sizes[end];
          std::memcpy(c.route_stars, paths[end], sizes[end] * sizeof(uint16_t));
        }
      }
    }
  }
  if (c.route_size < 2) return RenderError::InvalidRoute;
  c.route_length = 0; c.route_offset[0] = 0;
  for (size_t i = 0; i + 1 < c.route_size; ++i) {
    size_t chosen = E; bool reverse = false;
    for (size_t edge = 0; edge < E; ++edge) {
      const uint16_t a = constellation_compact_edge_start_star[edge], b = constellation_compact_edge_end_star[edge];
      if (a == c.route_stars[i] && b == c.route_stars[i + 1]) { chosen = edge; reverse = false; }
      if (b == c.route_stars[i] && a == c.route_stars[i + 1]) { chosen = edge; reverse = true; }
    }
    if (chosen == E) return RenderError::InvalidRoute;
    c.route_edges[i] = static_cast<uint16_t>(chosen); c.route_reverse[i] = reverse;
    c.route_length += edgeLength(chosen); c.route_offset[i + 1] = c.route_length;
  }
  c.initialized = true;
  return RenderError::Ok;
}

RenderError renderNativeEffects(RenderContext& c, uint64_t time_ms, const NativeParams& p,
                                uint8_t* rgb, size_t capacity) {
  if (!validParams(p)) return RenderError::InvalidParams;
  if (!c.initialized) return RenderError::NotInitialized;
  if (c.seed != p.seed || c.source_config != p.source_star || c.route_config_count != p.route_count ||
      (p.route_count && std::memcmp(c.route_config, p.route, p.route_count * sizeof(uint16_t)) != 0)) return RenderError::RequiresInit;
  if (!rgb || capacity < L * 3) return RenderError::OutputTooSmall;
  const double seconds = static_cast<double>(time_ms) / 1000.0 * p.speed;
  if (!std::isfinite(seconds)) return RenderError::TimeOverflow;
  std::memset(c.work, 0, sizeof(c.work));

  double sparkleStrength[N] = {}, sparkleColors[N][3] = {};
  double alongMin = infinity, alongMax = -infinity, acrossMin = infinity, acrossMax = -infinity;
  double meteorCos = 0, meteorSin = 0, meteorTravel = 0, meteorLocal = 0, meteorHead = 0, meteorTrack = 0, meteorEnvelope = 0;
  if (p.effect == Effect::Sparkle) {
    const double event = std::floor(seconds / p.sparkle_period_s);
    if (!std::isfinite(event)) return RenderError::TimeOverflow;
    const uint32_t eventLow = static_cast<uint32_t>(mod(event, 4294967296.0));
    const double local = mod(seconds, p.sparkle_period_s);
    for (size_t i = 0; i < N; ++i) {
      const uint32_t hashed = mix32(p.seed ^ constellation_compact_star_hip[i] ^ (eventLow * 0x9e3779b9u));
      const double start = unit(mix32(hashed)) * (p.sparkle_period_s - p.sparkle_duration_s);
      const double phase = (local - start) / p.sparkle_duration_s;
      if (unit(hashed) < p.sparkle_density && phase > 0 && phase < 1) sparkleStrength[i] = std::pow(std::sin(pi * phase), 4);
      const double warmth = unit(mix32(hashed ^ 0xa511e9b3u));
      color(sparkleColors[i], 0.70 + 0.30 * warmth, 0.88 + 0.12 * warmth, 1 - 0.12 * warmth);
    }
  }
  if (p.effect == Effect::Meteor) {
    meteorCos = std::cos(p.meteor_angle_deg * pi / 180); meteorSin = std::sin(p.meteor_angle_deg * pi / 180);
    for (size_t led = 0; led < L; ++led) if (visible(led)) {
      const double along = x(led) * meteorCos + y(led) * meteorSin, across = -x(led) * meteorSin + y(led) * meteorCos;
      alongMin = std::min(alongMin, along); alongMax = std::max(alongMax, along);
      acrossMin = std::min(acrossMin, across); acrossMax = std::max(acrossMax, across);
    }
    const double start = alongMin - 20;
    meteorTravel = (alongMax - start + p.meteor_tail_mm * 3) / p.meteor_velocity_mm_s;
    const double interval = p.meteor_interval_s > 0 ? p.meteor_interval_s : meteorTravel + 0.8;
    if (!std::isfinite(meteorTravel) || !std::isfinite(interval)) return RenderError::TimeOverflow;
    if (interval < meteorTravel) return RenderError::InvalidParams;
    const double event = std::floor(seconds / interval);
    if (!std::isfinite(event)) return RenderError::TimeOverflow;
    const uint32_t eventLow = static_cast<uint32_t>(mod(event, 4294967296.0));
    const uint32_t hashed = mix32(p.seed ^ (eventLow * 0x9e3779b9u) ^ 0xb5297a4du);
    meteorLocal = mod(seconds, interval);
    meteorTrack = acrossMin + (0.25 + 0.5 * unit(hashed)) * (acrossMax - acrossMin);
    meteorHead = start + meteorLocal * p.meteor_velocity_mm_s;
    if (!std::isfinite(meteorHead)) return RenderError::TimeOverflow;
    meteorEnvelope = std::max(0.0, std::min(1.0, std::min(meteorLocal / 0.15, (meteorTravel - meteorLocal) / 0.6)));
  }

  for (size_t led = 0; led < L; ++led) {
    if (!visible(led)) continue;
    const size_t owner = constellation_compact_led_owner_index[led];
    const bool isStar = star(led);
    double* work = c.work[led];
    switch (p.effect) {
    case Effect::Twinkle:
      if (isStar) color(work, 1, 0.90, 0.78, (0.79 + 0.13 * std::sin(seconds * c.rate[owner] + c.phase[owner]) +
          0.06 * std::sin(seconds * c.rate[owner] * 1.7 + c.phase[owner] * 0.71)) * c.magnitude[owner]);
      else color(work, 0.38, 0.63, 1, 0.38 + 0.035 * std::sin(seconds * 0.6));
      break;
    case Effect::Flow: {
      const double length = p.flow_period_s > 0 ? p.flow_period_s * p.flow_velocity_mm_s : c.route_length;
      if (!std::isfinite(length)) return RenderError::TimeOverflow;
      const double head = mod(seconds * p.flow_velocity_mm_s, length);
      if (!std::isfinite(head)) return RenderError::TimeOverflow;
      if (isStar) color(work, 0.26, 0.20, 0.13); else color(work, 0.08, 0.12, 0.22);
      for (size_t i = 0; i < c.route_size; ++i) {
        double position = infinity;
        if (isStar && c.route_stars[i] == owner) position = c.route_offset[i];
        else if (!isStar && i + 1 < c.route_size && c.route_edges[i] == owner)
          position = c.route_offset[i] + (c.route_reverse[i] ? 1 - u(led) : u(led)) * edgeLength(owner);
        if (std::isfinite(position)) {
          const double delta = mod(head - position + length / 2, length) - length / 2;
          const double strength = gaussian(delta / p.flow_width_mm);
          if (isStar) maximum(work, 1, 0.79, 0.43, strength); else maximum(work, 0.26, 0.81, 1, strength);
        }
      }
      break;
    }
    case Effect::Ripple: {
      const double radius = std::hypot(x(led) - (p.custom_center ? p.center_x_mm : c.center_x),
                                       y(led) - (p.custom_center ? p.center_y_mm : c.center_y));
      const double phase = tau * (radius - seconds * p.ripple_velocity_mm_s) / p.wavelength_mm;
      const double wave = 0.5 + 0.5 * std::cos(phase), level = 0.15 + 0.85 * wave * wave;
      color(work, 0.35 + 0.25 * std::cos(phase + 0.5), 0.52 + 0.28 * std::cos(phase - 1.5), 1, level);
      if (isStar) maximum(work, 0.32, 0.28, 0.22);
      break;
    }
    case Effect::Breath: {
      const double rise = 0.5 - 0.5 * std::cos(tau * mod(seconds, p.breath_period_s) / p.breath_period_s);
      const double level = p.breath_floor + (1 - p.breath_floor) * rise;
      if (isStar) color(work, 1, 0.86, 0.60, (0.22 + 0.78 * level) * c.magnitude[owner]);
      else color(work, 1, 0.43, 0.12, 0.12 + 0.62 * level);
      break;
    }
    case Effect::Aurora: {
      const double drift = seconds * p.aurora_velocity_mm_s / p.aurora_wavelength_mm;
      const double curtain = x(led) / p.aurora_wavelength_mm + 0.23 * std::sin(tau * y(led) / p.aurora_wavelength_mm + drift * 2);
      const double scaled = mod(curtain - drift + c.seed_phase, 1) * 4;
      if (!std::isfinite(scaled)) return RenderError::TimeOverflow;
      const size_t index = static_cast<size_t>(std::floor(scaled)); const double fraction = scaled - index;
      static const double palette[5][3] = {{0.08,0.95,0.40},{0.08,0.75,1},{0.68,0.15,1},{0.14,0.28,1},{0.08,0.95,0.40}};
      const double wave = 0.5 + 0.5 * std::sin(tau * (y(led) / p.aurora_wavelength_mm * 0.7 + curtain * 0.3) + drift * 3.2);
      const double level = 0.85 * ((1 - p.aurora_contrast) + p.aurora_contrast * (0.2 + 0.8 * wave));
      for (size_t channel = 0; channel < 3; ++channel)
        work[channel] = (palette[index][channel] * (1 - fraction) + palette[index + 1][channel] * fraction) * level;
      if (isStar) { work[0] += 0.23; work[1] += 0.20; work[2] += 0.24; }
      break;
    }
    case Effect::Sparkle:
      if (isStar) {
        color(work, 0.30, 0.38, 0.49);
        maximum(work, sparkleColors[owner][0], sparkleColors[owner][1], sparkleColors[owner][2], sparkleStrength[owner]);
      } else color(work, 0.15, 0.25, 0.43);
      break;
    case Effect::GraphWave: {
      if (isStar) color(work, 0.28, 0.25, 0.20); else color(work, 0.10, 0.18, 0.30);
      if (std::isfinite(c.graph_distance[led])) {
        const double period = p.graph_period_s > 0 ? p.graph_period_s :
            c.graph_max / p.graph_velocity_mm_s + 4 * p.graph_width_mm / p.graph_velocity_mm_s + 1;
        if (!std::isfinite(period)) return RenderError::TimeOverflow;
        const double delta = mod(mod(seconds, period) - c.graph_distance[led] / p.graph_velocity_mm_s + period / 2, period) - period / 2;
        if (!std::isfinite(delta)) return RenderError::TimeOverflow;
        const double strength = gaussian(delta / (p.graph_width_mm / p.graph_velocity_mm_s));
        const double far = c.graph_distance[led] / std::max(c.graph_max, 1.0);
        maximum(work, 0.10 + 0.65 * far, 0.92 - 0.60 * far, 1, strength);
        if (isStar) maximum(work, 1, 0.89, 0.68, strength);
      }
      break;
    }
    case Effect::Draw: {
      const double travel = c.draw_length / p.draw_velocity_mm_s;
      if (!std::isfinite(travel + p.draw_hold_s + p.draw_fade_s)) return RenderError::TimeOverflow;
      const double period = p.draw_period_s > 0 ? p.draw_period_s : travel + p.draw_hold_s + p.draw_fade_s;
      if (period <= travel + p.draw_hold_s) return RenderError::InvalidParams;
      const double local = mod(seconds, period);
      const double head = std::min(local * p.draw_velocity_mm_s, c.draw_length + p.draw_head_width_mm);
      const double opacity = local > travel + p.draw_hold_s ?
          0.5 + 0.5 * std::cos(pi * (local - travel - p.draw_hold_s) / p.draw_fade_s) : 1;
      const double painted = clip((head - c.draw_distance[led]) / p.pitch_mm + 0.5) * opacity;
      const double pulse = gaussian((head - c.draw_distance[led]) / p.draw_head_width_mm) * opacity;
      if (isStar) color(work, 0.18, 0.19, 0.23); else color(work, 0.08, 0.12, 0.19);
      maximum(work, 0.12, 0.65, 0.94, painted); maximum(work, 0.80, 0.94, 1, pulse);
      if (isStar) maximum(work, 1, 0.86, 0.58, painted);
      break;
    }
    case Effect::Meteor: {
      if (isStar) color(work, 0.28, 0.25, 0.40); else color(work, 0.13, 0.15, 0.28);
      const double along = x(led) * meteorCos + y(led) * meteorSin, across = -x(led) * meteorSin + y(led) * meteorCos;
      const double delta = meteorHead - along;
      const double longitudinal = std::exp(-std::max(delta, 0.0) / p.meteor_tail_mm) * gaussian(std::min(delta, 0.0) / 11);
      const double intensity = longitudinal * gaussian((across - meteorTrack) / p.meteor_width_mm) * meteorEnvelope;
      const double warmth = std::exp(-std::max(delta, 0.0) / 28);
      maximum(work, 0.13 + 0.87 * warmth, 0.35 + 0.56 * warmth, 1, intensity);
      break;
    }
    }
    for (size_t channel = 0; channel < 3; ++channel)
      if (!std::isfinite(work[channel])) return RenderError::TimeOverflow;
  }
  for (size_t led = 0; led < L; ++led)
    for (size_t channel = 0; channel < 3; ++channel)
      rgb[led * 3 + channel] = roundEven(std::pow(clip(c.work[led][channel]), p.gamma) * (255 * p.brightness));
  return RenderError::Ok;
}
}  // namespace clp
