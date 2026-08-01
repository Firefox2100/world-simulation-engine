# Image Generation Configs

Image generation uses both an image service config and an LLM chat config:

- The image config sends the final prompt to the image backend, currently ComfyUI.
- The chat config builds image prompts from world state, character state, or narration.

Use the **Images** tab in **Configurations** to create reusable ComfyUI image model configs.

<!-- Screenshot placeholder: Image model config editor with ComfyUI connection, model, VAE, CLIP, dimensions, seed, steps, and CFG. -->

## ComfyUI image fields

| Field | Description |
| --- | --- |
| `model` | Optional checkpoint/model name. |
| `vae` | Optional VAE model name. |
| `clip` | Optional CLIP model name. |
| `image_width` / `image_height` | Optional requested image dimensions. |
| `seed` | Optional deterministic seed. |
| `steps` | Optional generation step count. |
| `cfg` | Optional classifier-free guidance value. |

## Assignments

Assign image configs to world or simulation image components:

| Component | Purpose |
| --- | --- |
| `character_image_generator` | Character state/cover images. |
| `character_portrait_image_generator` | Character portrait images. |
| `location_image_generator` | Location images. |
| `item_image_generator` | Item images. |
| `scene_image_generator` | Turn or scene illustrations. |

For automatic turn images, make sure both `scene_image_generator` and `turn_image_trigger` have suitable chat model assignments, and that `scene_image_generator` also has an image model assignment.

## Per-simulation behavior

Per-simulation image generation behavior is controlled by `ImageGenerationConfig`:

| Field | Description |
| --- | --- |
| `mode` | `manual`, `auto`, or `always`. Manual only generates on request. Auto uses a significance check and fallback interval. Always generates every turn. |
| `fallback_turns` | In `auto` mode, force an image after this many turns without one. |

<!-- Screenshot placeholder: Simulation Image Generation tab showing image model assignments and generation behavior settings. -->
