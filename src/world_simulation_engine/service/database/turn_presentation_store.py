"""Persistence for non-authoritative turn renderings."""

from datetime import datetime

from neo4j import AsyncDriver

from world_simulation_engine.model import (
    TurnPresentationBlock,
    TurnPresentationRendering,
)


class TurnPresentationStore:
    def __init__(self, driver: AsyncDriver):
        self._driver = driver

    @staticmethod
    def block_from_node(node) -> TurnPresentationBlock:
        created_at = node["created_at"]
        updated_at = node["updated_at"]
        if hasattr(created_at, "to_native"):
            created_at = created_at.to_native()
        if hasattr(updated_at, "to_native"):
            updated_at = updated_at.to_native()
        return TurnPresentationBlock(
            id=node["id"],
            turn_id=node["turn_id"],
            rendering_id=node["rendering_id"],
            locale=node.get("locale"),
            sequence=node["sequence"],
            type=node["type"],
            text=node.get("text"),
            speaker_id=node.get("speaker_id"),
            speaker_name=node.get("speaker_name"),
            media_id=node.get("media_id"),
            completion=node["completion"],
            created_at=created_at,
            updated_at=updated_at,
        )

    async def replace_rendering(
            self,
            rendering: TurnPresentationRendering,
    ) -> TurnPresentationRendering | None:
        """Atomically replace one display variant without changing its canonical turn."""
        rows = [block.model_dump(mode="python") for block in rendering.blocks]
        result = await self._driver.execute_query(
            """
            MATCH (source:World|Simulation)-[:CONTAINS]->(turn:Turn {id: $turn_id})
            OPTIONAL MATCH (turn)-[:HAS_PRESENTATION]->(old:TurnPresentationBlock {
                rendering_id: $rendering_id
            })
            WHERE (old.locale = $locale OR (old.locale IS NULL AND $locale IS NULL))
            WITH source, turn, collect(old) AS old_blocks
            FOREACH (old IN old_blocks | DETACH DELETE old)
            WITH source, turn
            UNWIND $blocks AS row
            CREATE (block:TurnPresentationBlock {
                id: row.id,
                turn_id: row.turn_id,
                rendering_id: row.rendering_id,
                locale: row.locale,
                sequence: row.sequence,
                type: row.type,
                text: row.text,
                speaker_id: row.speaker_id,
                speaker_name: row.speaker_name,
                media_id: row.media_id,
                completion: row.completion,
                created_at: row.created_at,
                updated_at: row.updated_at
            })
            MERGE (turn)-[:HAS_PRESENTATION]->(block)
            MERGE (source)-[:CONTAINS]->(block)
            RETURN block
            ORDER BY block.sequence
            """,
            parameters_={
                "turn_id": rendering.turn_id,
                "rendering_id": rendering.rendering_id,
                "locale": rendering.locale,
                "blocks": rows,
            },
        )
        if rendering.blocks and len(result.records) != len(rendering.blocks):
            return None
        if not rendering.blocks:
            turn_result = await self._driver.execute_query(
                "MATCH (turn:Turn {id: $turn_id}) RETURN turn",
                parameters_={"turn_id": rendering.turn_id},
            )
            return rendering if turn_result.records else None
        return rendering.model_copy(update={
            "blocks": [self.block_from_node(record["block"]) for record in result.records],
        })

    async def list_blocks(
            self,
            *,
            turn_ids: list[str],
            rendering_id: str = "default",
            locale: str | None = None,
            include_incomplete: bool = True,
    ) -> list[TurnPresentationBlock]:
        if not turn_ids:
            return []
        result = await self._driver.execute_query(
            """
            MATCH (turn:Turn)-[:HAS_PRESENTATION]->(block:TurnPresentationBlock {
                rendering_id: $rendering_id
            })
            WHERE turn.id IN $turn_ids
              AND (block.locale = $locale OR (block.locale IS NULL AND $locale IS NULL))
              AND ($include_incomplete OR block.completion = 'complete')
            RETURN block
            ORDER BY turn.sequence, block.sequence, block.id
            """,
            parameters_={
                "turn_ids": list(dict.fromkeys(turn_ids)),
                "rendering_id": rendering_id,
                "locale": locale,
                "include_incomplete": include_incomplete,
            },
        )
        return [self.block_from_node(record["block"]) for record in result.records]

    async def copy_presentations(
            self,
            *,
            turn_pairs: list[dict],
            copied_at: datetime,
            entity_pairs: list[dict] | None = None,
    ) -> int:
        if not turn_pairs:
            return 0
        result = await self._driver.execute_query(
            """
            UNWIND $turn_pairs AS pair
            MATCH (source:Turn {id: pair.source_id})-[:HAS_PRESENTATION]->(original:TurnPresentationBlock)
            MATCH (target_source:World|Simulation)-[:CONTAINS]->(target:Turn {id: pair.copy_id})
            CREATE (copy:TurnPresentationBlock {
                id: randomUUID(),
                turn_id: pair.copy_id,
                rendering_id: original.rendering_id,
                locale: original.locale,
                sequence: original.sequence,
                type: original.type,
                text: original.text,
                speaker_id: coalesce(
                    head([
                        mapping IN $entity_pairs
                        WHERE mapping.source_id = original.speaker_id
                        | mapping.copy_id
                    ]),
                    original.speaker_id
                ),
                speaker_name: original.speaker_name,
                media_id: original.media_id,
                completion: original.completion,
                created_at: $copied_at,
                updated_at: $copied_at
            })
            MERGE (target)-[:HAS_PRESENTATION]->(copy)
            MERGE (target_source)-[:CONTAINS]->(copy)
            RETURN count(copy) AS copied
            """,
            parameters_={
                "turn_pairs": turn_pairs,
                "entity_pairs": entity_pairs or [],
                "copied_at": copied_at,
            },
        )
        return result.records[0]["copied"] if result.records else 0
