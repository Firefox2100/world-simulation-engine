from neo4j import AsyncDriver

from world_simulation_engine.model import MediaFile


def _media_from_node(media_node) -> MediaFile:
    return MediaFile(
        id=media_node["id"],
        type=media_node["type"],
        title=media_node.get("title"),
        hash=media_node["hash"],
        filename=media_node["filename"],
    )


class MediaStore:
    _COVER_SOURCE_LABELS = "World|Simulation|Character|BackgroundCharacter|Location|Landmark|Item|ItemStack|Equipment|Container"

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
                filename: $filename
            })
            RETURN m
            """,
            parameters_={
                "id": media.id,
                "type": media.type,
                "title": media.title,
                "hash": media.hash,
                "filename": media.filename,
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

    async def delete_media(self, media_id: str) -> tuple[MediaFile, int] | None:
        result = await self._driver.execute_query(
            """
            MATCH (media:Media {id: $media_id})
            WITH media, properties(media) AS media_properties, media.hash AS hash
            DETACH DELETE media
            WITH media_properties, hash
            OPTIONAL MATCH (other:Media {hash: hash})
            RETURN media_properties, count(other) AS remaining_hash_references
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
