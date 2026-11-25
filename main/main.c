#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "esp_ldo_regulator.h"
#include "esp_lcd_mipi_dsi.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_st7123.h"
#include "esp_lcd_touch.h"
#include "esp_lcd_touch_st7123.h"
#include "driver/i2c_master.h"
#include "driver/gpio.h"
#include "lvgl.h"
#include "game_world.h"

static esp_lcd_panel_handle_t disp_panel = NULL;
static esp_lcd_touch_handle_t tp = NULL;
static lv_display_t *lv_disp = NULL;
static bool touch_ready = false;

static void lvgl_tick_cb(void *arg) { lv_tick_inc(5); }

static bool on_dpi_trans_done(esp_lcd_panel_handle_t panel, esp_lcd_dpi_panel_event_data_t *edata, void *user_ctx) {
    if (lv_disp) lv_display_flush_ready(lv_disp);
    return false;
}

static void disp_flush_cb(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map) {
    esp_lcd_panel_draw_bitmap(disp_panel, area->x1, area->y1, area->x2 + 1, area->y2 + 1, px_map);
}

static void touch_read_cb(lv_indev_t *indev, lv_indev_data_t *data) {
    if (!touch_ready || !tp) { data->state = LV_INDEV_STATE_RELEASED; return; }
    if (esp_lcd_touch_read_data(tp) == ESP_OK) {
        esp_lcd_touch_point_data_t pt;
        uint8_t cnt = 0;
        if (esp_lcd_touch_get_data(tp, &pt, &cnt, 1) == ESP_OK && cnt > 0) {
            data->point.x = pt.x;
            data->point.y = pt.y;
            data->state = LV_INDEV_STATE_PRESSED;
            return;
        }
    }
    data->state = LV_INDEV_STATE_RELEASED;
}

static void lvgl_task(void *arg) {
    while (1) {
        uint32_t delay = lv_timer_handler();
        vTaskDelay(pdMS_TO_TICKS(delay > 10 ? 10 : (delay < 1 ? 1 : delay)));
    }
}

static void io_expander_init(i2c_master_bus_handle_t bus) {
    i2c_master_dev_handle_t dev = NULL;
    i2c_device_config_t dcfg = { .dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = 0x43, .scl_speed_hz = 100000 };
    if (i2c_master_bus_add_device(bus, &dcfg, &dev) == ESP_OK) {
        // Only enable LCD_RST (P4) and TP_RST (P5) on expander 0x43; never touch 0x44 power/supervisor pins
        uint8_t b0=0x03, b1=0x30; uint8_t pkt[2]; pkt[0]=b0; pkt[1]=b1; i2c_master_transmit(dev, pkt, 2, 50); pkt[0]=0x05; pkt[1]=0x30; i2c_master_transmit(dev, pkt, 2, 50); pkt[0]=0x07; pkt[1]=0xCF; i2c_master_transmit(dev, pkt, 2, 50);
        i2c_master_bus_rm_device(dev);
    }
    vTaskDelay(pdMS_TO_TICKS(50));
}

