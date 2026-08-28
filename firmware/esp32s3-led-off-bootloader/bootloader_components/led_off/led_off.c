#include <stdint.h>

#include "esp_cpu.h"
#include "esp_rom_sys.h"
#include "hal/gpio_ll.h"
#include "soc/gpio_struct.h"
#include "soc/io_mux_reg.h"

#define BOARD_RGB_LED_GPIO 48U
#define LED_ZERO_BITS 32U

// Required by ESP-IDF's custom-bootloader hook linker integration.
void bootloader_hooks_include(void)
{
}

static inline void wait_cycles(uint32_t cycles)
{
    const uint32_t started = esp_cpu_get_cycle_count();
    while ((uint32_t)(esp_cpu_get_cycle_count() - started) < cycles) {
    }
}

static void board_rgb_led_off(void)
{
    // A reset interval first prevents a partially received frame from being
    // combined with this one.
    gpio_ll_func_sel(&GPIO, BOARD_RGB_LED_GPIO, PIN_FUNC_GPIO);
    gpio_ll_set_level(&GPIO, BOARD_RGB_LED_GPIO, 0);
    gpio_ll_output_enable(&GPIO, BOARD_RGB_LED_GPIO);
    esp_rom_delay_us(100);

    const uint32_t ticks_per_us = esp_rom_get_cpu_ticks_per_us();
    const uint32_t high_cycles = (ticks_per_us * 35U + 99U) / 100U;
    const uint32_t low_cycles = (ticks_per_us * 90U + 99U) / 100U;

    // 32 zero bits switch off both 24-bit WS2812 RGB and 32-bit SK6812 RGBW.
    // With a single on-board pixel, any surplus bits are simply forwarded.
    for (uint32_t bit = 0; bit < LED_ZERO_BITS; ++bit) {
        gpio_ll_set_level(&GPIO, BOARD_RGB_LED_GPIO, 1);
        wait_cycles(high_cycles);
        gpio_ll_set_level(&GPIO, BOARD_RGB_LED_GPIO, 0);
        wait_cycles(low_cycles);
    }

    // Latch the all-black frame and leave the line low.
    esp_rom_delay_us(100);
}

void bootloader_after_init(void)
{
    board_rgb_led_off();
}
