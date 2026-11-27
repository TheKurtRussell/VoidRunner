/*
 * VoidRunner — cinematic visual-novel engine.
 *
 * Painted scenes + portraits are embedded as JPEGs and decoded on the ESP32-P4
 * (esp_jpeg) into RGB565 canvas buffers. A node graph drives narration, speaker
 * dialogue, branching choices, and nuyen/karma state. No tile engine.
 */
#include "lvgl.h"
#include "game_world.h"
#include "esp_heap_caps.h"
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>

/* JPEG -> native RGB565, implemented in jpeg_decode.cpp via M5GFX */
extern bool vr_decode_jpeg(const uint8_t *data, uint32_t len, uint16_t *out, int w, int h);

/* ---- embedded assets ---------------------------------------------------- */
#define EMB(sym) extern const uint8_t sym##_start[] asm("_binary_" #sym "_start"); \
                 extern const uint8_t sym##_end[]   asm("_binary_" #sym "_end");
EMB(scn_street_jpg) EMB(scn_office_jpg) EMB(scn_gallery_jpg) EMB(scn_vault_jpg)
EMB(por_vex_jpg) EMB(por_fixer_jpg) EMB(por_guard_jpg)

typedef struct { const uint8_t *s, *e; } blob_t;
static const blob_t scenes[] = {
    {scn_street_jpg_start, scn_street_jpg_end},
    {scn_office_jpg_start, scn_office_jpg_end},
    {scn_gallery_jpg_start, scn_gallery_jpg_end},
    {scn_vault_jpg_start, scn_vault_jpg_end},
};
static const blob_t portraits[] = {
    {por_vex_jpg_start, por_vex_jpg_end},
    {por_fixer_jpg_start, por_fixer_jpg_end},
    {por_guard_jpg_start, por_guard_jpg_end},
};
enum { SC_STREET, SC_OFFICE, SC_GALLERY, SC_VAULT };
enum { P_VEX, P_FIXER, P_GUARD };

/* ---- story graph -------------------------------------------------------- */
typedef struct { const char *label; int next; int dnuyen; int dkarma; } vn_choice_t;
typedef struct {
    int scene;              /* -1 = keep current background */
    int portrait;           /* -1 = none (narration) */
    const char *speaker;    /* NULL = narration */
    const char *text;
    vn_choice_t choices[3]; /* label NULL = unused */
} vn_node_t;

static const vn_node_t story[] = {
/*0*/ { SC_STREET, -1, NULL,
        "Rain hammers the Seattle Barrens. Neon bleeds down the glass and pools in the gutters. "
        "Your commlink buzzes against your ribs — an encrypted ping. Vex has work.",
        { {"Answer it", 1, 0, 0}, {0}, {0} } },
/*1*/ { SC_OFFICE, P_VEX, "VEX",
        "\"Evening, chummer. Saeder-Krupp moved a prototype deck into the downtown gallery. "
        "Corp security's running a skeleton crew tonight. Clean grab. You in?\"",
        { {"Take the job", 2, 0, 0}, {"How much?", 3, 0, 0}, {"Walk away", 4, 0, 0} } },
/*2*/ { -1, P_VEX, "VEX",
        "\"Knew I called the right runner. Eight-k nuyen on delivery. Don't get sentimental "
        "with the merch — in and out.\"",
        { {"Head to the gallery", 5, 0, 1}, {0}, {0} } },
/*3*/ { -1, P_VEX, "VEX",
        "\"Price? Twelve-five. I'll wire half to your credstick now as a show of faith. "
        "The rest when the deck's in my hands.\"",
        { {"Take it (6,250 up front)", 5, 6250, 0}, {"Still too risky — walk", 4, 0, 0} } },
/*4*/ { SC_STREET, -1, NULL,
        "You let the ping ring out. Some runs aren't worth the body bag. The rain keeps falling, "
        "and the credstick stays light. Maybe next time, chummer.",
        { {"Reconsider", 1, 0, 0}, {0}, {0} } },
/*5*/ { SC_GALLERY, -1, NULL,
        "Midnight. The gallery's spires bleed violet into the storm. Two ways in: a dark service "
        "door down the alley, or the lit marble lobby out front.",
        { {"Slip in the side", 6, 0, 1}, {"Stroll through the front", 7, 0, -1} } },
/*6*/ { SC_VAULT, P_GUARD, "SECURITY",
        "A patrol light sweeps the corridor. You melt into the dark between display cases and hold "
        "your breath. Boots pass within a meter, then recede. You're through.",
        { {"Reach the vault", 8, 8000, 1}, {0}, {0} } },
/*7*/ { SC_VAULT, P_GUARD, "SECURITY",
        "\"Hey! The gallery's closed, pal—\" The guard reaches for his radio. You move first. "
        "It's messy and loud, but the corridor's yours.",
        { {"Reach the vault", 8, 8000, -2}, {0}, {0} } },
/*8*/ { -1, -1, NULL,
        "The prototype deck hums in its cradle, haloed in cyan. You lift it, and the case alarm "
        "stays dark — clean. Sixty seconds to extraction. Vex is going to owe you.\n\n[ END OF PROLOGUE ]",
        { {"Run it again", 1, 0, 0}, {0}, {0} } },
};

