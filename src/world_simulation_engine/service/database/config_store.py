from neo4j import AsyncDriver

from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import ConnectionConfig, ChatModelConfigUnion, OllamaChatModelConfig, \
    OpenAiChatModelConfig, EmbedModelConfigUnion, OllamaEmbedModelConfig, OpenAiEmbedModelConfig


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


def _ollama_chat_from_node(config_node, connection_node=None) -> OllamaChatModelConfig:
    return OllamaChatModelConfig(
        id=config_node["id"],
        name=config_node["name"],
        model=config_node["model"],
        temperature=config_node["temperature"],
        context_window=config_node["context_window"],
        seed=config_node.get("seed"),
        reasoning=config_node.get("reasoning"),
        stop_tokens=config_node.get("stop_tokens"),
        mirostat=config_node.get("mirostat"),
        mirostat_eta=config_node.get("mirostat_eta"),
        mirostat_tau=config_node.get("mirostat_tau"),
        num_predict=config_node.get("num_predict"),
        repeat_penalty_window=config_node.get("repeat_penalty_window"),
        repeat_penalty=config_node.get("repeat_penalty"),
        connection=_connection_from_optional_node(connection_node),
    )


def _openai_chat_from_node(config_node, connection_node=None) -> OpenAiChatModelConfig:
    return OpenAiChatModelConfig(
        id=config_node["id"],
        name=config_node["name"],
        model=config_node["model"],
        temperature=config_node["temperature"],
        context_window=config_node["context_window"],
        seed=config_node.get("seed"),
        reasoning=config_node.get("reasoning"),
        stop_tokens=config_node.get("stop_tokens"),
        connection=_connection_from_optional_node(connection_node),
    )


def _chat_from_node(config_node, labels: list[str], connection_node=None) -> ChatModelConfigUnion:
    if "OllamaChatModelConfig" in labels:
        return _ollama_chat_from_node(config_node, connection_node)
    if "OpenAiChatModelConfig" in labels:
        return _openai_chat_from_node(config_node, connection_node)
    raise ValueError(f"Unknown config labels {labels}")


def _ollama_embed_from_node(config_node, connection_node=None) -> OllamaEmbedModelConfig:
    return OllamaEmbedModelConfig(
        id=config_node["id"],
        model=config_node["model"],
        dimension=config_node.get("dimension"),
        context_window=config_node.get("context_window"),
        connection=_connection_from_optional_node(connection_node),
    )


def _openai_embed_from_node(config_node, connection_node=None) -> OpenAiEmbedModelConfig:
    return OpenAiEmbedModelConfig(
        id=config_node["id"],
        model=config_node["model"],
        dimension=config_node.get("dimension"),
        connection=_connection_from_optional_node(connection_node),
    )


