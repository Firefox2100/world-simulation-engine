from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.model import Character
from .tables import CharacterOrm


class CharacterRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

    @staticmethod
    def _to_model(record: CharacterOrm) -> Character:
        payload = {
            column.name: getattr(record, column.name)
            for column in CharacterOrm.__table__.columns
            if column.name != "simulation_id"
        }
        return Character.model_validate(payload)

    async def get(self, character_id: int) -> Character | None:
        """
        Retrieve a character by its ID.
        :param character_id: The ID of the character to retrieve.
        :return: The character with the specified ID, None if not found.
        """
        async with self._session_factory() as session:
            character = await session.get(CharacterOrm, character_id)

            if not character:
                return None

            return self._to_model(character)

    async def list(self,
                   simulation_id: int | None = None,
                   location: int | None = None,
                   controlled_by_user: bool | None = None,
                   character_ids: list[int] | None = None,
                   ) -> list[Character]:
        async with self._session_factory() as session:
            stmt = select(CharacterOrm)
            if simulation_id:
                stmt = stmt.where(CharacterOrm.simulation_id == simulation_id)
            if location:
                stmt = stmt.where(CharacterOrm.location == location)
            if controlled_by_user is not None:
                stmt = stmt.where(CharacterOrm.user_controlled == controlled_by_user)
            if character_ids:
                stmt = stmt.where(CharacterOrm.id.in_(character_ids))

            result = await session.scalars(stmt)
            records = result.all()

            return [self._to_model(record) for record in records]

    async def create(self,
                     character: Character,
                     simulation_id: int,
                     ) -> Character:
        """
        Create a character in the database.
        :param character: The character to create.
        :param simulation_id: The simulation id that the character belongs to
        """
        payload = character.model_dump(mode="json", exclude={"id"})

        async with self._session_factory() as session:
            new_character = CharacterOrm(simulation_id=simulation_id, **payload)
            session.add(new_character)

            await session.commit()
            return self._to_model(new_character)

    async def update(self, character_id: int, patched_data: dict):
        async with self._session_factory() as session:
            await session.execute(
                update(CharacterOrm).where(CharacterOrm.id == character_id).values(patched_data)
            )
            await session.commit()

    async def delete(self, character_id: int) -> None:
        async with self._session_factory() as session:
            await session.execute(
                delete(CharacterOrm).where(CharacterOrm.id == character_id)
            )
            await session.commit()
