#ifndef CONSTELLATION_LAMP_OUTPUT_TRANSFORM_H
#define CONSTELLATION_LAMP_OUTPUT_TRANSFORM_H

#include <stddef.h>
#include <stdint.h>

namespace clp {

// Same linear channel-current model and floor rounding as the Python sender.
// Microamp coefficients allow calibration without floating-point processing.
// Output is GRB. RGB front/back buffers remain untouched by this transform.
inline bool rgbToGrbLimited(const uint8_t* rgb, uint8_t* grb, uint16_t count,
                            uint32_t currentLimitMa, uint32_t idleLedUa,
                            uint32_t channelUa) {
  uint64_t sum = 0;
  const size_t bytes = static_cast<size_t>(count) * 3;
  for (size_t i = 0; i < bytes; ++i) sum += rgb[i];
  const uint64_t idle = static_cast<uint64_t>(count) * idleLedUa;
  const uint64_t limit = static_cast<uint64_t>(currentLimitMa) * 1000;
  const uint64_t available = limit > idle ? (limit - idle) * 255 : 0;
  const uint64_t demand = sum * channelUa;
  const bool limited = demand > available;
  for (size_t led = 0; led < count; ++led) {
    for (size_t channel = 0; channel < 3; ++channel) {
      const size_t source = led * 3 + channel;
      const size_t output = led * 3 + (channel == 0 ? 1 : channel == 1 ? 0 : 2);
      grb[output] = limited ? static_cast<uint8_t>(rgb[source] * available / demand) : rgb[source];
    }
  }
  return limited;
}

}  // namespace clp
#endif
