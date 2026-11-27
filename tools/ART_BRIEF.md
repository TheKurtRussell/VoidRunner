# VoidRunner — Art Brief (hybrid AI workflow)

The game decodes any JPEG dropped into these slots. Generate images in any AI tool
(Midjourney, Flux, SDXL, DALL·E 3, Leonardo…), hand them over, and they get
cropped/resized/wired in automatically via `tools/import_art.py`. You do **not**
need to hit exact pixel sizes — just the right aspect ratio and style.

## Specs
| Slot          | What it is                              | Aspect | Final px  |
|---------------|-----------------------------------------|--------|-----------|
| `scn_street`  | Rainy neon alley (opening shot)         | 16:9   | 1280×720  |
| `scn_office`  | Fixer's dim office, rainy city window   | 16:9   | 1280×720  |
| `scn_gallery` | Gallery / corp tower exterior at night  | 16:9   | 1280×720  |
| `scn_vault`   | High-security gallery vault interior    | 16:9   | 1280×720  |
| `por_vex`     | Vex, the fixer (bust)                    | 4:5    | 192×240   |
| `por_fixer`   | Mr. Johnson, corp suit (bust)           | 4:5    | 192×240   |
| `por_guard`   | Security guard (bust)                   | 4:5    | 192×240   |

Generate large (e.g. scenes at 1920×1080, portraits ~896×1152); downscaling keeps detail.

## Consistency (important)
Keep one cohesive look across every image:
- Same tool + model, and **reuse one style reference** (Midjourney `--sref <code>`
  or a reference image; SDXL/Flux: fixed style + seed family).
- Append the same **style suffix** to every prompt:

> `cyberpunk noir, cinematic concept art, painterly digital painting, dramatic volumetric lighting, rain, wet reflections, magenta-and-cyan neon palette, deep shadows, atmospheric haze, highly detailed, no text, no watermark`

- Keep important content out of the **bottom third** of scenes — a dialogue box sits there.

## Scene prompts (add the style suffix + `--ar 16:9`)
- **scn_street** — "A rain-soaked neon back-alley in a sprawling cyberpunk megacity at night, towering buildings with countless glowing windows, holographic signage, steam, wet reflective asphalt, a lone coated figure walking away, atmospheric fog"
- **scn_office** — "Interior of a dim cyberpunk fixer's office at night, a shadowed figure seated behind a desk, a large rain-streaked floor-to-ceiling window with a glittering neon city beyond, single warm desk lamp, moody film-noir lighting"
- **scn_gallery** — "Exterior of an opulent futuristic art gallery and corporate tower at night in the rain, grand illuminated entrance, marble and glass, sleek neon accents, imposing architecture, reflections on wet stone"
- **scn_vault** — "Interior of a sleek high-security gallery vault at night, glowing glass display cases holding a prototype artifact, dark polished marble, subtle security laser grid, cyan accent light, tense and quiet"

## Portrait prompts (add the style suffix + `--ar 4:5`, head-and-shoulders, face slightly in shadow)
- **por_vex** — "Portrait of Vex, a sharp street-savvy cyberpunk fixer, confident, cybernetic implant details, strong magenta rim light, face half in shadow, dark background"
- **por_fixer** — "Portrait of a corporate Mr. Johnson in an expensive dark suit, cold and composed, cold amber key light, shadowed eyes, dark background"
- **por_guard** — "Portrait of a corporate security officer in sleek tactical armor with a visor, cyan rim light, stern, dark background"

## Handoff
Attach the images in chat (any size/format). I'll run `tools/import_art.py`, commit,
and the next build picks them up — then reflash. More scenes later just means more
slots + story nodes.
