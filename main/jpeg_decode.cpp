/*
 * JPEG -> native RGB565 decode using M5GFX's built-in decoder (the same library
 * that drives the Tab5 panel), exposed to the C VN engine.
 *
 * Decodes into an off-screen PSRAM sprite, then reads it back as lgfx::rgb565_t
 * (CPU-native RGB565, matching LVGL's canvas format) into `out`.
 */
#include <M5GFX.h>

extern "C" bool vr_decode_jpeg(const uint8_t *data, uint32_t len,
                               uint16_t *out, int w, int h)
{
    M5Canvas spr;
    spr.setPsram(true);
    spr.setColorDepth(16);
    if (!spr.createSprite(w, h)) {
        return false;
    }
    spr.fillScreen(0);
    bool ok = spr.drawJpg(data, len, 0, 0, w, h);   // our JPEGs are authored at w x h
    if (ok) {
        spr.readRect(0, 0, w, h, reinterpret_cast<lgfx::rgb565_t *>(out));
    }
    spr.deleteSprite();
    return ok;
}