def _embed_from_node(config_node, labels: list[str], connection_node=None) -> EmbedModelConfigUnion:
    if "OllamaEmbedModelConfig" in labels:
        return _ollama_embed_from_node(config_node, connection_node)
    if "OpenAiEmbedModelConfig" in labels:
        return _openai_embed_from_node(config_node, connection_node)
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
            """
            MATCH (s:OllamaChatModelConfig|OpenAiChatModelConfig {id: $source_id})
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
            """
            MATCH (s:OllamaEmbedModelConfig|OpenAiEmbedModelConfig {id: $source_id})
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
            """
            MATCH (s:OllamaChatModelConfig|OpenAiChatModelConfig|OllamaEmbedModelConfig|OpenAiEmbedModelConfig {
                id: $source_id
            })
            MATCH (c:ConnectionConfig {id: $connection_id})
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
            """
            MATCH (source:OllamaChatModelConfig|OpenAiChatModelConfig|OllamaEmbedModelConfig|OpenAiEmbedModelConfig {
                id: $source_id
            })
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
        if isinstance(chat_config, OllamaChatModelConfig):
            result = await self._driver.execute_query(
                """
                CREATE (c:OllamaChatModelConfig {
                    id: $id,
                    name: $name,
                    model: $model,
                    temperature: $temperature,
                    context_window: $context_window,
                    seed: $seed,
                    reasoning: $reasoning,
                    stop_tokens: $stop_tokens,
                    mirostat: $mirostat,
                    mirostat_eta: $mirostat_eta,
                    mirostat_tau: $mirostat_tau,
                    num_predict: $num_predict,
                    repeat_penalty_window: $repeat_penalty_window,
                    repeat_penalty: $repeat_penalty
                }) RETURN c
                """,
                parameters_={
                    "id": chat_config.id,
                    "name": chat_config.name,
                    "model": chat_config.model,
                    "temperature": chat_config.temperature,
                    "context_window": chat_config.context_window,
                    "seed": chat_config.seed,
                    "reasoning": chat_config.reasoning,
                    "stop_tokens": chat_config.stop_tokens,
                    "mirostat": chat_config.mirostat,
                    "mirostat_eta": chat_config.mirostat_eta,
                    "mirostat_tau": chat_config.mirostat_tau,
                    "num_predict": chat_config.num_predict,
                    "repeat_penalty_window": chat_config.repeat_penalty_window,
                    "repeat_penalty": chat_config.repeat_penalty,
                }
            )
            return _ollama_chat_from_node(result.records[0]["c"])
        elif isinstance(chat_config, OpenAiChatModelConfig):
            result = await self._driver.execute_query(
                """
                CREATE (c:OpenAiChatModelConfig {
                    id: $id,
                    name: $name,
                    model: $model,
                    temperature: $temperature,
                    context_window: $context_window,
                    seed: $seed,
                    reasoning: $reasoning,
                    stop_tokens: $stop_tokens
                }) RETURN c
                """,
                parameters_={
                    "id": chat_config.id,
                    "name": chat_config.name,
                    "model": chat_config.model,
                    "temperature": chat_config.temperature,
                    "context_window": chat_config.context_window,
                    "seed": chat_config.seed,
                    "reasoning": chat_config.reasoning,
                    "stop_tokens": chat_config.stop_tokens,
                }
            )
            return _openai_chat_from_node(result.records[0]["c"])
        else:
            raise TypeError(f"Expected ChatModelConfigUnion, got {type(chat_config)}")

    async def list_chats(self) -> list[ChatModelConfigUnion]:
        result = await self._driver.execute_query(
            """
            MATCH (c:OllamaChatModelConfig|OpenAiChatModelConfig)
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
            """
            MATCH (c:OllamaChatModelConfig|OpenAiChatModelConfig {id: $config_id})
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
            """
            MATCH (s:World|Simulation {id: $source_id})
                -[:USES {component: $component}]->
                (c:OllamaChatModelConfig|OpenAiChatModelConfig)
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
            """
            MATCH (s:World|Simulation {id: $source_id})
                -[uses:USES]->
                (c:OllamaChatModelConfig|OpenAiChatModelConfig)
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
            """
            MATCH (s:World|Simulation {id: $source_id})
            MATCH (c:OllamaChatModelConfig|OpenAiChatModelConfig {id: $config_id})
            OPTIONAL MATCH (s)-[previous:USES {component: $component}]->(
                :OllamaChatModelConfig|OpenAiChatModelConfig
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

        return _chat_from_node(record["config"], record["config_labels"], record["connection"])

    async def unlink_chat(self,
                          source_id: str,
                          component: ComponentType,
                          ) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            OPTIONAL MATCH (source)-[uses:USES {component: $component}]->(
                :OllamaChatModelConfig|OpenAiChatModelConfig
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

    async def update_chat(self,
                          config_id: str,
                          properties: dict,
                          ) -> ChatModelConfigUnion | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            """
            MATCH (c:OllamaChatModelConfig|OpenAiChatModelConfig {id: $config_id})
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
            """
            MATCH (c:OllamaChatModelConfig|OpenAiChatModelConfig {id: $config_id})
            WITH collect(c) AS configs
            FOREACH (config IN configs | DETACH DELETE config)
            RETURN size(configs) AS deleted
            """,
            parameters_={"config_id": config_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])

    async def create_embed(self, embed_config: EmbedModelConfigUnion):
        if isinstance(embed_config, OllamaEmbedModelConfig):
            result = await self._driver.execute_query(
                """
                CREATE (c:OllamaEmbedModelConfig {
                    id: $id,
                    model: $model,
                    dimension: $dimension,
                    context_window: $context_window
                }) RETURN c
                """,
                parameters_={
                    "id": embed_config.id,
                    "model": embed_config.model,
                    "dimension": embed_config.dimension,
                    "context_window": embed_config.context_window,
                }
            )
            return _ollama_embed_from_node(result.records[0]["c"])
        elif isinstance(embed_config, OpenAiEmbedModelConfig):
            result = await self._driver.execute_query(
                """
                CREATE (c:OpenAiEmbedModelConfig {
                    id: $id,
                    model: $model,
                    dimension: $dimension
                }) RETURN c
                """,
                parameters_={
                    "id": embed_config.id,
                    "model": embed_config.model,
                    "dimension": embed_config.dimension,
                }
            )
            return _openai_embed_from_node(result.records[0]["c"])
        else:
            raise TypeError(f"Expected EmbedModelConfigUnion, got {type(embed_config)}")

    async def list_embeds(self) -> list[EmbedModelConfigUnion]:
        result = await self._driver.execute_query(
            """
            MATCH (c:OllamaEmbedModelConfig|OpenAiEmbedModelConfig)
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
            """
            MATCH (c:OllamaEmbedModelConfig|OpenAiEmbedModelConfig {id: $config_id})
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
            """
            MATCH (s:World|Simulation {id: $source_id})
                -[:USES {component: $component}]->
                (c:OllamaEmbedModelConfig|OpenAiEmbedModelConfig)
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
            """
            MATCH (s:World|Simulation {id: $source_id})
                -[uses:USES]->
                (c:OllamaEmbedModelConfig|OpenAiEmbedModelConfig)
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
            """
            MATCH (s:World|Simulation {id: $source_id})
            MATCH (c:OllamaEmbedModelConfig|OpenAiEmbedModelConfig {id: $config_id})
            OPTIONAL MATCH (s)-[previous:USES {component: $component}]->(
                :OllamaEmbedModelConfig|OpenAiEmbedModelConfig
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

        return _embed_from_node(record["config"], record["config_labels"], record["connection"])

    async def unlink_embed(self,
                           source_id: str,
                           component: ComponentType,
                           ) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation {id: $source_id})
            OPTIONAL MATCH (source)-[uses:USES {component: $component}]->(
                :OllamaEmbedModelConfig|OpenAiEmbedModelConfig
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

        result = await self._driver.execute_query(
            """
            MATCH (c:OllamaEmbedModelConfig|OpenAiEmbedModelConfig {id: $config_id})
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
            """
            MATCH (c:OllamaEmbedModelConfig|OpenAiEmbedModelConfig {id: $config_id})
            WITH collect(c) AS configs
            FOREACH (config IN configs | DETACH DELETE config)
            RETURN size(configs) AS deleted
            """,
            parameters_={"config_id": config_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])
