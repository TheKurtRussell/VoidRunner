#include <M5GFX.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"
#include "esp_heap_caps.h"
#include "lvgl.h"
extern "C" {
#include "game_world.h"
}

static M5GFX display;

static void lvgl_tick_cb(void *arg) { lv_tick_inc(5); }

static void disp_flush_cb(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map) {
    uint32_t w = (area->x2 - area->x1 + 1);
    uint32_t h = (area->y2 - area->y1 + 1);
    display.pushImage(area->x1, area->y1, w, h, (uint16_t *)px_map);
    lv_display_flush_ready(disp);
}

static void touch_read_cb(lv_indev_t *indev, lv_indev_data_t *data) {
    uint16_t tx = 0, ty = 0;
    if (display.getTouch(&tx, &ty)) {
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

extern "C" void app_main(void) {
    display.begin();
    display.setRotation(1);
    display.setBrightness(220);
    display.setSwapBytes(true);

    lv_init();
    const esp_timer_create_args_t tick_args = { .callback = &lvgl_tick_cb, .name = "lv_tick" };
    esp_timer_handle_t tick_timer = NULL;
    esp_timer_create(&tick_args, &tick_timer);
    esp_timer_start_periodic(tick_timer, 5000);

    lv_display_t *disp = lv_display_create(1280, 720);
    size_t buf_sz = 1280 * 120 * sizeof(uint16_t);
    void *buf1 = heap_caps_malloc(buf_sz, MALLOC_CAP_SPIRAM);
    void *buf2 = heap_caps_malloc(buf_sz, MALLOC_CAP_SPIRAM);
    lv_display_set_buffers(disp, buf1, buf2, buf_sz, LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_flush_cb(disp, disp_flush_cb);

    lv_indev_t *indev = lv_indev_create();
    lv_indev_set_type(indev, LV_INDEV_TYPE_POINTER);
    lv_indev_set_read_cb(indev, touch_read_cb);

    vr_game_init(lv_scr_act());
    xTaskCreatePinnedToCore(lvgl_task, "lvgl", 8192, NULL, 5, NULL, 1);
}
