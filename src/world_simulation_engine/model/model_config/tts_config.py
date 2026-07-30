from uuid import uuid4
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ConnectionType, TtsEngine, TtsTextFilteringMode, TtsTextNotInsideMode
from .connection_config import ConnectionConfig


class TtsModelConfig(BaseModel):
    """
    The configuration for a TTS (text-to-speech) model: connection, engine, and shared generation
    parameters. Deliberately holds no voice of any kind - narrator voice lives on TtsGenerationConfig and
    each character's voice lives on CharacterTtsConfig, so many characters (and the narrator) can share one
    backend config while each picking their own voice.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for the model",
    )
    name: Optional[str] = Field(
        None,
        description="Display name of the TTS config, falls back to the model/engine identifier when unset",
    )
    model: Optional[str] = Field(
        None,
        description="Name of the model to use, for providers that support switching the underlying TTS model",
    )
    connection: Optional[ConnectionConfig] = Field(
        None,
        description="The provider connection used by this TTS model config",
    )


class AllTalkTtsModelConfig(TtsModelConfig):
    """
    Fields common to every AllTalk V2 TTS engine, and shared across every character using this backend.
    AllTalk applies narrator splitting, RVC post-processing, and output handling itself, independently of
    which underlying TTS engine (xtts, piper, vits, ...) is loaded, so these fields are always valid
    regardless of engine. Engine-specific generation parameters (e.g. temperature, pitch, language support)
    live on the per-engine subclasses instead, since AllTalk's engines do not all support the same knobs.

    No voice of any kind lives here: a character's voice (character_voice, rvc_character_voice,
    rvc_character_pitch) lives on CharacterTtsConfig, and the narrator's voice (narrator_voice,
    rvc_narrator_voice, rvc_narrator_pitch) lives on TtsGenerationConfig, since the narrator is a
    per-simulation concept rather than part of the shared backend (see Character -[:HAS_CONFIG]->
    CharacterTtsConfig -[:USE_CONFIG]-> AllTalk*ModelConfig).
    """

    provider: Literal[ConnectionType.ALLTALK] = Field(
        ConnectionType.ALLTALK,
        description="Provider for this TTS model config",
    )
    text_filtering: Optional[TtsTextFilteringMode] = Field(
        None,
        description="Text filtering mode applied to the input text before synthesis",
    )
    text_not_inside: Optional[TtsTextNotInsideMode] = Field(
        None,
        description="How to voice text that is not inside quotes, when the narrator is enabled",
    )
    narrator_enabled: Optional[bool] = Field(
        None,
        description="Whether to enable the narrator voice for text outside quotes",
    )
    output_file_timestamp: Optional[bool] = Field(
        None,
        description="Whether to append a timestamp to the generated output file name",
    )
    autoplay: Optional[bool] = Field(
        None,
        description="Whether the AllTalk server should play the generated audio at its own terminal",
    )
    autoplay_volume: Optional[float] = Field(
        None,
        ge=0.1,
        le=1.0,
        description="Playback volume used by the AllTalk server when autoplay is enabled",
    )


class AllTalkXttsModelConfig(AllTalkTtsModelConfig):
    """
    Configuration for AllTalk's XTTS engine (Coqui XTTSv2): zero-shot voice cloning from a WAV sample,
    multi-language, sampling-based generation. Does not support pitch adjustment.
    """

    engine: Literal[TtsEngine.XTTS] = Field(
        TtsEngine.XTTS,
        description="AllTalk TTS engine backing this config",
    )
    language: Optional[str] = Field(
        None,
        description="Language for the TTS generation, e.g. 'en', 'zh-cn', or 'auto'",
    )
    speed: Optional[float] = Field(
        None,
        ge=0.25,
        le=2.0,
        description="Speed of the generated speech",
    )
    temperature: Optional[float] = Field(
        None,
        ge=0.1,
        le=1.0,
        description="Sampling temperature for the TTS engine",
    )
    repetition_penalty: Optional[float] = Field(
        None,
        ge=1.0,
        le=20.0,
        description="Repetition penalty for the TTS engine",
    )


class AllTalkPiperModelConfig(AllTalkTtsModelConfig):
    """
    Configuration for AllTalk's Piper engine: fast, deterministic ONNX voice models. No voice cloning,
    no sampling parameters (temperature/repetition penalty), no runtime language switching, and no pitch
    adjustment - only playback speed is tunable.
    """

    engine: Literal[TtsEngine.PIPER] = Field(
        TtsEngine.PIPER,
        description="AllTalk TTS engine backing this config",
    )
    speed: Optional[float] = Field(
        None,
        ge=0.25,
        le=2.0,
        description="Speed of the generated speech",
    )


class AllTalkVitsModelConfig(AllTalkTtsModelConfig):
    """
    Configuration for AllTalk's VITS engine: individual voice model files, with multi-language support
    depending on the loaded model. No sampling parameters (temperature/repetition penalty) or pitch
    adjustment.
    """

    engine: Literal[TtsEngine.VITS] = Field(
        TtsEngine.VITS,
        description="AllTalk TTS engine backing this config",
    )
    language: Optional[str] = Field(
        None,
        description="Language for the TTS generation, if supported by the loaded VITS model file",
    )
    speed: Optional[float] = Field(
        None,
        ge=0.25,
        le=2.0,
        description="Speed of the generated speech",
    )


class AllTalkParlerModelConfig(AllTalkTtsModelConfig):
    """
    Configuration for AllTalk's Parler engine: voices are described in natural language rather than
    selected from a WAV sample (narrator_voice here, and character_voice on CharacterTtsConfig, hold the
    written voice description instead of a filename). Supports sampling temperature but not repetition
    penalty or pitch adjustment.
    """

    engine: Literal[TtsEngine.PARLER] = Field(
        TtsEngine.PARLER,
        description="AllTalk TTS engine backing this config",
    )
    speed: Optional[float] = Field(
        None,
        ge=0.25,
        le=2.0,
        description="Speed of the generated speech",
    )
    temperature: Optional[float] = Field(
        None,
        ge=0.1,
        le=1.0,
        description="Sampling temperature for the TTS engine",
    )


class AllTalkF5ttsModelConfig(AllTalkTtsModelConfig):
    """
    Configuration for AllTalk's F5-TTS engine: voice cloning from a reference WAV sample, English and
    Chinese only. Flow-matching generation, so no sampling temperature/repetition penalty or pitch
    adjustment - only playback speed is tunable.
    """

    engine: Literal[TtsEngine.F5TTS] = Field(
        TtsEngine.F5TTS,
        description="AllTalk TTS engine backing this config",
    )
    language: Optional[str] = Field(
        None,
        description="Language for the TTS generation. F5-TTS only supports 'en' and 'zh-cn'",
    )
    speed: Optional[float] = Field(
        None,
        ge=0.25,
        le=2.0,
        description="Speed of the generated speech",
    )


class AllTalkStatus(BaseModel):
    """
    Live status reported by a running AllTalk V2 server for a given connection: the engine/model it
    currently has loaded, which inference-time parameters that engine supports, and the voices/RVC voices
    actually present on disk. This app never changes AllTalk's own engine/model configuration, so config
    editors should use this - rather than a hardcoded per-engine guess - to decide which fields to show and
    which voices are selectable.
    """

    engine: TtsEngine = Field(..., description="TTS engine currently loaded on the AllTalk server")
    model: Optional[str] = Field(None, description="Model currently loaded for the active engine")
    models_available: list[str] = Field(
        default_factory=list, description="Models available for the active engine",
    )
    languages_capable: bool = Field(False, description="Whether the active engine supports language selection")
    temperature_capable: bool = Field(
        False, description="Whether the active engine supports sampling temperature",
    )
    repetition_penalty_capable: bool = Field(
        False, description="Whether the active engine supports repetition penalty",
    )
    generation_speed_capable: bool = Field(False, description="Whether the active engine supports speed adjustment")
    voices: list[str] = Field(default_factory=list, description="Voices currently available on the AllTalk server")
    rvc_voices: list[str] = Field(
        default_factory=list, description="RVC voice models currently available on the AllTalk server",
    )


AllTalkTtsModelConfigUnion = Annotated[
    Union[
        AllTalkXttsModelConfig,
        AllTalkPiperModelConfig,
        AllTalkVitsModelConfig,
        AllTalkParlerModelConfig,
        AllTalkF5ttsModelConfig,
    ],
    Field(discriminator="engine"),
]

# AllTalk is currently the only TTS provider, so this is discriminated directly by engine. A
# discriminated union nested one level deeper (provider -> engine, mirroring how ImageModelConfigUnion
# and ChatModelConfigUnion are structured) only works in pydantic once there are 2+ provider
# branches - with a single branch it collapses and "provider" stops being a valid discriminator.
# Once a second TTS provider is added, restructure this as
# Annotated[Union[AllTalkTtsModelConfigUnion, ...], Field(discriminator="provider")].
TtsModelConfigUnion = AllTalkTtsModelConfigUnion
