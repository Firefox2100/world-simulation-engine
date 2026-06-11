from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from world_simulation_engine.model import Character
from .tables import CharacterOrm


class CharacterRepository:
    def __init__(self,
                 session_factory: async_sessionmaker[AsyncSession],
                 ):
        self._session_factory = session_factory

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

            return Character(
                id=character.id,
                name=character.name,
                description=character.description,
                gender=character.gender,
                age=character.age,
                appearance=character.appearance,
                public_state=character.public_state,
                private_state=character.private_state,
                location=character.location,
                user_controlled=character.user_controlled,
            )

    async def list(self,
                   simulation_id: int | None = None,
                   location: int | None = None,
                   character_ids: list[int] | None = None,
                   ) -> list[Character]:
        async with self._session_factory() as session:
            stmt = select(CharacterOrm)
            if simulation_id:
                stmt = stmt.where(CharacterOrm.simulation_id == simulation_id)
            if location:
                stmt = stmt.where(CharacterOrm.location == location)
            if character_ids:
                stmt = stmt.where(CharacterOrm.id.in_(character_ids))

            result = await session.scalars(stmt)
            records = result.all()

            return [
                Character(
                    id=r.id,
                    name=r.name,
                    description=r.description,
                    gender=r.gender,
                    age=r.age,
                    appearance=r.appearance,
                    public_state=r.public_state,
                    private_state=r.private_state,
                    location=r.location,
                    user_controlled=r.user_controlled,
                ) for r in records
            ]

    async def create(self,
                     character: Character,
                     simulation_id: int,
                     ) -> Character:
        """
        Create a character in the database.
        :param character: The character to create.
        :param simulation_id: The simulation id that the character belongs to
        """
        async with self._session_factory() as session:
            new_character = CharacterOrm(
                simulation_id=simulation_id,
                name=character.name,
                description=character.description,
                gender=character.gender,
                age=character.age,
                appearance=character.appearance,
                public_state=character.public_state,
                private_state=character.private_state,
                attributes=character.attributes,
                stats=character.stats,
                location=character.location,
                user_controlled=character.user_controlled,
            )
            session.add(new_character)

            await session.commit()
            return character.model_copy(update={'id': new_character.id})
