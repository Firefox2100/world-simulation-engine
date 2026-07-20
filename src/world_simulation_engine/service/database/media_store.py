from neo4j import AsyncDriver

from world_simulation_engine.misc.enums import ComponentType, MediaType, SupportedLanguage
from world_simulation_engine.model import MediaFile, PromptMediaFile


def _media_from_node(media_node) -> MediaFile:
    data = {
        "id": media_node["id"],
        "type": media_node["type"],
        "title": media_node.get("title"),
        "hash": media_node["hash"],
        "filename": media_node["filename"],
    }
    if media_node.get("prompt_name") is not None:
        return PromptMediaFile(
            **data,
            prompt_name=media_node["prompt_name"],
            language=media_node["language"],
            component=media_node.get("component"),
        )

    return MediaFile(**data)


class MediaStore:
    _COVER_SOURCE_LABELS = "World|Simulation|Character|BackgroundCharacter|Location|Landmark|Item|ItemStack|Equipment|Container"
    _MEDIA_SOURCE_LABELS = "World|Simulation|Character|BackgroundCharacter|Location|Landmark|Item|ItemStack|Equipment|Container"
    _PROMPT_SOURCE_LABELS = "World|Simulation"

    def __init__(self,
                 driver: AsyncDriver,
                 ):
        self._driver = driver

    async def create_media(self, media: MediaFile) -> MediaFile:
        result = await self._driver.execute_query(
            """
            CREATE (m:Media {
                id: $id,
                type: $type,
                title: $title,
                hash: $hash,
                filename: $filename,
                prompt_name: $prompt_name,
                language: $language,
                component: $component
            })
            RETURN m
            """,
            parameters_={
                "id": media.id,
                "type": media.type,
                "title": media.title,
                "hash": media.hash,
                "filename": media.filename,
                "prompt_name": getattr(media, "prompt_name", None),
                "language": getattr(media, "language", None),
                "component": getattr(media, "component", None),
            },
        )

        return _media_from_node(result.records[0]["m"])

    async def get_media(self, media_id: str) -> MediaFile | None:
        result = await self._driver.execute_query(
            "MATCH (m:Media {id: $id}) RETURN m LIMIT 1",
            parameters_={"id": media_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _media_from_node(record["m"])

    async def list_media(self,
                         world_id: str | None = None,
                         simulation_id: str | None = None,
                         media_type: str | None = None,
                         limit: int | None = None,
                         skip: int = 0,
                         ) -> list[MediaFile]:
        pagination = """
            SKIP $skip
        """
        if limit is not None:
            pagination += """
            LIMIT $limit
            """

        if world_id is not None and simulation_id is not None:
            source_match = """
            MATCH (:World {id: $world_id})<-[:BASED_ON]-(root:Simulation {id: $simulation_id})
            MATCH (root)-[:CONTAINS|HOLDS|PART_OF*0..]->(source)
            MATCH (source)-[:HAS_MEDIA]->(media:Media)
            """
        elif world_id is not None:
            source_match = """
            MATCH (root:World {id: $world_id})
            MATCH (root)-[:CONTAINS|HOLDS|PART_OF*0..]->(source)
            MATCH (source)-[:HAS_MEDIA]->(media:Media)
            """
        elif simulation_id is not None:
            source_match = """
            MATCH (root:Simulation {id: $simulation_id})
            MATCH (root)-[:CONTAINS|HOLDS|PART_OF*0..]->(source)
            MATCH (source)-[:HAS_MEDIA]->(media:Media)
            """
        else:
            source_match = """
            MATCH (media:Media)
            """

        result = await self._driver.execute_query(
            source_match + """
            WHERE $media_type IS NULL OR media.type = $media_type
            RETURN DISTINCT media
            ORDER BY media.filename, media.id
            """ + pagination,
            parameters_={
                "world_id": world_id,
                "simulation_id": simulation_id,
                "media_type": media_type,
                "limit": limit,
                "skip": skip,
            },
        )

        return [
            _media_from_node(record["media"])
            for record in result.records
        ]

    async def set_cover_image(self,
                              source_id: str,
                              media_id: str,
                              ) -> MediaFile | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (source:{self._COVER_SOURCE_LABELS} {{id: $source_id}})
            MATCH (media:Media {{id: $media_id}})
            OPTIONAL MATCH (source)-[previous:HAS_COVER]->(:Media)
            DELETE previous
            MERGE (source)-[:HAS_MEDIA]->(media)
            MERGE (source)-[:HAS_COVER]->(media)
            RETURN media LIMIT 1
            """,
            parameters_={
                "source_id": source_id,
                "media_id": media_id,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _media_from_node(record["media"])

    async def get_cover_image(self, source_id: str) -> MediaFile | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (:{self._COVER_SOURCE_LABELS} {{id: $source_id}})-[:HAS_COVER]->(media:Media)
            RETURN media LIMIT 1
            """,
            parameters_={"source_id": source_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _media_from_node(record["media"])

    async def remove_cover_image(self, source_id: str) -> bool:
        result = await self._driver.execute_query(
            f"""
            MATCH (source:{self._COVER_SOURCE_LABELS} {{id: $source_id}})
            OPTIONAL MATCH (source)-[cover:HAS_COVER]->(:Media)
            DELETE cover
            RETURN count(source) AS source_count
            """,
            parameters_={"source_id": source_id},
        )

        record = result.records[0] if result.records else None
        return bool(record and record["source_count"])

    async def add_media(self,
                        source_id: str,
                        media_id: str,
                        ) -> MediaFile | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (source:{self._MEDIA_SOURCE_LABELS} {{id: $source_id}})
            MATCH (media:Media {{id: $media_id}})
            MERGE (source)-[:HAS_MEDIA]->(media)
            RETURN media LIMIT 1
            """,
            parameters_={
                "source_id": source_id,
                "media_id": media_id,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _media_from_node(record["media"])

    async def list_source_media(self,
                                source_id: str,
                                media_type: str | None = None,
                                ) -> list[MediaFile]:
        result = await self._driver.execute_query(
            f"""
            MATCH (source:{self._MEDIA_SOURCE_LABELS} {{id: $source_id}})
            MATCH (source)-[:HAS_MEDIA]->(media:Media)
            WHERE $media_type IS NULL OR media.type = $media_type
            RETURN DISTINCT media
            ORDER BY media.filename, media.id
            """,
            parameters_={
                "source_id": source_id,
                "media_type": media_type,
            },
        )

        return [
            _media_from_node(record["media"])
            for record in result.records
        ]

    async def remove_media(self,
                           source_id: str,
                           media_id: str,
                           ) -> bool:
        result = await self._driver.execute_query(
            f"""
            MATCH (source:{self._MEDIA_SOURCE_LABELS} {{id: $source_id}})
            OPTIONAL MATCH (source)-[media:HAS_MEDIA]->(:Media {{id: $media_id}})
            OPTIONAL MATCH (source)-[cover:HAS_COVER]->(:Media {{id: $media_id}})
            DELETE media, cover
            RETURN count(source) AS source_count
            """,
            parameters_={
                "source_id": source_id,
                "media_id": media_id,
            },
        )

        record = result.records[0] if result.records else None
        return bool(record and record["source_count"])

    async def list_prompt_media(self,
                                world_id: str | None = None,
                                simulation_id: str | None = None,
                                language: SupportedLanguage | None = None,
                                component: ComponentType | None = None,
                                prompt_name: str | None = None,
                                ) -> list[PromptMediaFile]:
        if world_id is not None and simulation_id is not None:
            prompt_match = """
            MATCH (:World {id: $world_id})<-[:BASED_ON]-(source:Simulation {id: $simulation_id})
            MATCH (source)-[:USE_PROMPT]->(media:Media)
            """
        elif world_id is not None:
            prompt_match = """
            MATCH (source:World {id: $world_id})
            MATCH (source)-[:USE_PROMPT]->(media:Media)
            """
        elif simulation_id is not None:
            prompt_match = """
            MATCH (source:Simulation {id: $simulation_id})
            MATCH (source)-[:USE_PROMPT]->(media:Media)
            """
        else:
            prompt_match = """
            MATCH (media:Media)
            """

        result = await self._driver.execute_query(
            prompt_match + """
            WHERE media.type = $media_type
                AND media.prompt_name IS NOT NULL
                AND ($language IS NULL OR media.language = $language)
                AND ($component IS NULL OR media.component = $component)
                AND ($prompt_name IS NULL OR media.prompt_name = $prompt_name)
            RETURN DISTINCT media
            ORDER BY media.language, media.prompt_name, media.id
            """,
            parameters_={
                "world_id": world_id,
                "simulation_id": simulation_id,
                "language": language,
                "component": component,
                "prompt_name": prompt_name,
                "media_type": MediaType.JSON,
            },
        )

        return [
            PromptMediaFile.model_validate(_media_from_node(record["media"]))
            for record in result.records
        ]

    async def get_prompt_media(self,
                               simulation_id: str,
                               language: SupportedLanguage,
                               prompt_name: str,
                               ) -> PromptMediaFile | None:
        result = await self._driver.execute_query(
            """
            MATCH (simulation:Simulation {id: $simulation_id})
            OPTIONAL MATCH (simulation)-[:USE_PROMPT]->(simulation_media:Media {
                type: $media_type,
                language: $language,
                prompt_name: $prompt_name
            })
            OPTIONAL MATCH (simulation)-[:BASED_ON]->(:World)-[:USE_PROMPT]->(world_media:Media {
                type: $media_type,
                language: $language,
                prompt_name: $prompt_name
            })
            RETURN coalesce(simulation_media, world_media) AS media LIMIT 1
            """,
            parameters_={
                "simulation_id": simulation_id,
                "language": language,
                "prompt_name": prompt_name,
                "media_type": MediaType.JSON,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return PromptMediaFile.model_validate(_media_from_node(record["media"]))

    async def get_source_prompt_media(self,
                                      source_id: str,
                                      language: SupportedLanguage,
                                      prompt_name: str,
                                      component: ComponentType | None = None,
                                      ) -> PromptMediaFile | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (source:{self._PROMPT_SOURCE_LABELS} {{id: $source_id}})
            MATCH (source)-[:USE_PROMPT]->(media:Media {{
                type: $media_type,
                language: $language,
                prompt_name: $prompt_name
            }})
            WHERE $component IS NULL OR media.component = $component
            RETURN media LIMIT 1
            """,
            parameters_={
                "source_id": source_id,
                "language": language,
                "prompt_name": prompt_name,
                "component": component,
                "media_type": MediaType.JSON,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return PromptMediaFile.model_validate(_media_from_node(record["media"]))

    async def set_prompt_media(self,
                               source_id: str,
                               media_id: str,
                               ) -> tuple[PromptMediaFile, PromptMediaFile | None] | None:
        result = await self._driver.execute_query(
            f"""
            MATCH (source:{self._PROMPT_SOURCE_LABELS} {{id: $source_id}})
            MATCH (media:Media {{id: $media_id}})
            WHERE media.type = $media_type
                AND media.prompt_name IS NOT NULL
                AND media.language IS NOT NULL
            OPTIONAL MATCH (source)-[previous:USE_PROMPT]->(old:Media)
            WHERE old.type = $media_type
                AND old.language = media.language
                AND old.prompt_name = media.prompt_name
                AND coalesce(old.component, "") = coalesce(media.component, "")
            DELETE previous
            MERGE (source)-[:USE_PROMPT]->(media)
            RETURN media, old LIMIT 1
            """,
            parameters_={
                "source_id": source_id,
                "media_id": media_id,
                "media_type": MediaType.JSON,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        old = record["old"]
        return (
            PromptMediaFile.model_validate(_media_from_node(record["media"])),
            PromptMediaFile.model_validate(_media_from_node(old)) if old else None,
        )

    async def copy_prompt_media_relationships(self,
                                              world_id: str,
                                              simulation_id: str,
                                              ) -> list[PromptMediaFile]:
        result = await self._driver.execute_query(
            """
            MATCH (world:World {id: $world_id})<-[:BASED_ON]-(simulation:Simulation {id: $simulation_id})
            MATCH (world)-[:USE_PROMPT]->(media:Media)
            MERGE (simulation)-[:USE_PROMPT]->(media)
            RETURN DISTINCT media
            ORDER BY media.language, media.prompt_name, media.id
            """,
            parameters_={
                "world_id": world_id,
                "simulation_id": simulation_id,
            },
        )

        return [
            PromptMediaFile.model_validate(_media_from_node(record["media"]))
            for record in result.records
        ]

    async def remove_prompt_media(self,
                                  source_id: str,
                                  language: SupportedLanguage,
                                  prompt_name: str,
                                  component: ComponentType | None = None,
                                  delete_media: bool = True,
                                  ) -> tuple[PromptMediaFile, int] | None:
        if delete_media:
            delete_clause = """
            OPTIONAL MATCH (other:Media {hash: hash})
            WHERE other.id <> media.id
            WITH media, media_properties, count(other) AS remaining_hash_references
            DETACH DELETE media
            RETURN media_properties, remaining_hash_references
            """
        else:
            delete_clause = """
            WITH media_properties
            RETURN media_properties, 1 AS remaining_hash_references
            """

        result = await self._driver.execute_query(
            f"""
            MATCH (source:{self._PROMPT_SOURCE_LABELS} {{id: $source_id}})-[prompt:USE_PROMPT]->(media:Media {{
                type: $media_type,
                language: $language,
                prompt_name: $prompt_name
            }})
            WHERE $component IS NULL OR media.component = $component
            DELETE prompt
            WITH media, properties(media) AS media_properties, media.hash AS hash
            {delete_clause}
            """,
            parameters_={
                "source_id": source_id,
                "language": language,
                "prompt_name": prompt_name,
                "component": component,
                "media_type": MediaType.JSON,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return (
            PromptMediaFile.model_validate(_media_from_node(record["media_properties"])),
            record["remaining_hash_references"],
        )

    async def update_media(self,
                           media_id: str,
                           properties: dict,
                           ) -> MediaFile | None:
        properties = {
            key: value
            for key, value in properties.items()
            if value is not None
        }

        result = await self._driver.execute_query(
            """
            MATCH (media:Media {id: $media_id})
            SET media += $properties
            RETURN media LIMIT 1
            """,
            parameters_={
                "media_id": media_id,
                "properties": properties,
            },
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return _media_from_node(record["media"])

    async def delete_media(self, media_id: str) -> tuple[MediaFile, int] | None:
        result = await self._driver.execute_query(
            """
            MATCH (media:Media {id: $media_id})
            WITH media, properties(media) AS media_properties, media.hash AS hash
            OPTIONAL MATCH (other:Media {hash: hash})
            WHERE other.id <> media.id
            WITH media, media_properties, count(other) AS remaining_hash_references
            DETACH DELETE media
            RETURN media_properties, remaining_hash_references
            """,
            parameters_={"media_id": media_id},
        )

        record = result.records[0] if result.records else None
        if not record:
            return None

        return (
            _media_from_node(record["media_properties"]),
            record["remaining_hash_references"],
        )
