from neo4j import AsyncDriver

from world_simulation_engine.model import CharacterTtsConfig

from .config_store import TTS_CONFIG_LABELS, _tts_from_node


def _character_tts_config_from_node(
        config_node, backend_labels=None, backend_node=None, connection_node=None,
) -> CharacterTtsConfig:
    return CharacterTtsConfig(
        id=config_node["id"],
        character_voice=config_node.get("character_voice"),
        rvc_character_voice=config_node.get("rvc_character_voice"),
        rvc_character_pitch=config_node.get("rvc_character_pitch"),
        backend=_tts_from_node(backend_node, backend_labels, connection_node) if backend_node else None,
    )


class CharacterTtsConfigStore:
    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    async def get_character_tts_config(self, character_id: str) -> CharacterTtsConfig | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (:Character {{id: $character_id}})-[:HAS_CONFIG]->(c:CharacterTtsConfig)
            OPTIONAL MATCH (c)-[:USE_CONFIG]->(backend:{TTS_CONFIG_LABELS})
            OPTIONAL MATCH (backend)-[:USES]->(connection:ConnectionConfig)
            RETURN c, labels(backend) AS backend_labels, backend, connection
            """,
            parameters_={"character_id": character_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _character_tts_config_from_node(
            record["c"], record["backend_labels"], record["backend"], record["connection"],
        )

    async def set_character_tts_config(self,
                                       character_id: str,
                                       config: CharacterTtsConfig,
                                       ) -> CharacterTtsConfig | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (character:Character {{id: $character_id}})
            MERGE (character)-[:HAS_CONFIG]->(c:CharacterTtsConfig)
            SET c.id = $id,
                c.character_voice = $character_voice,
                c.rvc_character_voice = $rvc_character_voice,
                c.rvc_character_pitch = $rvc_character_pitch
            WITH c
            OPTIONAL MATCH (c)-[:USE_CONFIG]->(backend:{TTS_CONFIG_LABELS})
            OPTIONAL MATCH (backend)-[:USES]->(connection:ConnectionConfig)
            RETURN c, labels(backend) AS backend_labels, backend, connection
            """,
            parameters_={
                "character_id": character_id,
                "id": config.id,
                "character_voice": config.character_voice,
                "rvc_character_voice": config.rvc_character_voice,
                "rvc_character_pitch": config.rvc_character_pitch,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _character_tts_config_from_node(
            record["c"], record["backend_labels"], record["backend"], record["connection"],
        )

    async def link_character_tts_backend(self,
                                         character_id: str,
                                         backend_config_id: str,
                                         ) -> CharacterTtsConfig | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (:Character {{id: $character_id}})-[:HAS_CONFIG]->(c:CharacterTtsConfig)
            MATCH (backend:{TTS_CONFIG_LABELS} {{id: $backend_config_id}})
            OPTIONAL MATCH (c)-[previous:USE_CONFIG]->(:{TTS_CONFIG_LABELS})
            DELETE previous
            MERGE (c)-[:USE_CONFIG]->(backend)
            OPTIONAL MATCH (backend)-[:USES]->(connection:ConnectionConfig)
            RETURN c, labels(backend) AS backend_labels, backend, connection
            """,
            parameters_={
                "character_id": character_id,
                "backend_config_id": backend_config_id,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _character_tts_config_from_node(
            record["c"], record["backend_labels"], record["backend"], record["connection"],
        )

    async def unlink_character_tts_backend(self, character_id: str) -> bool:
        result = await self._driver.execute_query(
            f"""
            MATCH (:Character {{id: $character_id}})-[:HAS_CONFIG]->(c:CharacterTtsConfig)
            OPTIONAL MATCH (c)-[uses:USE_CONFIG]->(:{TTS_CONFIG_LABELS})
            DELETE uses
            RETURN count(c) AS config_count
            """,
            parameters_={"character_id": character_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["config_count"])

    async def delete_character_tts_config(self, character_id: str) -> bool:
        result = await self._driver.execute_query(
            """
            MATCH (:Character {id: $character_id})-[:HAS_CONFIG]->(c:CharacterTtsConfig)
            WITH collect(c) AS configs
            FOREACH (config IN configs | DETACH DELETE config)
            RETURN size(configs) AS deleted
            """,
            parameters_={"character_id": character_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["deleted"])