void app_main(void) {
    i2c_master_bus_handle_t i2c_bus = NULL;
    i2c_master_bus_config_t i2c_cfg = {
        .i2c_port = I2C_NUM_0, .sda_io_num = GPIO_NUM_31, .scl_io_num = GPIO_NUM_32,
        .clk_source = I2C_CLK_SRC_DEFAULT, .glitch_ignore_cnt = 7, .flags.enable_internal_pullup = true,
    };
    if (i2c_new_master_bus(&i2c_cfg, &i2c_bus) == ESP_OK) {
        io_expander_init(i2c_bus);
    }

    esp_ldo_channel_handle_t ldo_mipi = NULL;
    esp_ldo_channel_config_t ldo_cfg = { .chan_id = 3, .voltage_mv = 2500 };
    esp_ldo_acquire_channel(&ldo_cfg, &ldo_mipi);

    esp_lcd_dsi_bus_handle_t dsi_bus = NULL;
    esp_lcd_dsi_bus_config_t bus_cfg = ST7123_PANEL_BUS_DSI_2CH_CONFIG();
    esp_lcd_new_dsi_bus(&bus_cfg, &dsi_bus);

    esp_lcd_panel_io_handle_t io_handle = NULL;
    esp_lcd_dbi_io_config_t dbi_cfg = ST7123_PANEL_IO_DBI_CONFIG();
    esp_lcd_new_panel_io_dbi(dsi_bus, &dbi_cfg, &io_handle);

    esp_lcd_dpi_panel_config_t dpi_cfg = {
        .virtual_channel = 0, .dpi_clk_src = MIPI_DSI_DPI_CLK_SRC_DEFAULT,
        .dpi_clock_freq_mhz = 34, .pixel_format = LCD_COLOR_PIXEL_FORMAT_RGB565, .num_fbs = 1,
        .video_timing = { .h_size = 720, .v_size = 1280, .hsync_pulse_width = 40, .hsync_back_porch = 140, .hsync_front_porch = 40, .vsync_pulse_width = 4, .vsync_back_porch = 20, .vsync_front_porch = 20 },
        .flags.use_dma2d = true,
    };
    st7123_vendor_config_t vendor_cfg = { .mipi_config = { .dsi_bus = dsi_bus, .dpi_config = &dpi_cfg } };
    esp_lcd_panel_dev_config_t lcd_cfg = { .reset_gpio_num = GPIO_NUM_27, .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB, .bits_per_pixel = 16, .vendor_config = &vendor_cfg };
    esp_lcd_new_panel_st7123(io_handle, &lcd_cfg, &disp_panel);
    esp_lcd_panel_reset(disp_panel);
    esp_lcd_panel_init(disp_panel);
    esp_lcd_dpi_panel_event_callbacks_t cbs = { .on_color_trans_done = on_dpi_trans_done };
    esp_lcd_dpi_panel_register_event_callbacks(disp_panel, &cbs, NULL);
    esp_lcd_panel_disp_on_off(disp_panel, true);

    gpio_config_t bl_cfg = { .pin_bit_mask = (1ULL << 22), .mode = GPIO_MODE_OUTPUT };
    gpio_config(&bl_cfg);
    gpio_set_level(GPIO_NUM_22, 1);

    if (i2c_bus) {
        esp_lcd_panel_io_handle_t tp_io = NULL;
        esp_lcd_panel_io_i2c_config_t tp_io_cfg = ESP_LCD_TOUCH_IO_I2C_ST7123_CONFIG();
        tp_io_cfg.scl_speed_hz = 400000;
        if (esp_lcd_new_panel_io_i2c(i2c_bus, &tp_io_cfg, &tp_io) == ESP_OK) {
            esp_lcd_touch_config_t tp_cfg = { .x_max = 720, .y_max = 1280, .rst_gpio_num = GPIO_NUM_NC, .int_gpio_num = GPIO_NUM_NC };
            if (esp_lcd_touch_new_i2c_st7123(tp_io, &tp_cfg, &tp) == ESP_OK) {
                touch_ready = true;
            }
        }
    }

    lv_init();
    const esp_timer_create_args_t tick_args = { .callback = &lvgl_tick_cb, .name = "lv_tick" };
    esp_timer_handle_t tick_timer = NULL;
    esp_timer_create(&tick_args, &tick_timer);
    esp_timer_start_periodic(tick_timer, 5000);

    lv_disp = lv_display_create(720, 1280);
    size_t buf_sz = 720 * 160 * sizeof(uint16_t);
    void *buf1 = heap_caps_malloc(buf_sz, MALLOC_CAP_SPIRAM);
    void *buf2 = heap_caps_malloc(buf_sz, MALLOC_CAP_SPIRAM);
    lv_display_set_buffers(lv_disp, buf1, buf2, buf_sz, LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(lv_disp, disp_flush_cb);
    lv_display_set_rotation(lv_disp, LV_DISPLAY_ROTATION_90);

    lv_indev_t *indev = lv_indev_create();
    lv_indev_set_type(indev, LV_INDEV_TYPE_POINTER);
    lv_indev_set_read_cb(indev, touch_read_cb);

    vr_game_init(lv_scr_act());
    xTaskCreatePinnedToCore(lvgl_task, "lvgl", 8192, NULL, 5, NULL, 1);
}
