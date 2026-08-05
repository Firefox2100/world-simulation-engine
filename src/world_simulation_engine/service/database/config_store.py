import json

from neo4j import AsyncDriver
from pydantic import TypeAdapter

from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import ConnectionConfig, ChatModelConfigUnion, EmbedModelConfigUnion, \
    ComfyUiImageModelConfig, ImageModelConfigUnion, ImageGenerationConfig, AllTalkF5ttsModelConfig, \
    AllTalkParlerModelConfig, AllTalkPiperModelConfig, AllTalkVitsModelConfig, AllTalkXttsModelConfig, \
    TtsModelConfigUnion, TtsGenerationConfig, SttModelConfigUnion, WhisperCppSttModelConfig


TTS_CONFIG_LABELS = (
    "AllTalkXttsModelConfig|AllTalkPiperModelConfig|AllTalkVitsModelConfig|"
    "AllTalkParlerModelConfig|AllTalkF5ttsModelConfig"
)

STT_CONFIG_LABELS = "WhisperCppSttModelConfig"

CHAT_CONFIG_LABELS = (
    "OllamaChatModelConfig|OpenAiChatModelConfig|AnthropicChatModelConfig|OpenRouterChatModelConfig|"
    "GoogleGenAiChatModelConfig|MistralAiChatModelConfig|CohereChatModelConfig|"
    "PerplexityChatModelConfig|GroqChatModelConfig|DeepSeekChatModelConfig|XAiChatModelConfig|"
    "CloudflareChatModelConfig"
)

CHAT_CONFIG_PROVIDERS = {
    "OllamaChatModelConfig": "ollama",
    "OpenAiChatModelConfig": "openai",
    "AnthropicChatModelConfig": "anthropic",
    "OpenRouterChatModelConfig": "openrouter",
    "GoogleGenAiChatModelConfig": "google_genai",
    "MistralAiChatModelConfig": "mistralai",
    "CohereChatModelConfig": "cohere",
    "PerplexityChatModelConfig": "perplexity",
    "GroqChatModelConfig": "groq",
    "DeepSeekChatModelConfig": "deepseek",
    "XAiChatModelConfig": "xai",
    "CloudflareChatModelConfig": "cloudflare",
}

CHAT_CONFIG_ADAPTER = TypeAdapter(ChatModelConfigUnion)

EMBED_CONFIG_LABELS = (
    "OllamaEmbedModelConfig|OpenAiEmbedModelConfig|GoogleGenAiEmbedModelConfig|"
    "MistralAiEmbedModelConfig|CohereEmbedModelConfig|PerplexityEmbedModelConfig|CloudflareEmbedModelConfig"
)

EMBED_CONFIG_PROVIDERS = {
    "OllamaEmbedModelConfig": "ollama",
    "OpenAiEmbedModelConfig": "openai",
    "GoogleGenAiEmbedModelConfig": "google_genai",
    "MistralAiEmbedModelConfig": "mistralai",
    "CohereEmbedModelConfig": "cohere",
    "PerplexityEmbedModelConfig": "perplexity",
    "CloudflareEmbedModelConfig": "cloudflare",
}

EMBED_CONFIG_ADAPTER = TypeAdapter(EmbedModelConfigUnion)


def _node_properties(config_node) -> dict:
    return {
        key: config_node.get(key)
        for key in config_node.keys()
    }


def _encode_model_property(value):
    if isinstance(value, dict | tuple):
        return json.dumps(value)
    if isinstance(value, list) and any(isinstance(item, dict | list | tuple) for item in value):
        return json.dumps(value)
    return value


def _decode_model_property(value):
    if not isinstance(value, str) or not value:
        return value
    if value[0] not in "[{":
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _chat_provider_from_labels(labels: list[str]) -> str:
    for label in labels:
        provider = CHAT_CONFIG_PROVIDERS.get(label)
        if provider is not None:
            return provider
    raise ValueError(f"Unknown config labels {labels}")


def _embed_provider_from_labels(labels: list[str]) -> str:
    for label in labels:
        provider = EMBED_CONFIG_PROVIDERS.get(label)
        if provider is not None:
            return provider
    raise ValueError(f"Unknown config labels {labels}")


def _connection_from_node(connection_node) -> ConnectionConfig:
    return ConnectionConfig(
        id=connection_node["id"],
        type=connection_node["type"],
        name=connection_node["name"],
        base_url=connection_node.get("base_url"),
        api_key=connection_node.get("api_key"),
    )


def _connection_from_optional_node(connection_node) -> ConnectionConfig | None:
    return _connection_from_node(connection_node) if connection_node else None


def _chat_from_node(config_node, labels: list[str], connection_node=None) -> ChatModelConfigUnion:
    properties = {
        key: _decode_model_property(value)
        for key, value in _node_properties(config_node).items()
    }
    properties["provider"] = _chat_provider_from_labels(labels)
    properties["connection"] = _connection_from_optional_node(connection_node)
    return CHAT_CONFIG_ADAPTER.validate_python(properties)


def _embed_from_node(config_node, labels: list[str], connection_node=None) -> EmbedModelConfigUnion:
    properties = {
        key: _decode_model_property(value)
        for key, value in _node_properties(config_node).items()
    }
    properties["provider"] = _embed_provider_from_labels(labels)
    properties["connection"] = _connection_from_optional_node(connection_node)
    return EMBED_CONFIG_ADAPTER.validate_python(properties)


