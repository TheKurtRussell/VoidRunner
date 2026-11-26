#include "esp_heap_caps.h"
#include "game_world.h"
#include "assets/vr_assets.h"
#include <stdio.h>
#include <stdlib.h>
#define MAP_W 8
#define MAP_H 8
#define CANVAS_W 920
#define CANVAS_H 540
static const uint8_t street_map[MAP_H][MAP_W]={{1,1,1,2,1,1,1,1},{1,0,0,0,0,0,0,1},{1,0,0,3,0,0,0,1},{1,0,0,0,0,0,0,1},{1,0,0,0,0,3,0,1},{1,0,0,0,0,0,0,1},{1,0,0,0,0,0,0,1},{1,1,1,1,1,1,1,1}};
static int player_gx=3,player_gy=5,target_gx=3,target_gy=5;
static const int johnson_gx=5,johnson_gy=2;
static int nuyen=1250,karma=4,hp_phys=10,hp_stun=10,active_payout=0;
static bool contract_active=false;
static lv_obj_t *canvas,*lbl_stats,*lbl_log,*dlg_panel,*dlg_text,*btn_accept;
static uint16_t *canvas_buf;
/* 1:1 blit with colour-key transparency (0x0000 == clear); sprites are authored
 * at full on-screen resolution by tools/gen_assets.py */
static void blit(const uint16_t *src,int sw,int sh,int dx0,int dy0){
    for(int y=0;y<sh;y++){int py=dy0+y;if(py<0||py>=CANVAS_H)continue;
        const uint16_t *row=&src[y*sw];uint16_t *drow=&canvas_buf[py*CANVAS_W];
        for(int x=0;x<sw;x++){uint16_t c=row[x];if(!c)continue;int px=dx0+x;if(px<0||px>=CANVAS_W)continue;drow[px]=c;}}
}
static void iso(int gx,int gy,int *sx,int *sy){*sx=(CANVAS_W/2)+(gx-gy)*64;*sy=110+(gx+gy)*32;}
/* one drawable placed on the iso grid; bottom-centre of the sprite sits on the
 * tile's diamond centre, so taller sprites rise above the floor */