/* ---- state + widgets ---------------------------------------------------- */
static int nuyen = 2000, karma = 0, cur_node = 0, cur_scene = -1;
static uint16_t *bg_buf, *por_buf;
#define BGW 1280
#define BGH 720
#define PW 192
#define PH 240
static lv_obj_t *bg_canvas, *por_canvas, *panel, *lbl_speaker, *lbl_text, *lbl_hud;
static lv_obj_t *btn[3], *btn_lbl[3];

static void decode_jpg(const blob_t *b, uint16_t *out, int w, int h) {
    if (!vr_decode_jpeg(b->s, (uint32_t)(b->e - b->s), out, w, h)) {
        for (int i = 0; i < w * h; i++) out[i] = 0x1082;  /* dark fallback */
    }
}

static void update_hud(void) {
    char b[96];
    snprintf(b, sizeof(b), "NUYEN %d   KARMA %d", nuyen, karma);
    lv_label_set_text(lbl_hud, b);
}

static void show_node(int idx) {
    cur_node = idx;
    const vn_node_t *n = &story[idx];
    if (n->scene >= 0 && n->scene != cur_scene) {
        decode_jpg(&scenes[n->scene], bg_buf, BGW, BGH);
        cur_scene = n->scene;
        lv_obj_invalidate(bg_canvas);
    }
    if (n->portrait >= 0) {
        decode_jpg(&portraits[n->portrait], por_buf, PW, PH);
        lv_obj_invalidate(por_canvas);
        lv_obj_clear_flag(por_canvas, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(por_canvas, LV_OBJ_FLAG_HIDDEN);
    }
    if (n->speaker) {
        lv_label_set_text(lbl_speaker, n->speaker);
        lv_obj_clear_flag(lbl_speaker, LV_OBJ_FLAG_HIDDEN);
    } else {
        lv_obj_add_flag(lbl_speaker, LV_OBJ_FLAG_HIDDEN);
    }
    lv_label_set_text(lbl_text, n->text);
    for (int i = 0; i < 3; i++) {
        if (n->choices[i].label) {
            lv_label_set_text(btn_lbl[i], n->choices[i].label);
            lv_obj_clear_flag(btn[i], LV_OBJ_FLAG_HIDDEN);
        } else {
            lv_obj_add_flag(btn[i], LV_OBJ_FLAG_HIDDEN);
        }
    }
    update_hud();
}

static void on_choice(lv_event_t *e) {
    int i = (int)(intptr_t)lv_event_get_user_data(e);
    const vn_choice_t *c = &story[cur_node].choices[i];
    if (!c->label) return;
    nuyen += c->dnuyen;
    karma += c->dkarma;
    show_node(c->next);
}

void vr_game_init(lv_obj_t *parent) {
    lv_obj_set_style_bg_color(parent, lv_color_hex(0x05070E), 0);

    bg_buf = heap_caps_malloc(BGW * BGH * 2, MALLOC_CAP_SPIRAM);
    por_buf = heap_caps_malloc(PW * PH * 2, MALLOC_CAP_SPIRAM);

    bg_canvas = lv_canvas_create(parent);
    lv_canvas_set_buffer(bg_canvas, bg_buf, BGW, BGH, LV_COLOR_FORMAT_RGB565);
    lv_obj_align(bg_canvas, LV_ALIGN_TOP_LEFT, 0, 0);

    /* portrait */
    por_canvas = lv_canvas_create(parent);
    lv_canvas_set_buffer(por_canvas, por_buf, PW, PH, LV_COLOR_FORMAT_RGB565);
    lv_obj_align(por_canvas, LV_ALIGN_TOP_LEFT, 56, 236);
    lv_obj_set_style_border_color(por_canvas, lv_color_hex(0xFF2AA5), 0);
    lv_obj_set_style_border_width(por_canvas, 2, 0);

    /* HUD */
    lbl_hud = lv_label_create(parent);
    lv_obj_set_style_text_color(lbl_hud, lv_color_hex(0x7CF5C2), 0);
    lv_obj_align(lbl_hud, LV_ALIGN_TOP_RIGHT, -20, 16);

    /* dialogue panel */
    panel = lv_obj_create(parent);
    lv_obj_set_size(panel, 1196, 212);
    lv_obj_align(panel, LV_ALIGN_BOTTOM_MID, 0, -14);
    lv_obj_set_style_bg_color(panel, lv_color_hex(0x080A14), 0);
    lv_obj_set_style_bg_opa(panel, 205, 0);
    lv_obj_set_style_border_color(panel, lv_color_hex(0x00F0FF), 0);
    lv_obj_set_style_border_width(panel, 2, 0);
    lv_obj_set_style_radius(panel, 4, 0);
    lv_obj_clear_flag(panel, LV_OBJ_FLAG_SCROLLABLE);

    lbl_speaker = lv_label_create(panel);
    lv_obj_set_style_bg_color(lbl_speaker, lv_color_hex(0xFF2AA5), 0);
    lv_obj_set_style_bg_opa(lbl_speaker, 255, 0);
    lv_obj_set_style_text_color(lbl_speaker, lv_color_hex(0x0A0A10), 0);
    lv_obj_set_style_pad_all(lbl_speaker, 5, 0);
    lv_obj_align(lbl_speaker, LV_ALIGN_TOP_LEFT, 6, 6);

    lbl_text = lv_label_create(panel);
    lv_label_set_long_mode(lbl_text, LV_LABEL_LONG_WRAP);
    lv_obj_set_width(lbl_text, 720);
    lv_obj_set_style_text_color(lbl_text, lv_color_hex(0xDEE8F6), 0);
    lv_obj_align(lbl_text, LV_ALIGN_TOP_LEFT, 236, 40);

    for (int i = 0; i < 3; i++) {
        btn[i] = lv_btn_create(panel);
        lv_obj_set_size(btn[i], 300, 50);
        lv_obj_align(btn[i], LV_ALIGN_TOP_RIGHT, -10, 14 + i * 58);
        lv_obj_set_style_bg_color(btn[i], lv_color_hex(0x13241F), 0);
        lv_obj_set_style_border_color(btn[i], lv_color_hex(0x7CF5C2), 0);
        lv_obj_set_style_border_width(btn[i], 2, 0);
        lv_obj_set_style_radius(btn[i], 3, 0);
        lv_obj_add_event_cb(btn[i], on_choice, LV_EVENT_CLICKED, (void *)(intptr_t)i);
        btn_lbl[i] = lv_label_create(btn[i]);
        lv_obj_set_style_text_color(btn_lbl[i], lv_color_hex(0x7CF5C2), 0);
        lv_obj_center(btn_lbl[i]);
    }

    show_node(0);
}