def _comfyui_image_from_node(config_node, connection_node=None) -> ComfyUiImageModelConfig:
    return ComfyUiImageModelConfig(
        id=config_node["id"],
        model=config_node.get("model"),
        vae=config_node.get("vae"),
        clip=config_node.get("clip"),
        image_width=config_node.get("image_width"),
        image_height=config_node.get("image_height"),
        seed=config_node.get("seed"),
        steps=config_node.get("steps"),
        cfg=config_node.get("cfg"),
        connection=_connection_from_optional_node(connection_node),
    )


def _image_from_node(config_node, labels: list[str], connection_node=None) -> ImageModelConfigUnion:
    if "ComfyUiImageModelConfig" in labels:
        return _comfyui_image_from_node(config_node, connection_node)
    raise ValueError(f"Unknown config labels {labels}")


def _image_generation_config_from_node(config_node) -> ImageGenerationConfig:
    return ImageGenerationConfig(
        id=config_node["id"],
        mode=config_node["mode"],
        fallback_turns=config_node["fallback_turns"],
    )


def _tts_generation_config_from_node(config_node) -> TtsGenerationConfig:
    return TtsGenerationConfig(
        id=config_node["id"],
        mode=config_node["mode"],
        autoplay_in_browser=config_node.get("autoplay_in_browser", False),
        narrator_voice=config_node.get("narrator_voice"),
        rvc_narrator_voice=config_node.get("rvc_narrator_voice"),
        rvc_narrator_pitch=config_node.get("rvc_narrator_pitch"),
    )


def _alltalk_common_fields_from_node(config_node, connection_node=None) -> dict:
    return {
        "id": config_node["id"],
        "name": config_node.get("name"),
        "model": config_node.get("model"),
        "text_filtering": config_node.get("text_filtering"),
        "text_not_inside": config_node.get("text_not_inside"),
        "narrator_enabled": config_node.get("narrator_enabled"),
        "output_file_timestamp": config_node.get("output_file_timestamp"),
        "autoplay": config_node.get("autoplay"),
        "autoplay_volume": config_node.get("autoplay_volume"),
        "connection": _connection_from_optional_node(connection_node),
    }


def _alltalk_xtts_from_node(config_node, connection_node=None) -> AllTalkXttsModelConfig:
    return AllTalkXttsModelConfig(
        **_alltalk_common_fields_from_node(config_node, connection_node),
        language=config_node.get("language"),
        speed=config_node.get("speed"),
        temperature=config_node.get("temperature"),
        repetition_penalty=config_node.get("repetition_penalty"),
    )


def _alltalk_piper_from_node(config_node, connection_node=None) -> AllTalkPiperModelConfig:
    return AllTalkPiperModelConfig(
        **_alltalk_common_fields_from_node(config_node, connection_node),
        speed=config_node.get("speed"),
    )


def _alltalk_vits_from_node(config_node, connection_node=None) -> AllTalkVitsModelConfig:
    return AllTalkVitsModelConfig(
        **_alltalk_common_fields_from_node(config_node, connection_node),
        language=config_node.get("language"),
        speed=config_node.get("speed"),
    )


def _alltalk_parler_from_node(config_node, connection_node=None) -> AllTalkParlerModelConfig:
    return AllTalkParlerModelConfig(
        **_alltalk_common_fields_from_node(config_node, connection_node),
        speed=config_node.get("speed"),
        temperature=config_node.get("temperature"),
    )


def _alltalk_f5tts_from_node(config_node, connection_node=None) -> AllTalkF5ttsModelConfig:
    return AllTalkF5ttsModelConfig(
        **_alltalk_common_fields_from_node(config_node, connection_node),
        language=config_node.get("language"),
        speed=config_node.get("speed"),
    )


def _tts_from_node(config_node, labels: list[str], connection_node=None) -> TtsModelConfigUnion:
    if "AllTalkXttsModelConfig" in labels:
        return _alltalk_xtts_from_node(config_node, connection_node)
    if "AllTalkPiperModelConfig" in labels:
        return _alltalk_piper_from_node(config_node, connection_node)
    if "AllTalkVitsModelConfig" in labels:
        return _alltalk_vits_from_node(config_node, connection_node)
    if "AllTalkParlerModelConfig" in labels:
        return _alltalk_parler_from_node(config_node, connection_node)
    if "AllTalkF5ttsModelConfig" in labels:
        return _alltalk_f5tts_from_node(config_node, connection_node)
    raise ValueError(f"Unknown config labels {labels}")


def _whisper_cpp_stt_from_node(config_node, connection_node=None) -> WhisperCppSttModelConfig:
    return WhisperCppSttModelConfig(
        id=config_node["id"],
        model=config_node.get("model"),
        language=config_node.get("language"),
        translate=config_node.get("translate"),
        temperature=config_node.get("temperature"),
        temperature_inc=config_node.get("temperature_inc"),
        initial_prompt=config_node.get("initial_prompt"),
        carry_initial_prompt=config_node.get("carry_initial_prompt"),
        connection=_connection_from_optional_node(connection_node),
    )


def _stt_from_node(config_node, labels: list[str], connection_node=None) -> SttModelConfigUnion:
    if "WhisperCppSttModelConfig" in labels:
        return _whisper_cpp_stt_from_node(config_node, connection_node)
    raise ValueError(f"Unknown config labels {labels}")


class ConfigStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    async def create_connection(self, connection_config: ConnectionConfig):
        result = await self._driver.execute_query(
            """
            CREATE (c:ConnectionConfig {
                id: $id,
                type: $type,
                name: $name,
                base_url: $base_url,
                api_key: $api_key
            }) RETURN c
            """,
            parameters_={
                "id": connection_config.id,
                "type": connection_config.type,
                "name": connection_config.name,
                "base_url": connection_config.base_url,
                "api_key": connection_config.api_key,
            }
        )
        return _connection_from_node(result.records[0]["c"])

    async def list_connections(self) -> list[ConnectionConfig]:
        result = await self._driver.execute_query(
            """
            MATCH (c:ConnectionConfig)
            RETURN c
            ORDER BY c.name
            """
        )

        return [
            _connection_from_node(record["c"])
            for record in result.records
        ]

    async def get_connection(self, config_id: str) -> ConnectionConfig | None:
        result = await self._driver.execute_query(
            "MATCH (c:ConnectionConfig {id: $id}) RETURN c LIMIT 1",
            parameters_={"id": config_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _connection_from_node(record["c"])

    async def get_connection_by_source(self, source_id: str) -> ConnectionConfig | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:{CHAT_CONFIG_LABELS} {{id: $source_id}})
                -[:USES]->
                (c:ConnectionConfig)
            RETURN c LIMIT 1
            """,
            parameters_={"source_id": source_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _connection_from_node(record["c"])

    async def get_connection_by_embed_source(self, source_id: str) -> ConnectionConfig | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:{EMBED_CONFIG_LABELS} {{id: $source_id}})
                -[:USES]->
                (c:ConnectionConfig)
            RETURN c LIMIT 1
            """,
            parameters_={"source_id": source_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _connection_from_node(record["c"])

    async def get_connection_by_image_source(self, source_id: str) -> ConnectionConfig | None:
        result = await self._driver.execute_query(
            """
            MATCH (s:ComfyUiImageModelConfig {id: $source_id})
                -[:USES]->
                (c:ConnectionConfig)
            RETURN c LIMIT 1
            """,
            parameters_={"source_id": source_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _connection_from_node(record["c"])

    async def get_connection_by_tts_source(self, source_id: str) -> ConnectionConfig | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:{TTS_CONFIG_LABELS} {{id: $source_id}})
                -[:USES]->
                (c:ConnectionConfig)
            RETURN c LIMIT 1
            """,
            parameters_={"source_id": source_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _connection_from_node(record["c"])

    async def get_connection_by_stt_source(self, source_id: str) -> ConnectionConfig | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:{STT_CONFIG_LABELS} {{id: $source_id}})
                -[:USES]->
                (c:ConnectionConfig)
            RETURN c LIMIT 1
            """,
            parameters_={"source_id": source_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _connection_from_node(record["c"])

    async def link_connection(self,
                              source_id: str,
                              connection_id: str,
                              ) -> ConnectionConfig | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:{CHAT_CONFIG_LABELS}|{EMBED_CONFIG_LABELS}
                |ComfyUiImageModelConfig|{TTS_CONFIG_LABELS}|{STT_CONFIG_LABELS} {{
                id: $source_id
            }})
            MATCH (c:ConnectionConfig {{id: $connection_id}})
            OPTIONAL MATCH (s)-[previous:USES]->(:ConnectionConfig)
            DELETE previous
            MERGE (s) -[:USES]-> (c)
            RETURN c LIMIT 1
            """,
            parameters_={
                "source_id": source_id,
                "connection_id": connection_id,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _connection_from_node(record["c"])

    async def unlink_connection(self, source_id: str) -> bool:
        result = await self._driver.execute_query(
            f"""
            MATCH (source:{CHAT_CONFIG_LABELS}|{EMBED_CONFIG_LABELS}
                |ComfyUiImageModelConfig|{TTS_CONFIG_LABELS}|{STT_CONFIG_LABELS} {{
                id: $source_id
            }})
            OPTIONAL MATCH (source)-[uses:USES]->(:ConnectionConfig)
            DELETE uses
            RETURN count(source) AS source_count
            """,
            parameters_={"source_id": source_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["source_count"])

    async def update_connection(self,
                                config_id: str,
                                properties: dict,
                                ) -> ConnectionConfig | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            """
            MATCH (c:ConnectionConfig {id: $config_id})
            SET c += $properties
            RETURN c LIMIT 1
            """,
            parameters_={
                "config_id": config_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _connection_from_node(record["c"])

    async def delete_connection(self, config_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (c:ConnectionConfig {id: $config_id})
            WITH collect(c) AS configs
            FOREACH (config IN configs | DETACH DELETE config)
            RETURN size(configs) AS deleted
            """,
            parameters_={"config_id": config_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def create_chat(self, chat_config: ChatModelConfigUnion):
        label = type(chat_config).__name__
        if label not in CHAT_CONFIG_PROVIDERS:
            raise TypeError(f"Expected ChatModelConfigUnion, got {type(chat_config)}")

        properties = {
            key: _encode_model_property(value)
            for key, value in chat_config.model_dump(
                exclude={"provider", "connection"},
                mode="python",
            ).items()
            if value is not None
        }

        result = await self._driver.execute_query(
            f"""
            CREATE (c:{label})
            SET c = $properties
            RETURN labels(c) AS config_labels, c AS config
            """,
            parameters_={"properties": properties},
        )

        return _chat_from_node(result.records[0]["config"], result.records[0]["config_labels"])

    async def list_chats(self) -> list[ChatModelConfigUnion]:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{CHAT_CONFIG_LABELS})
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            ORDER BY c.name
            """
        )

        return [
            _chat_from_node(record["config"], record["config_labels"], record["connection"])
            for record in result.records
        ]

    async def get_chat(self, config_id: str) -> ChatModelConfigUnion | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{CHAT_CONFIG_LABELS} {{id: $config_id}})
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={"config_id": config_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _chat_from_node(record["config"], record["config_labels"], record["connection"])

    async def get_chat_by_source(self,
                                 source_id: str,
                                 component: ComponentType,
                                 ) -> ChatModelConfigUnion | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:World|Simulation {{id: $source_id}})
                -[:USES {{component: $component}}]->
                (c:{CHAT_CONFIG_LABELS})
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={
                "source_id": source_id,
                "component": component,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _chat_from_node(record["config"], record["config_labels"], record["connection"])

    async def list_chats_by_source(self,
                                   source_id: str,
                                   ) -> dict[ComponentType, ChatModelConfigUnion]:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:World|Simulation {{id: $source_id}})
                -[uses:USES]->
                (c:{CHAT_CONFIG_LABELS})
            WHERE uses.component IS NOT NULL
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN uses.component AS component, labels(c) AS config_labels, c AS config, connection
            ORDER BY uses.component
            """,
            parameters_={"source_id": source_id},
        )

        return {
            ComponentType(record["component"]): _chat_from_node(
                record["config"],
                record["config_labels"],
                record["connection"],
            )
            for record in result.records
        }

    async def link_chat(self,
                        source_id: str,
                        config_id: str,
                        component: ComponentType,
                        ) -> ChatModelConfigUnion | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:World|Simulation {{id: $source_id}})
            MATCH (c:{CHAT_CONFIG_LABELS} {{id: $config_id}})
            OPTIONAL MATCH (s)-[previous:USES {{component: $component}}]->(
                :{CHAT_CONFIG_LABELS}
            )
            DELETE previous
            MERGE (s) -[:USES {{component: $component}}]-> (c)
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={
                "source_id": source_id,
                "config_id": config_id,
                "component": component,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _chat_from_node(record["config"], record["config_labels"], record["connection"])

    async def unlink_chat(self,
                          source_id: str,
                          component: ComponentType,
                          ) -> bool:
        result = await self._driver.execute_query(
            f"""
            MATCH (source:World|Simulation {{id: $source_id}})
            OPTIONAL MATCH (source)-[uses:USES {{component: $component}}]->(
                :{CHAT_CONFIG_LABELS}
            )
            DELETE uses
            RETURN count(source) AS source_count
            """,
            parameters_={
                "source_id": source_id,
                "component": component,
            },
        )

        record = result.records[0] if result.records else None
        return bool(record and record["source_count"])

    async def get_global_chat(self, component: ComponentType) -> ChatModelConfigUnion | None:
        """A chat config used for one component without belonging to any World or Simulation -
        e.g. the SillyTavern import pipeline, which necessarily runs before any World exists.

        Mirrors `get_global_stt`'s approach (no source/scope node - just look for a config marked
        for this purpose directly) rather than inventing a fake World-like scope node, generalized
        with a `global_components` marker property since - unlike STT, which only ever has one
        config in the whole system - a global chat config still needs to say *which* component(s)
        it is the default for. A list, not a single value, because the same config is commonly the
        global default for several components at once (e.g. every stage of one import pipeline).
        """
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{CHAT_CONFIG_LABELS})
            WHERE $component IN coalesce(c.global_components, [])
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection LIMIT 1
            """,
            parameters_={"component": component},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _chat_from_node(record["config"], record["config_labels"], record["connection"])

    async def link_global_chat(self, config_id: str, component: ComponentType) -> ChatModelConfigUnion | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{CHAT_CONFIG_LABELS} {{id: $config_id}})
            OPTIONAL MATCH (previous:{CHAT_CONFIG_LABELS})
            WHERE previous.id <> $config_id AND $component IN coalesce(previous.global_components, [])
            WITH c, collect(previous) AS previous_holders
            FOREACH (p IN previous_holders |
                SET p.global_components = [x IN p.global_components WHERE x <> $component]
            )
            SET c.global_components =
                CASE WHEN $component IN coalesce(c.global_components, [])
                    THEN c.global_components
                    ELSE coalesce(c.global_components, []) + $component
                END
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={"config_id": config_id, "component": component},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _chat_from_node(record["config"], record["config_labels"], record["connection"])

    async def unlink_global_chat(self, component: ComponentType) -> bool:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{CHAT_CONFIG_LABELS})
            WHERE $component IN coalesce(c.global_components, [])
            SET c.global_components = [x IN c.global_components WHERE x <> $component]
            RETURN count(c) AS count
            """,
            parameters_={"component": component},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["count"])

    async def update_chat(self,
                          config_id: str,
                          properties: dict,
                          ) -> ChatModelConfigUnion | None:
        properties = {
            key: _encode_model_property(value)
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            f"""
            MATCH (c:{CHAT_CONFIG_LABELS} {{id: $config_id}})
            SET c += $properties
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={
                "config_id": config_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _chat_from_node(record["config"], record["config_labels"], record["connection"])

    async def delete_chat(self, config_id: str) -> bool:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{CHAT_CONFIG_LABELS} {{id: $config_id}})
            WITH collect(c) AS configs
            FOREACH (config IN configs | DETACH DELETE config)
            RETURN size(configs) AS deleted
            """,
            parameters_={"config_id": config_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def create_embed(self, embed_config: EmbedModelConfigUnion):
        label = type(embed_config).__name__
        if label not in EMBED_CONFIG_PROVIDERS:
            raise TypeError(f"Expected EmbedModelConfigUnion, got {type(embed_config)}")

        properties = {
            key: _encode_model_property(value)
            for key, value in embed_config.model_dump(
                exclude={"provider", "connection"},
                mode="python",
            ).items()
            if value is not None
        }

        result = await self._driver.execute_query(
            f"""
            CREATE (c:{label})
            SET c = $properties
            RETURN labels(c) AS config_labels, c AS config
            """,
            parameters_={"properties": properties},
        )

        return _embed_from_node(result.records[0]["config"], result.records[0]["config_labels"])

    async def list_embeds(self) -> list[EmbedModelConfigUnion]:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{EMBED_CONFIG_LABELS})
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            ORDER BY c.model
            """
        )

        return [
            _embed_from_node(record["config"], record["config_labels"], record["connection"])
            for record in result.records
        ]

    async def get_embed(self, config_id: str) -> EmbedModelConfigUnion | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{EMBED_CONFIG_LABELS} {{id: $config_id}})
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={"config_id": config_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _embed_from_node(record["config"], record["config_labels"], record["connection"])

    async def get_embed_by_source(self,
                                  source_id: str,
                                  component: ComponentType,
                                  ) -> EmbedModelConfigUnion | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:World|Simulation {{id: $source_id}})
                -[:USES {{component: $component}}]->
                (c:{EMBED_CONFIG_LABELS})
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={
                "source_id": source_id,
                "component": component,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _embed_from_node(record["config"], record["config_labels"], record["connection"])

    async def list_embeds_by_source(self,
                                    source_id: str,
                                    ) -> dict[ComponentType, EmbedModelConfigUnion]:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:World|Simulation {{id: $source_id}})
                -[uses:USES]->
                (c:{EMBED_CONFIG_LABELS})
            WHERE uses.component IS NOT NULL
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN uses.component AS component, labels(c) AS config_labels, c AS config, connection
            ORDER BY uses.component
            """,
            parameters_={"source_id": source_id},
        )

        return {
            ComponentType(record["component"]): _embed_from_node(
                record["config"],
                record["config_labels"],
                record["connection"],
            )
            for record in result.records
        }

    async def link_embed(self,
                         source_id: str,
                         config_id: str,
                         component: ComponentType,
                         ) -> EmbedModelConfigUnion | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:World|Simulation {{id: $source_id}})
            MATCH (c:{EMBED_CONFIG_LABELS} {{id: $config_id}})
            OPTIONAL MATCH (s)-[previous:USES {{component: $component}}]->(
                :{EMBED_CONFIG_LABELS}
            )
            DELETE previous
            MERGE (s) -[:USES {{component: $component}}]-> (c)
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={
                "source_id": source_id,
                "config_id": config_id,
                "component": component,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _embed_from_node(record["config"], record["config_labels"], record["connection"])

    async def unlink_embed(self,
                           source_id: str,
                           component: ComponentType,
                           ) -> bool:
        result = await self._driver.execute_query(
            f"""
            MATCH (source:World|Simulation {{id: $source_id}})
            OPTIONAL MATCH (source)-[uses:USES {{component: $component}}]->(
                :{EMBED_CONFIG_LABELS}
            )
            DELETE uses
            RETURN count(source) AS source_count
            """,
            parameters_={
                "source_id": source_id,
                "component": component,
            },
        )

        record = result.records[0] if result.records else None
        return bool(record and record["source_count"])

    async def update_embed(self,
                           config_id: str,
                           properties: dict,
                           ) -> EmbedModelConfigUnion | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        properties = {
            key: _encode_model_property(value)
            for key, value in properties.items()
        }

        result = await self._driver.execute_query(
            f"""
            MATCH (c:{EMBED_CONFIG_LABELS} {{id: $config_id}})
            SET c += $properties
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={
                "config_id": config_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _embed_from_node(record["config"], record["config_labels"], record["connection"])

    async def delete_embed(self, config_id: str) -> bool:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{EMBED_CONFIG_LABELS} {{id: $config_id}})
            WITH collect(c) AS configs
            FOREACH (config IN configs | DETACH DELETE config)
            RETURN size(configs) AS deleted
            """,
            parameters_={"config_id": config_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def create_image(self, image_config: ImageModelConfigUnion):
        if isinstance(image_config, ComfyUiImageModelConfig):
            result = await self._driver.execute_query(
                """
                CREATE (c:ComfyUiImageModelConfig {
                    id: $id,
                    model: $model,
                    vae: $vae,
                    clip: $clip,
                    image_width: $image_width,
                    image_height: $image_height,
                    seed: $seed,
                    steps: $steps,
                    cfg: $cfg
                }) RETURN c
                """,
                parameters_={
                    "id": image_config.id,
                    "model": image_config.model,
                    "vae": image_config.vae,
                    "clip": image_config.clip,
                    "image_width": image_config.image_width,
                    "image_height": image_config.image_height,
                    "seed": image_config.seed,
                    "steps": image_config.steps,
                    "cfg": image_config.cfg,
                }
            )
            return _comfyui_image_from_node(result.records[0]["c"])
        else:
            raise TypeError(f"Expected ImageModelConfigUnion, got {type(image_config)}")

    async def list_images(self) -> list[ImageModelConfigUnion]:
        result = await self._driver.execute_query(
            """
            MATCH (c:ComfyUiImageModelConfig)
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            ORDER BY c.id
            """
        )

        return [
            _image_from_node(record["config"], record["config_labels"], record["connection"])
            for record in result.records
        ]

    async def get_image(self, config_id: str) -> ImageModelConfigUnion | None:
        result = await self._driver.execute_query(
            """
            MATCH (c:ComfyUiImageModelConfig {id: $config_id})
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={"config_id": config_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _image_from_node(record["config"], record["config_labels"], record["connection"])

    async def get_image_by_source(self,
                                  source_id: str,
                                  component: ComponentType,
                                  ) -> ImageModelConfigUnion | None:
        result = await self._driver.execute_query(
            """
            MATCH (s:World|Simulation {id: $source_id})
                -[:USES {component: $component}]->
                (c:ComfyUiImageModelConfig)
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={
                "source_id": source_id,
                "component": component,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _image_from_node(record["config"], record["config_labels"], record["connection"])

    async def list_images_by_source(self,
                                    source_id: str,
                                    ) -> dict[ComponentType, ImageModelConfigUnion]:
        result = await self._driver.execute_query(
            """
            MATCH (s:World|Simulation {id: $source_id})
                -[uses:USES]->
                (c:ComfyUiImageModelConfig)
            WHERE uses.component IS NOT NULL
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN uses.component AS component, labels(c) AS config_labels, c AS config, connection
            ORDER BY uses.component
            """,
            parameters_={"source_id": source_id},
        )

        return {
            ComponentType(record["component"]): _image_from_node(
                record["config"],
                record["config_labels"],
                record["connection"],
            )
            for record in result.records
        }

    async def link_image(self,
                         source_id: str,
                         config_id: str,
                         component: ComponentType,
                         ) -> ImageModelConfigUnion | None:
        result = await self._driver.execute_query(
            """
            MATCH (s:World|Simulation {id: $source_id})
            MATCH (c:ComfyUiImageModelConfig {id: $config_id})
            OPTIONAL MATCH (s)-[previous:USES {component: $component}]->(
                :ComfyUiImageModelConfig
            )
            DELETE previous
            MERGE (s) -[:USES {component: $component}]-> (c)
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={
                "source_id": source_id,
                "config_id": config_id,
                "component": component,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _image_from_node(record["config"], record["config_labels"], record["connection"])

    async def unlink_image(self,
                           source_id: str,
                           component: ComponentType,
                           ) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            OPTIONAL MATCH (source)-[uses:USES {component: $component}]->(
                :ComfyUiImageModelConfig
            )
            DELETE uses
            RETURN count(source) AS source_count
            """,
            parameters_={
                "source_id": source_id,
                "component": component,
            },
        )

        record = result.records[0] if result.records else None
        return bool(record and record["source_count"])

    async def update_image(self,
                           config_id: str,
                           properties: dict,
                           ) -> ImageModelConfigUnion | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            """
            MATCH (c:ComfyUiImageModelConfig {id: $config_id})
            SET c += $properties
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={
                "config_id": config_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _image_from_node(record["config"], record["config_labels"], record["connection"])

    async def delete_image(self, config_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (c:ComfyUiImageModelConfig {id: $config_id})
            WITH collect(c) AS configs
            FOREACH (config IN configs | DETACH DELETE config)
            RETURN size(configs) AS deleted
            """,
            parameters_={"config_id": config_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def get_image_generation_config(self, simulation_id: str) -> ImageGenerationConfig | None:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_IMAGE_GENERATION_CONFIG]->(c:ImageGenerationConfig)
            RETURN c
            """,
            parameters_={"simulation_id": simulation_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _image_generation_config_from_node(record["c"])

    async def set_image_generation_config(self,
                                          simulation_id: str,
                                          config: ImageGenerationConfig,
                                          ) -> ImageGenerationConfig | None:
        result = await self._driver.execute_query(
            """
            MATCH (s:Simulation {id: $simulation_id})
            MERGE (s)-[:HAS_IMAGE_GENERATION_CONFIG]->(c:ImageGenerationConfig)
            SET c.id = $id, c.mode = $mode, c.fallback_turns = $fallback_turns
            RETURN c
            """,
            parameters_={
                "simulation_id": simulation_id,
                "id": config.id,
                "mode": config.mode,
                "fallback_turns": config.fallback_turns,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _image_generation_config_from_node(record["c"])

    async def get_tts_generation_config(self, simulation_id: str) -> TtsGenerationConfig | None:
        result = await self._driver.execute_query(
            """
            MATCH (:Simulation {id: $simulation_id})-[:HAS_TTS_GENERATION_CONFIG]->(c:TtsGenerationConfig)
            RETURN c
            """,
            parameters_={"simulation_id": simulation_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _tts_generation_config_from_node(record["c"])

    async def set_tts_generation_config(self,
                                        simulation_id: str,
                                        config: TtsGenerationConfig,
                                        ) -> TtsGenerationConfig | None:
        result = await self._driver.execute_query(
            """
            MATCH (s:Simulation {id: $simulation_id})
            MERGE (s)-[:HAS_TTS_GENERATION_CONFIG]->(c:TtsGenerationConfig)
            SET c.id = $id, c.mode = $mode, c.autoplay_in_browser = $autoplay_in_browser,
                c.narrator_voice = $narrator_voice, c.rvc_narrator_voice = $rvc_narrator_voice,
                c.rvc_narrator_pitch = $rvc_narrator_pitch
            RETURN c
            """,
            parameters_={
                "simulation_id": simulation_id,
                "id": config.id,
                "mode": config.mode,
                "autoplay_in_browser": config.autoplay_in_browser,
                "narrator_voice": config.narrator_voice,
                "rvc_narrator_voice": config.rvc_narrator_voice,
                "rvc_narrator_pitch": config.rvc_narrator_pitch,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _tts_generation_config_from_node(record["c"])

    async def create_tts(self, tts_config: TtsModelConfigUnion):
        common_parameters = {
            "id": tts_config.id,
            "name": tts_config.name,
            "model": tts_config.model,
            "text_filtering": tts_config.text_filtering,
            "text_not_inside": tts_config.text_not_inside,
            "narrator_enabled": tts_config.narrator_enabled,
            "output_file_timestamp": tts_config.output_file_timestamp,
            "autoplay": tts_config.autoplay,
            "autoplay_volume": tts_config.autoplay_volume,
        }
        common_properties_cypher = """
                id: $id,
                name: $name,
                model: $model,
                text_filtering: $text_filtering,
                text_not_inside: $text_not_inside,
                narrator_enabled: $narrator_enabled,
                output_file_timestamp: $output_file_timestamp,
                autoplay: $autoplay,
                autoplay_volume: $autoplay_volume
        """

        if isinstance(tts_config, AllTalkXttsModelConfig):
            result = await self._driver.execute_query(
                f"""
                CREATE (c:AllTalkXttsModelConfig {{
                    {common_properties_cypher},
                    language: $language,
                    speed: $speed,
                    temperature: $temperature,
                    repetition_penalty: $repetition_penalty
                }}) RETURN c
                """,
                parameters_={
                    **common_parameters,
                    "language": tts_config.language,
                    "speed": tts_config.speed,
                    "temperature": tts_config.temperature,
                    "repetition_penalty": tts_config.repetition_penalty,
                }
            )
            return _alltalk_xtts_from_node(result.records[0]["c"])
        elif isinstance(tts_config, AllTalkPiperModelConfig):
            result = await self._driver.execute_query(
                f"""
                CREATE (c:AllTalkPiperModelConfig {{
                    {common_properties_cypher},
                    speed: $speed
                }}) RETURN c
                """,
                parameters_={
                    **common_parameters,
                    "speed": tts_config.speed,
                }
            )
            return _alltalk_piper_from_node(result.records[0]["c"])
        elif isinstance(tts_config, AllTalkVitsModelConfig):
            result = await self._driver.execute_query(
                f"""
                CREATE (c:AllTalkVitsModelConfig {{
                    {common_properties_cypher},
                    language: $language,
                    speed: $speed
                }}) RETURN c
                """,
                parameters_={
                    **common_parameters,
                    "language": tts_config.language,
                    "speed": tts_config.speed,
                }
            )
            return _alltalk_vits_from_node(result.records[0]["c"])
        elif isinstance(tts_config, AllTalkParlerModelConfig):
            result = await self._driver.execute_query(
                f"""
                CREATE (c:AllTalkParlerModelConfig {{
                    {common_properties_cypher},
                    speed: $speed,
                    temperature: $temperature
                }}) RETURN c
                """,
                parameters_={
                    **common_parameters,
                    "speed": tts_config.speed,
                    "temperature": tts_config.temperature,
                }
            )
            return _alltalk_parler_from_node(result.records[0]["c"])
        elif isinstance(tts_config, AllTalkF5ttsModelConfig):
            result = await self._driver.execute_query(
                f"""
                CREATE (c:AllTalkF5ttsModelConfig {{
                    {common_properties_cypher},
                    language: $language,
                    speed: $speed
                }}) RETURN c
                """,
                parameters_={
                    **common_parameters,
                    "language": tts_config.language,
                    "speed": tts_config.speed,
                }
            )
            return _alltalk_f5tts_from_node(result.records[0]["c"])
        else:
            raise TypeError(f"Expected TtsModelConfigUnion, got {type(tts_config)}")

    async def list_ttss(self) -> list[TtsModelConfigUnion]:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{TTS_CONFIG_LABELS})
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            ORDER BY c.id
            """
        )

        return [
            _tts_from_node(record["config"], record["config_labels"], record["connection"])
            for record in result.records
        ]

    async def get_tts(self, config_id: str) -> TtsModelConfigUnion | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{TTS_CONFIG_LABELS} {{id: $config_id}})
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={"config_id": config_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _tts_from_node(record["config"], record["config_labels"], record["connection"])

    async def get_tts_by_source(self,
                                source_id: str,
                                component: ComponentType,
                                ) -> TtsModelConfigUnion | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:World|Simulation {{id: $source_id}})
                -[:USES {{component: $component}}]->
                (c:{TTS_CONFIG_LABELS})
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={
                "source_id": source_id,
                "component": component,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _tts_from_node(record["config"], record["config_labels"], record["connection"])

    async def list_ttss_by_source(self,
                                  source_id: str,
                                  ) -> dict[ComponentType, TtsModelConfigUnion]:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:World|Simulation {{id: $source_id}})
                -[uses:USES]->
                (c:{TTS_CONFIG_LABELS})
            WHERE uses.component IS NOT NULL
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN uses.component AS component, labels(c) AS config_labels, c AS config, connection
            ORDER BY uses.component
            """,
            parameters_={"source_id": source_id},
        )

        return {
            ComponentType(record["component"]): _tts_from_node(
                record["config"],
                record["config_labels"],
                record["connection"],
            )
            for record in result.records
        }

    async def link_tts(self,
                       source_id: str,
                       config_id: str,
                       component: ComponentType,
                       ) -> TtsModelConfigUnion | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (s:World|Simulation {{id: $source_id}})
            MATCH (c:{TTS_CONFIG_LABELS} {{id: $config_id}})
            OPTIONAL MATCH (s)-[previous:USES {{component: $component}}]->(:{TTS_CONFIG_LABELS})
            DELETE previous
            MERGE (s) -[:USES {{component: $component}}]-> (c)
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={
                "source_id": source_id,
                "config_id": config_id,
                "component": component,
            }
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _tts_from_node(record["config"], record["config_labels"], record["connection"])

    async def unlink_tts(self,
                         source_id: str,
                         component: ComponentType,
                         ) -> bool:
        result = await self._driver.execute_query(
            f"""
            MATCH (source:World|Simulation {{id: $source_id}})
            OPTIONAL MATCH (source)-[uses:USES {{component: $component}}]->(:{TTS_CONFIG_LABELS})
            DELETE uses
            RETURN count(source) AS source_count
            """,
            parameters_={
                "source_id": source_id,
                "component": component,
            },
        )

        record = result.records[0] if result.records else None
        return bool(record and record["source_count"])

    async def update_tts(self,
                         config_id: str,
                         properties: dict,
                         ) -> TtsModelConfigUnion | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            f"""
            MATCH (c:{TTS_CONFIG_LABELS} {{id: $config_id}})
            SET c += $properties
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={
                "config_id": config_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _tts_from_node(record["config"], record["config_labels"], record["connection"])

    async def delete_tts(self, config_id: str) -> bool:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{TTS_CONFIG_LABELS} {{id: $config_id}})
            WITH collect(c) AS configs
            FOREACH (config IN configs | DETACH DELETE config)
            RETURN size(configs) AS deleted
            """,
            parameters_={"config_id": config_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def create_stt(self, stt_config: SttModelConfigUnion):
        if isinstance(stt_config, WhisperCppSttModelConfig):
            result = await self._driver.execute_query(
                """
                CREATE (c:WhisperCppSttModelConfig {
                    id: $id,
                    model: $model,
                    language: $language,
                    translate: $translate,
                    temperature: $temperature,
                    temperature_inc: $temperature_inc,
                    initial_prompt: $initial_prompt,
                    carry_initial_prompt: $carry_initial_prompt
                }) RETURN c
                """,
                parameters_={
                    "id": stt_config.id,
                    "model": stt_config.model,
                    "language": stt_config.language,
                    "translate": stt_config.translate,
                    "temperature": stt_config.temperature,
                    "temperature_inc": stt_config.temperature_inc,
                    "initial_prompt": stt_config.initial_prompt,
                    "carry_initial_prompt": stt_config.carry_initial_prompt,
                }
            )
            return _whisper_cpp_stt_from_node(result.records[0]["c"])
        else:
            raise TypeError(f"Expected SttModelConfigUnion, got {type(stt_config)}")

    async def list_stts(self) -> list[SttModelConfigUnion]:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{STT_CONFIG_LABELS})
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            ORDER BY c.id
            """
        )

        return [
            _stt_from_node(record["config"], record["config_labels"], record["connection"])
            for record in result.records
        ]

    async def get_global_stt(self) -> SttModelConfigUnion | None:
        """STT is not per-simulation/world like chat/embed/image/TTS - there is a single shared
        backend, so this returns the only STT config expected to exist rather than looking one up
        by source/component."""
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{STT_CONFIG_LABELS})
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            ORDER BY c.id LIMIT 1
            """
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _stt_from_node(record["config"], record["config_labels"], record["connection"])

    async def get_stt(self, config_id: str) -> SttModelConfigUnion | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{STT_CONFIG_LABELS} {{id: $config_id}})
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={"config_id": config_id}
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _stt_from_node(record["config"], record["config_labels"], record["connection"])

    async def update_stt(self,
                         config_id: str,
                         properties: dict,
                         ) -> SttModelConfigUnion | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            f"""
            MATCH (c:{STT_CONFIG_LABELS} {{id: $config_id}})
            SET c += $properties
            OPTIONAL MATCH (c)-[:USES]->(connection:ConnectionConfig)
            RETURN labels(c) AS config_labels, c AS config, connection
            """,
            parameters_={
                "config_id": config_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _stt_from_node(record["config"], record["config_labels"], record["connection"])

    async def get_image_url_whitelist(self) -> list[str]:
        """Base URL prefixes the SillyTavern import pipeline trusts enough to auto-download an
        image link from without asking the user first (see `MediaDownloadService`/`ImageExtractor`).
        Global, not per-simulation/world - a singleton node, since there's nothing to scope it to."""
        result = await self._driver.execute_query(
            "MATCH (c:SillyTavernImageUrlWhitelist {id: 'singleton'}) RETURN c.base_urls AS base_urls"
        )

        record = result.records[0] if result.records else None
        return list(record["base_urls"]) if record and record["base_urls"] else []

    async def set_image_url_whitelist(self, base_urls: list[str]) -> list[str]:
        result = await self._driver.execute_query(
            """
            MERGE (c:SillyTavernImageUrlWhitelist {id: 'singleton'})
            SET c.base_urls = $base_urls
            RETURN c.base_urls AS base_urls
            """,
            parameters_={"base_urls": base_urls},
        )

        record = result.records[0] if result.records else None
        return list(record["base_urls"]) if record and record["base_urls"] else []

    async def delete_stt(self, config_id: str) -> bool:
        result = await self._driver.execute_query(
            f"""
            MATCH (c:{STT_CONFIG_LABELS} {{id: $config_id}})
            WITH collect(c) AS configs
            FOREACH (config IN configs | DETACH DELETE config)
            RETURN size(configs) AS deleted
            """,
            parameters_={"config_id": config_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])
