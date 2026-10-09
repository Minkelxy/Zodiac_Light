#pragma once

#include <stdint.h>
#include "driver/rmt_encoder.h"

#ifdef __cplusplus
extern "C" {
#endif

// One statically owned composite encoder, with SDK-owned child encoders.
// Fixed 40 MHz resolution gives exact 800 kbit/s cells and a >=300 us reset.
esp_err_t clp_new_ws2812_encoder(uint32_t resolution_hz, uint32_t reset_us,
                               rmt_encoder_handle_t *ret_encoder);

#ifdef __cplusplus
}
#endif
