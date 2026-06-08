from sqlalchemy import ForeignKey, String, Text, Integer, JSON, LargeBinary, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class WorldTable(Base):
    __tablename__ = "world"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)


class SimulationTable(Base):
    __tablename__ = "simulation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    world_id: Mapped[int] = mapped_column(Integer, ForeignKey("world.id"), nullable=False)
    data_preset: Mapped[dict] = mapped_column(JSON, nullable=False)


class SimulationStateTable(Base):
    __tablename__ = "simulation_state"

    id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), primary_key=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("location.id"), nullable=False)
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    time_label: Mapped[str] = mapped_column(String(32), nullable=False)


class CharacterTable(Base):
    __tablename__ = "character"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    gender: Mapped[str] = mapped_column(String(32), nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    appearance: Mapped[str] = mapped_column(Text, nullable=False)
    public_state: Mapped[str] = mapped_column(Text, nullable=False)
    private_state: Mapped[str] = mapped_column(Text, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, nullable=False)
    stats: Mapped[dict] = mapped_column(JSON, nullable=False)
    location: Mapped[int] = mapped_column(Integer, ForeignKey("location.id"), nullable=False)
    user_controlled: Mapped[bool] = mapped_column(Boolean, nullable=False)


class LlmConnectionProfileTable(Base):
    __tablename__ = "llm_connection_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), nullable=False)


class DataPresetTable(Base):
    __tablename__ = "data_preset"

    id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), primary_key=True)
    character_attributes: Mapped[list] = mapped_column(JSON, nullable=False)
    character_stats: Mapped[list] = mapped_column(JSON, nullable=False)
    faction_attributes: Mapped[list] = mapped_column(JSON, nullable=False)
    faction_stats: Mapped[list] = mapped_column(JSON, nullable=False)
    entity_types: Mapped[dict] = mapped_column(JSON, nullable=False)


class FactionTable(Base):
    __tablename__ = "faction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, nullable=False)
    stats: Mapped[dict] = mapped_column(JSON, nullable=False)


class FactionRelationship(Base):
    __tablename__ = "faction_relationship"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_type: Mapped[str] = mapped_column(String(16), nullable=False)
    from_id: Mapped[int] = mapped_column(Integer, nullable=False)
    to_type: Mapped[str] = mapped_column(String(16), nullable=False)
    to_id: Mapped[int] = mapped_column(Integer, nullable=False)
    relationship: Mapped[str] = mapped_column(String(32), nullable=False)
    private: Mapped[bool] = mapped_column(Boolean, nullable=False)


class LocationTable(Base):
    __tablename__ = "location"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), nullable=False)
