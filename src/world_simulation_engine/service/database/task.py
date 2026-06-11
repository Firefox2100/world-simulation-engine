from sqlalchemy import select, func, exists
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.misc.enums import TaskPriority, TaskStatus, TaskType
from world_simulation_engine.model import Task
from .tables import TaskOrm, CharacterOrm


class TaskRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    async def get(self, task_id: int) -> Task | None:
        """
        Retrieve a task by its ID.
        :param task_id: The ID of the task to retrieve.
        :return: The task with the specified ID, None if not found.
        """
        async with self._session_factory() as session:
            task = await session.get(TaskOrm, task_id)

            if not task:
                return None

            return Task(
                id=task.id,
                character_ids=task.character_ids,
                private=task.private,
                priority=TaskPriority(task.priority),
                status=TaskStatus(task.status),
                type=TaskType(task.type),
                goal=task.goal,
                progress=task.progress,
                source=task.source,
                reward=task.reward,
            )

    async def list(self,
                   simulation_id: int | None = None,
                   character_ids: list[int] | None = None,
                   private: bool | None = None,
                   ):
        if simulation_id and character_ids:
            raise ValueError("Only one of simulation_id and character_ids can be specified ")

        je = func.json_each(TaskOrm.character_ids).table_valued("value").alias("je")

        if simulation_id:
            stmt = select(TaskOrm).where(
                exists(
                    select(1)
                    .select_from(je)
                    .join(
                        CharacterOrm,
                        CharacterOrm.id == je.c.value,
                    )
                    .where(CharacterOrm.simulation_id == simulation_id)
                )
            )

        elif character_ids:
            stmt = select(TaskOrm).where(
                exists(
                    select(1)
                    .select_from(je)
                    .where(je.c.value.in_(character_ids))
                )
            )

        else:
            stmt = select(TaskOrm)

        if private is not None:
            stmt = stmt.where(TaskOrm.private == private)

        async with self._session_factory() as session:
            result = await session.scalars(stmt)
            records = result.all()

            return [
                Task(
                    id=r.id,
                    character_ids=r.character_ids,
                    private=r.private,
                    priority=TaskPriority(r.priority),
                    status=TaskStatus(r.status),
                    type=TaskType(r.type),
                    goal=r.goal,
                    progress=r.progress,
                    source=r.source,
                    reward=r.reward,
                ) for r in records
            ]

    async def create(self, task: Task):
        new_task = TaskOrm(
            character_ids=task.character_ids,
            private=task.private,
            priority=task.priority.value,
            status=task.status.value,
            type=task.type.value,
            goal=task.goal,
            progress=task.progress,
            source=task.source,
            reward=task.reward,
        )

        async with self._session_factory() as session:
            session.add(new_task)

            await session.commit()

            return task.model_copy(update={"id": new_task.id})
