idf_component_register(
    SRCS "main.cpp" "game_world.c" "jpeg_decode.cpp"
    INCLUDE_DIRS "." "assets"
    EMBED_FILES
        "assets/vn/scn_street.jpg"
        "assets/vn/scn_office.jpg"
        "assets/vn/scn_gallery.jpg"
        "assets/vn/scn_vault.jpg"
        "assets/vn/por_vex.jpg"
        "assets/vn/por_fixer.jpg"
        "assets/vn/por_guard.jpg"
)
# Painted VN scenes/portraits (tools/paint_bg.py) are embedded as JPEGs and
# decoded on the P4 by esp_jpeg into RGB565 canvas buffers.
