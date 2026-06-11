from sqlalchemy import select, func, exists
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.model import Task
from .tables import TaskOrm, CharacterOrm


class TaskRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_model(record: TaskOrm) -> Task:
        payload = {column.name: getattr(record, column.name) for column in TaskOrm.__table__.columns}
        return Task.model_validate(payload)

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

            return self._to_model(task)

    async def list(self,
                   simulation_id: int | None = None,
                   character_ids: list[int] | None = None,
                   task_ids: list[int] | None = None,
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

        if task_ids:
            stmt = stmt.where(TaskOrm.id.in_(task_ids))

        if private is not None:
            stmt = stmt.where(TaskOrm.private == private)

        async with self._session_factory() as session:
            result = await session.scalars(stmt)
            records = result.all()

            return [self._to_model(record) for record in records]

    async def create(self, task: Task):
        payload = task.model_dump(mode="json", exclude={"id"})
        new_task = TaskOrm(**payload)

        async with self._session_factory() as session:
            session.add(new_task)

            await session.commit()

            return self._to_model(new_task)
