/*
 * SPDX-FileCopyrightText: 2021-2022 Espressif Systems (Shanghai) CO LTD
 * SPDX-FileCopyrightText: 2026 Constellation lamp contributors
 * SPDX-License-Identifier: Apache-2.0
 *
 * Adapted from ESP-IDF examples/peripherals/rmt/led_strip/main/
 * led_strip_encoder.c. Changes: static composite ownership, exact 800 kbit/s
 * cell timing, and an explicit >=300 us low reset instead of the example 50 us.
 */

#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include "esp_check.h"
#include "ws2812_encoder.h"

typedef struct {
    rmt_encoder_t base;  // First member: a base pointer is also a struct pointer.
    rmt_encoder_handle_t bytes;
    rmt_encoder_handle_t copy;
    int phase;
    rmt_symbol_word_t reset;
} clp_ws2812_encoder_t;

static clp_ws2812_encoder_t instance;
static bool created;

static size_t encode(rmt_encoder_t *base, rmt_channel_handle_t channel,
                     const void *data, size_t size, rmt_encode_state_t *ret_state)
{
    clp_ws2812_encoder_t *self = (clp_ws2812_encoder_t *)base;
    rmt_encode_state_t state = RMT_ENCODING_RESET;
    rmt_encode_state_t child_state = RMT_ENCODING_RESET;
    size_t symbols = 0;
    switch (self->phase) {
    case 0:
        symbols += self->bytes->encode(self->bytes, channel, data, size, &child_state);
        if (child_state & RMT_ENCODING_COMPLETE) self->phase = 1;
        if (child_state & RMT_ENCODING_MEM_FULL) {
            state |= RMT_ENCODING_MEM_FULL;
            break;
        }
        /* fall through */
    case 1:
        symbols += self->copy->encode(self->copy, channel, &self->reset,
                                     sizeof(self->reset), &child_state);
        if (child_state & RMT_ENCODING_COMPLETE) {
            self->phase = 0;
            state |= RMT_ENCODING_COMPLETE;
        }
        if (child_state & RMT_ENCODING_MEM_FULL) state |= RMT_ENCODING_MEM_FULL;
        break;
    }
    *ret_state = state;
    return symbols;
}

static esp_err_t reset(rmt_encoder_t *base)
{
    clp_ws2812_encoder_t *self = (clp_ws2812_encoder_t *)base;
    ESP_RETURN_ON_ERROR(rmt_encoder_reset(self->bytes), "clp", "reset bytes");
    ESP_RETURN_ON_ERROR(rmt_encoder_reset(self->copy), "clp", "reset copy");
    self->phase = 0;
    return ESP_OK;
}

static esp_err_t destroy(rmt_encoder_t *base)
{
    clp_ws2812_encoder_t *self = (clp_ws2812_encoder_t *)base;
    rmt_del_encoder(self->bytes);
    rmt_del_encoder(self->copy);
    memset(self, 0, sizeof(*self));
    created = false;
    return ESP_OK;
}

esp_err_t clp_new_ws2812_encoder(uint32_t resolution_hz, uint32_t reset_us,
                               rmt_encoder_handle_t *ret_encoder)
{
    if (!ret_encoder || resolution_hz != 40000000 || reset_us < 300 || reset_us > 1000)
        return ESP_ERR_INVALID_ARG;
    if (created) return ESP_ERR_INVALID_STATE;
    *ret_encoder = NULL;
    memset(&instance, 0, sizeof(instance));
    instance.base.encode = encode;
    instance.base.reset = reset;
    instance.base.del = destroy;
    rmt_bytes_encoder_config_t config = {
        .bit0 = {.level0 = 1, .duration0 = 14, .level1 = 0, .duration1 = 36},
        .bit1 = {.level0 = 1, .duration0 = 36, .level1 = 0, .duration1 = 14},
        .flags.msb_first = 1,
    };
    esp_err_t err = rmt_new_bytes_encoder(&config, &instance.bytes);
    if (err != ESP_OK) return err;
    rmt_copy_encoder_config_t copy_config = {};
    err = rmt_new_copy_encoder(&copy_config, &instance.copy);
    if (err != ESP_OK) {
        rmt_del_encoder(instance.bytes);
        memset(&instance, 0, sizeof(instance));
        return err;
    }
    const uint32_t half_reset_ticks = 40 * reset_us / 2;
    instance.reset = (rmt_symbol_word_t){
        .level0 = 0, .duration0 = half_reset_ticks,
        .level1 = 0, .duration1 = half_reset_ticks,
    };
    created = true;
    *ret_encoder = &instance.base;
    return ESP_OK;
}
