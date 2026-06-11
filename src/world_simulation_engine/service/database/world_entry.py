import numpy as np
from sqlalchemy import select, func, exists
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.misc.enums import NarrationPermission, WorldEntryRecallType, WorldEntryVisibility
from world_simulation_engine.model import WorldEntry, WorldEntryRecallKeyword
from .tables import WorldEntryOrm


class WorldEntryRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    async def get(self, entry_id: int) -> WorldEntry | None:
        """
        Retrieve a world entry by its ID.
        :param entry_id: The ID of the world entry to retrieve.
        :return: The world entry with the specified ID, None if not found.
        """
        async with self._session_factory() as session:
            entry = await session.get(WorldEntryOrm, entry_id)

            if not entry:
                return None

            return WorldEntry(
                id=entry.id,
                scope=entry.scope,
                content=entry.content,
                visibility=WorldEntryVisibility(entry.visibility),
                confidence=entry.confidence,
                created_at=entry.created_at,
                narration_permission=NarrationPermission(entry.narration_permission),
                recall_type=WorldEntryRecallType(entry.recall_type),
                keywords=[
                    WorldEntryRecallKeyword(
                        keyword=k["keyword"],
                        similarity=k["similarity"],
                        embedding=k.get("embedding", None),
                    ) for k in entry.keywords
                ] if entry.keywords else None,
                chained_ids=entry.chained_ids,
                semantic_instruction=entry.semantic_instruction,
                embedding=entry.embedding.tolist() if entry.embedding else None,
            )

    async def list(self,
                   simulation_id: int | None = None,
                   search_scope: list[int] | None = None,
                   ) -> list[WorldEntry]:
        stmt = select(WorldEntryOrm)
        if simulation_id:
            stmt = stmt.where(WorldEntryOrm.simulation_id == simulation_id)
        if search_scope:
            # Match any that contains any scope ID in the list
            je = func.json_each(WorldEntryOrm.scope).table_valued("value").alias("je")
            stmt = stmt.where(
                exists(
                    select(1)
                    .select_from(je)
                    .where(je.c.value.in_(search_scope))
                )
            )

        async with self._session_factory() as session:
            result = await session.scalars(stmt)
            records = result.all()

            return [
                WorldEntry(
                    id=r.id,
                    scope=r.scope,
                    content=r.content,
                    visibility=WorldEntryVisibility(r.visibility),
                    confidence=r.confidence,
                    created_at=r.created_at,
                    narration_permission=NarrationPermission(r.narration_permission),
                    recall_type=WorldEntryRecallType(r.recall_type),
                    keywords=[
                        WorldEntryRecallKeyword(
                            keyword=k["keyword"],
                            similarity=k["similarity"],
                            embedding=k.get("embedding", None),
                        ) for k in r.keywords
                    ] if r.keywords else None,
                    chained_ids=r.chained_ids,
                    semantic_instruction=r.semantic_instruction,
                    embedding=r.embedding.tolist() if r.embedding else None,
                ) for r in records
            ]

    async def create(self,
                     world_entry: WorldEntry,
                     simulation_id: int,
                     ):
        new_entry = WorldEntryOrm(
            simulation_id=simulation_id,
            scope=world_entry.scope,
            content=world_entry.content,
            visibility=world_entry.visibility.value,
            confidence=world_entry.confidence,
            created_at=world_entry.created_at,
            narration_permission=world_entry.narration_permission.value,
            recall_type=world_entry.recall_type.value,
            keywords=[k.model_dump() for k in world_entry.keywords] if world_entry.keywords else None,
            chained_ids=world_entry.chained_ids,
            semantic_instruction=world_entry.semantic_instruction,
            embedding=np.array(world_entry.embedding, dtype=np.float32) if world_entry.embedding else None,
        )

        async with self._session_factory() as session:
            session.add(new_entry)
            await session.commit()

            return world_entry.model_copy(update={"id": new_entry.id})
