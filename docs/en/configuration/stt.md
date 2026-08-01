# STT Configs

Use the **STT** tab to configure a whisper.cpp HTTP server connection for speech recognition.

<!-- Screenshot placeholder: STT config editor with whisper.cpp connection, language, translate, temperature, and initial prompt fields. -->

Only one STT backend is expected. It is shared by every simulation rather than assigned per world or per component.

## Fields

| Field | Description |
| --- | --- |
| `connection` | A `whispercpp` connection whose base URL points to a reachable whisper.cpp server. |
| `model` | Optional model label for display or backend selection where supported. |
| `language` | Spoken language code, such as `en`, `zh`, or `auto`. |
| `translate` | Whether to translate the transcription into English. |
| `temperature` | Decoding temperature. |
| `temperature_inc` | Temperature increment used on decoding fallback. |
| `initial_prompt` | Optional prompt text to bias vocabulary or context. |
| `carry_initial_prompt` | Whether to prepend the initial prompt for each request. |

When the backend runs in Docker, make sure the whisper.cpp URL is reachable from the backend container, not just from the host browser.