typedef struct { int gx, gy; const uint16_t *spr; int w, h; } vr_obj_t;
static int vr_obj_cmp(const void *a, const void *b){
    const vr_obj_t *x=a,*y=b;
    int ka=(x->gx+x->gy)*64+x->gx, kb=(y->gx+y->gy)*64+y->gx;
    return ka-kb;
}
static void draw_obj(const vr_obj_t *o){
    int sx,sy; iso(o->gx,o->gy,&sx,&sy);
    blit(o->spr, o->w, o->h, sx - o->w/2, sy + 32 - o->h);
}
static const uint16_t *floor_tile(uint8_t v){
    return v==1?vr_tile_sidewalk : v==2?vr_tile_jackpoint : v==3?vr_tile_puddle : vr_tile_asphalt;
}
static void render_scene(void){
    /* vertical night-sky gradient behind the city */
    for(int y=0;y<CANVAS_H;y++){
        uint16_t c = y<CANVAS_H/2 ? 0x1067 : 0x0842;
        for(int x=0;x<CANVAS_W;x++) canvas_buf[y*CANVAS_W+x]=c;
    }
    /* floor */
    for(int gy=0;gy<MAP_H;gy++)for(int gx=0;gx<MAP_W;gx++){
        int sx,sy; iso(gx,gy,&sx,&sy);
        blit(floor_tile(street_map[gy][gx]),VR_TILE_ASPHALT_W,VR_TILE_ASPHALT_H,sx-VR_TILE_ASPHALT_W/2,sy);
    }
    /* collect depth-sorted objects: a ring of buildings framing the plaza,
     * a few props, then the actors */
    vr_obj_t ob[80]; int n=0;
    for(int gy=-1;gy<=MAP_H;gy++)for(int gx=-1;gx<=MAP_W;gx++){
        if(!(gx==-1||gx==MAP_W||gy==-1||gy==MAP_H)) continue;
        if(gx==3&&gy==-1)
            ob[n++]=(vr_obj_t){gx,gy,vr_building_door,VR_BUILDING_DOOR_W,VR_BUILDING_DOOR_H};
        else if((gx+gy)&1)
            ob[n++]=(vr_obj_t){gx,gy,vr_building_mag,VR_BUILDING_MAG_W,VR_BUILDING_MAG_H};
        else
            ob[n++]=(vr_obj_t){gx,gy,vr_building_cyan,VR_BUILDING_CYAN_W,VR_BUILDING_CYAN_H};
    }
    ob[n++]=(vr_obj_t){6,-1,vr_sign,VR_SIGN_W,VR_SIGN_H};
    ob[n++]=(vr_obj_t){1,-1,vr_lamp,VR_LAMP_W,VR_LAMP_H};
    ob[n++]=(vr_obj_t){-1,5,vr_lamp,VR_LAMP_W,VR_LAMP_H};
    ob[n++]=(vr_obj_t){0,7,vr_crate,VR_CRATE_W,VR_CRATE_H};
    ob[n++]=(vr_obj_t){johnson_gx,johnson_gy,vr_sprite_johnson,VR_SPRITE_JOHNSON_W,VR_SPRITE_JOHNSON_H};
    ob[n++]=(vr_obj_t){player_gx,player_gy,vr_sprite_runner,VR_SPRITE_RUNNER_W,VR_SPRITE_RUNNER_H};
    qsort(ob,n,sizeof(vr_obj_t),vr_obj_cmp);
    for(int i=0;i<n;i++) draw_obj(&ob[i]);
    lv_obj_invalidate(canvas);
}
static void update_hud(void){char b[128];snprintf(b,sizeof(b),"NUYEN: %d Y  |  KARMA: %d  |  PHYS: %d/10  STUN: %d/10",nuyen,karma,hp_phys,hp_stun);lv_label_set_text(lbl_stats,b);}
static void open_johnson(void){if(!contract_active){const char *t[]={"Renraku Sub-Node","Aztechnology Courier","Fuchi Data Vault"};active_payout=850+(rand()%6)*150;char m[256];snprintf(m,sizeof(m),"MR. JOHNSON: \"Evening, chummer. Need an extraction from a %s two blocks east. Clean run pays %d Nuyen. You in?\"",t[rand()%3],active_payout);lv_label_set_text(dlg_text,m);lv_obj_clear_flag(btn_accept,LV_OBJ_FLAG_HIDDEN);}else{lv_label_set_text(dlg_text,"MR. JOHNSON: \"Clock is ticking, runner. Hit the Cyan Jackpoint Pad to deploy.\"");lv_obj_add_flag(btn_accept,LV_OBJ_FLAG_HIDDEN);}lv_obj_clear_flag(dlg_panel,LV_OBJ_FLAG_HIDDEN);}
static void on_accept(lv_event_t *e){contract_active=true;lv_obj_add_flag(dlg_panel,LV_OBJ_FLAG_HIDDEN);char l[160];snprintf(l,sizeof(l),"> CONTRACT ACCEPTED (%d Nuyen). Step onto the CYAN JACKPOINT PAD to run!",active_payout);lv_label_set_text(lbl_log,l);}
static void on_close(lv_event_t *e){lv_obj_add_flag(dlg_panel,LV_OBJ_FLAG_HIDDEN);}
static void on_tap(lv_event_t *e){lv_indev_t *in=lv_indev_active();if(!in)return;lv_point_t p;lv_indev_get_point(in,&p);float rx=(float)(p.x-(CANVAS_W/2))/64.0f,ry=(float)(p.y-126)/32.0f;int gx=(int)((rx+ry)*0.5f+0.5f),gy=(int)((ry-rx)*0.5f+0.5f);if(gx>=0&&gx<MAP_W&&gy>=0&&gy<MAP_H){if(abs(gx-johnson_gx)<=1&&abs(gy-johnson_gy)<=1){target_gx=johnson_gx-1;target_gy=johnson_gy;lv_label_set_text(lbl_log,"> Approaching Mr. Johnson...");}else{target_gx=gx;target_gy=gy;}}}
static void step_cb(lv_timer_t *t){if(player_gx!=target_gx||player_gy!=target_gy){if(player_gx<target_gx)player_gx++;else if(player_gx>target_gx)player_gx--;if(player_gy<target_gy)player_gy++;else if(player_gy>target_gy)player_gy--;render_scene();if(player_gx==target_gx&&player_gy==target_gy){if(abs(player_gx-johnson_gx)<=1&&abs(player_gy-johnson_gy)<=1)open_johnson();else if(street_map[player_gy][player_gx]==2){if(contract_active){nuyen+=active_payout;karma+=2;contract_active=false;update_hud();char l[160];snprintf(l,sizeof(l),"> RUN COMPLETE! +%d Nuyen & +2 Karma wired to credstick.",active_payout);lv_label_set_text(lbl_log,l);}else lv_label_set_text(lbl_log,"> JACKPOINT TERMINAL: Talk to Mr. Johnson first for a contract.");}}}}
void vr_game_init(lv_obj_t *parent){lv_obj_set_style_bg_color(parent,lv_color_hex(0x0A0C14),0);lv_obj_t *hud=lv_obj_create(parent);lv_obj_set_size(hud,1260,56);lv_obj_align(hud,LV_ALIGN_TOP_MID,0,6);lv_obj_set_style_bg_color(hud,lv_color_hex(0x161B2E),0);lv_obj_set_style_border_color(hud,lv_color_hex(0x00F0FF),0);lv_obj_set_style_border_width(hud,2,0);lbl_stats=lv_label_create(hud);lv_obj_set_style_text_color(lbl_stats,lv_color_hex(0x00F0FF),0);lv_obj_align(lbl_stats,LV_ALIGN_LEFT_MID,10,0);update_hud();canvas_buf=heap_caps_malloc(CANVAS_W*CANVAS_H*2,MALLOC_CAP_SPIRAM);canvas=lv_canvas_create(parent);lv_canvas_set_buffer(canvas,canvas_buf,CANVAS_W,CANVAS_H,LV_COLOR_FORMAT_RGB565);lv_obj_align(canvas,LV_ALIGN_TOP_LEFT,10,70);lv_obj_add_flag(canvas,LV_OBJ_FLAG_CLICKABLE);lv_obj_add_event_cb(canvas,on_tap,LV_EVENT_CLICKED,NULL);lv_obj_t *side=lv_obj_create(parent);lv_obj_set_size(side,330,540);lv_obj_align(side,LV_ALIGN_TOP_RIGHT,-10,70);lv_obj_set_style_bg_color(side,lv_color_hex(0x121626),0);lv_obj_set_style_border_color(side,lv_color_hex(0xFF2AA5),0);lv_obj_set_style_border_width(side,2,0);lv_obj_t *pc=lv_canvas_create(side);lv_canvas_set_buffer(pc,(void*)vr_portrait_runner,96,96,LV_COLOR_FORMAT_RGB565);lv_obj_align(pc,LV_ALIGN_TOP_MID,0,8);lv_obj_t *bio=lv_label_create(side);lv_label_set_text(bio,"HANDLE: VOIDRUNNER\nARCHETYPE: DECKER/SAMURAI\nSECTOR: SEATTLE BARRENS\n\n- Tap tiles to move\n- Tap MR. JOHNSON for runs\n- Step on CYAN PAD to jack in");lv_obj_set_style_text_color(bio,lv_color_hex(0xD8E4FF),0);lv_obj_align(bio,LV_ALIGN_TOP_LEFT,8,120);lv_obj_t *lb=lv_obj_create(parent);lv_obj_set_size(lb,1260,88);lv_obj_align(lb,LV_ALIGN_BOTTOM_MID,0,-8);lv_obj_set_style_bg_color(lb,lv_color_hex(0x0D111C),0);lv_obj_set_style_border_color(lb,lv_color_hex(0x28EB78),0);lv_obj_set_style_border_width(lb,2,0);lbl_log=lv_label_create(lb);lv_label_set_text(lbl_log,"> VOIDRUNNER ONLINE. Tap MR. JOHNSON (upper right) to negotiate a run.");lv_obj_set_style_text_color(lbl_log,lv_color_hex(0x28EB78),0);lv_obj_align(lbl_log,LV_ALIGN_LEFT_MID,8,0);dlg_panel=lv_obj_create(parent);lv_obj_set_size(dlg_panel,760,220);lv_obj_center(dlg_panel);lv_obj_set_style_bg_color(dlg_panel,lv_color_hex(0x181D30),0);lv_obj_set_style_border_color(dlg_panel,lv_color_hex(0xFFB928),0);lv_obj_set_style_border_width(dlg_panel,3,0);lv_obj_add_flag(dlg_panel,LV_OBJ_FLAG_HIDDEN);lv_obj_t *jp=lv_canvas_create(dlg_panel);lv_canvas_set_buffer(jp,(void*)vr_portrait_johnson,96,96,LV_COLOR_FORMAT_RGB565);lv_obj_align(jp,LV_ALIGN_LEFT_MID,10,0);dlg_text=lv_label_create(dlg_panel);lv_obj_set_width(dlg_text,580);lv_label_set_long_mode(dlg_text,LV_LABEL_LONG_WRAP);lv_obj_set_style_text_color(dlg_text,lv_color_hex(0xFFF2D6),0);lv_obj_align(dlg_text,LV_ALIGN_TOP_LEFT,125,14);btn_accept=lv_btn_create(dlg_panel);lv_obj_set_size(btn_accept,180,44);lv_obj_align(btn_accept,LV_ALIGN_BOTTOM_RIGHT,-210,-10);lv_obj_set_style_bg_color(btn_accept,lv_color_hex(0x1E8E5A),0);lv_obj_add_event_cb(btn_accept,on_accept,LV_EVENT_CLICKED,NULL);lv_obj_t *la=lv_label_create(btn_accept);lv_label_set_text(la,"ACCEPT RUN");lv_obj_center(la);lv_obj_t *bl=lv_btn_create(dlg_panel);lv_obj_set_size(bl,180,44);lv_obj_align(bl,LV_ALIGN_BOTTOM_RIGHT,-14,-10);lv_obj_set_style_bg_color(bl,lv_color_hex(0x8E2438),0);lv_obj_add_event_cb(bl,on_close,LV_EVENT_CLICKED,NULL);lv_obj_t *ll=lv_label_create(bl);lv_label_set_text(ll,"WALK AWAY");lv_obj_center(ll);render_scene();lv_timer_create(step_cb,140,NULL);}
