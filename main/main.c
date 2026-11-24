#include "bsp/m5stack_tab5.h"
#include "game_world.h"
void app_main(void){bsp_display_cfg_t cfg={.lvgl_port_cfg=ESP_LVGL_PORT_INIT_CONFIG(),.buffer_size=1280*80,.double_buffer=true,.flags={.buff_dma=false,.buff_spiram=true}};lv_disp_t *d=bsp_display_start_with_config(&cfg);bsp_display_rotate(d,LV_DISPLAY_ROTATION_90);bsp_display_backlight_on();bsp_display_lock(0);vr_game_init(lv_scr_act());bsp_display_unlock();}
