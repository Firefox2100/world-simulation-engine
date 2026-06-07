from sqlalchemy import ForeignKey, String, Text, Integer, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class WorldTable(Base):
    __tablename__ = 'world'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class SimulationTable(Base):
    __tablename__ = 'simulation'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    world_id: Mapped[int] = mapped_column(Integer, ForeignKey('world.id'), nullable=False)
    data_preset: Mapped[dict] = mapped_column(JSON, nullable=False)


class CharacterTable(Base):
    __tablename__ = 'character'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, ForeignKey('simulation.id'), nullable=False)


class LocationTable(Base):
    __tablename__ = 'location'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, ForeignKey('simulation.id'), nullable=False)
