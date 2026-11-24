#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "esp_ldo_regulator.h"
#include "esp_lcd_mipi_dsi.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_st7123.h"
#include "esp_lcd_touch_st7123.h"
#include "driver/i2c_master.h"
#include "driver/gpio.h"
#include "lvgl.h"
#include "game_world.h"

static esp_lcd_panel_handle_t disp_panel = NULL;
static esp_lcd_touch_handle_t tp = NULL;

static void lvgl_tick_cb(void *arg) { lv_tick_inc(5); }

static void disp_flush_cb(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map) {
    esp_lcd_panel_draw_bitmap(disp_panel, area->x1, area->y1, area->x2 + 1, area->y2 + 1, px_map);
    lv_display_flush_ready(disp);
}

static void touch_read_cb(lv_indev_t *indev, lv_indev_data_t *data) {
    esp_lcd_touch_read_data(tp);
    uint16_t tx, ty; uint8_t cnt = 0;
    if (esp_lcd_touch_get_coordinates(tp, &tx, &ty, NULL, &cnt, 1) && cnt > 0) {
        data->point.x = tx;
        data->point.y = ty;
        data->state = LV_INDEV_STATE_PRESSED;
    } else {
        data->state = LV_INDEV_STATE_RELEASED;
    }
}

static void lvgl_task(void *arg) {
    while (1) {
        uint32_t delay = lv_timer_handler();
        vTaskDelay(pdMS_TO_TICKS(delay > 10 ? 10 : (delay < 1 ? 1 : delay)));
    }
}

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

    esp_lcd_touch_config_t tp_cfg = { .x_max = 720, .y_max = 1280, .rst_gpio_num = GPIO_NUM_23, .int_gpio_num = GPIO_NUM_NC };
    esp_lcd_touch_new_i2c_st7123(tp_io, &tp_cfg, &tp);

    lv_init();
    const esp_timer_create_args_t tick_args = { .callback = &lvgl_tick_cb, .name = "lv_tick" };
    esp_timer_handle_t tick_timer = NULL;
    esp_timer_create(&tick_args, &tick_timer);
    esp_timer_start_periodic(tick_timer, 5000);

    lv_display_t *disp = lv_display_create(720, 1280);
    size_t buf_sz = 720 * 160 * sizeof(uint16_t);
    void *buf1 = heap_caps_malloc(buf_sz, MALLOC_CAP_SPIRAM);
    void *buf2 = heap_caps_malloc(buf_sz, MALLOC_CAP_SPIRAM);
    lv_display_set_buffers(disp, buf1, buf2, buf_sz, LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(disp, disp_flush_cb);
    lv_display_set_rotation(disp, LV_DISPLAY_ROTATION_90);

    lv_indev_t *indev = lv_indev_create();
    lv_indev_set_type(indev, LV_INDEV_TYPE_POINTER);
    lv_indev_set_read_cb(indev, touch_read_cb);

    vr_game_init(lv_scr_act());
    xTaskCreatePinnedToCore(lvgl_task, "lvgl", 8192, NULL, 5, NULL, 1);
}
