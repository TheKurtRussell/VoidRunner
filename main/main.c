#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_ldo_regulator.h"
#include "esp_lcd_mipi_dsi.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_st7123.h"
#include "esp_lcd_touch_st7123.h"
#include "esp_lvgl_port.h"
#include "driver/i2c_master.h"
#include "driver/gpio.h"
#include "game_world.h"

void app_main(void) {
    esp_ldo_channel_handle_t ldo_mipi = NULL;
    esp_ldo_channel_config_t ldo_cfg = { .chan_id = 3, .voltage_mv = 2500 };
    esp_ldo_acquire_channel(&ldo_cfg, &ldo_mipi);

    esp_lcd_dsi_bus_handle_t dsi_bus = NULL;
    esp_lcd_dsi_bus_config_t bus_cfg = ST7123_PANEL_BUS_DSI_2CH_CONFIG();
    esp_lcd_new_dsi_bus(&bus_cfg, &dsi_bus);

    esp_lcd_panel_io_handle_t io_handle = NULL;
    esp_lcd_dbi_io_config_t dbi_cfg = ST7123_PANEL_IO_DBI_CONFIG();
    esp_lcd_new_panel_io_dbi(dsi_bus, &dbi_cfg, &io_handle);

    esp_lcd_panel_handle_t disp_panel = NULL;
    esp_lcd_dpi_panel_config_t dpi_cfg = ST7123_720_1280_PANEL_60HZ_DPI_CONFIG(LCD_COLOR_PIXEL_FORMAT_RGB565);
    st7123_vendor_config_t vendor_cfg = { .mipi_config = { .dsi_bus = dsi_bus, .dpi_config = &dpi_cfg } };
    esp_lcd_panel_dev_config_t lcd_cfg = {
        .reset_gpio_num = GPIO_NUM_27, .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB,
        .bits_per_pixel = 16, .vendor_config = &vendor_cfg,
    };
    esp_lcd_new_panel_st7123(io_handle, &lcd_cfg, &disp_panel);
    esp_lcd_panel_reset(disp_panel);
    esp_lcd_panel_init(disp_panel);
    esp_lcd_panel_disp_on_off(disp_panel, true);

    gpio_config_t bl_cfg = { .pin_bit_mask = (1ULL << 22), .mode = GPIO_MODE_OUTPUT };
    gpio_config(&bl_cfg);
    gpio_set_level(GPIO_NUM_22, 1);

    i2c_master_bus_handle_t i2c_bus = NULL;
    i2c_master_bus_config_t i2c_cfg = {
        .i2c_port = I2C_NUM_0, .sda_io_num = GPIO_NUM_31, .scl_io_num = GPIO_NUM_32,
        .clk_source = I2C_CLK_SRC_DEFAULT, .glitch_ignore_cnt = 7, .flags.enable_internal_pullup = true,
    };
    i2c_new_master_bus(&i2c_cfg, &i2c_bus);

    esp_lcd_panel_io_handle_t tp_io = NULL;
    esp_lcd_panel_io_i2c_config_t tp_io_cfg = ESP_LCD_TOUCH_IO_I2C_ST7123_CONFIG();
    tp_io_cfg.scl_speed_hz = 400000;
    esp_lcd_new_panel_io_i2c(i2c_bus, &tp_io_cfg, &tp_io);

    esp_lcd_touch_handle_t tp = NULL;
    esp_lcd_touch_config_t tp_cfg = { .x_max = 720, .y_max = 1280, .rst_gpio_num = GPIO_NUM_23, .int_gpio_num = GPIO_NUM_NC };
    esp_lcd_touch_new_i2c_st7123(tp_io, &tp_cfg, &tp);

    const lvgl_port_cfg_t lvgl_cfg = ESP_LVGL_PORT_INIT_CONFIG();
    lvgl_port_init(&lvgl_cfg);

    const lvgl_port_display_cfg_t disp_cfg = {
        .io_handle = io_handle, .panel_handle = disp_panel,
        .buffer_size = 1280 * 80, .double_buffer = true,
        .hres = 720, .vres = 1280, .monochrome = false,
        .color_format = LV_COLOR_FORMAT_RGB565,
        .rotation = { .swap_xy = true, .mirror_x = true, .mirror_y = false },
        .flags = { .buff_spiram = true, .sw_rotate = true },
    };
    lv_display_t *disp = lvgl_port_add_disp(&disp_cfg);

    const lvgl_port_touch_cfg_t touch_cfg = { .disp = disp, .handle = tp };
    lvgl_port_add_touch(&touch_cfg);

    lvgl_port_lock(0);
    vr_game_init(lv_scr_act());
    lvgl_port_unlock();
}
