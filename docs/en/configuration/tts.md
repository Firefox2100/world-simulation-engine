# TTS Configs

Use the **TTS** tab to create AllTalk backend configs. The shared backend config controls engine-level settings; narrator and character voices are selected separately.

<!-- Screenshot placeholder: TTS config editor with AllTalk connection, engine status, text filtering, language, speed, temperature, and playback fields. -->

## Backend config

The frontend reads AllTalk's live engine, loaded model, voices, and capability flags from the selected connection. The app does not change AllTalk's own engine/model configuration; it mirrors the active server state and stores generation-time options that the active engine supports.

Typical fields include text filtering, how to handle text outside speech tags, output filename timestamps, server autoplay, autoplay volume, language, speed, temperature, and repetition penalty.

## Per-simulation generation

Per-simulation TTS generation settings:

| Field | Description |
| --- | --- |
| `mode` | `manual` or `auto`. Manual generates audio on demand. Auto voices turn narration/speech after the turn is committed. |
| `autoplay_in_browser` | When enabled with auto mode, the frontend plays generated segments in sequence in the browser. |
| `narrator_voice` | Voice used for narration and unattributed speech. |
| `rvc_narrator_voice` | Optional RVC model for narrator voice conversion. |
| `rvc_narrator_pitch` | Optional narrator RVC pitch adjustment from `-24` to `24`. |

Character-specific voice selection lives on each character's TTS config and can point back to a shared TTS backend.
