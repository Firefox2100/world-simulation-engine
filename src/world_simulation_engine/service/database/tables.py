from sqlalchemy import ForeignKey, String, Text, Integer, JSON, LargeBinary, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class CharacterOrm(Base):
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


class EntityOrm(Base):
    __tablename__ = "entity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("location.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    interactions: Mapped[list[str]] = mapped_column(JSON, nullable=False)


class FactionOrm(Base):
    __tablename__ = "faction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, nullable=False)
    stats: Mapped[dict] = mapped_column(JSON, nullable=False)


class FactionRelationshipOrm(Base):
    __tablename__ = "faction_relationship"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    from_type: Mapped[str] = mapped_column(String(16), nullable=False)
    from_id: Mapped[int] = mapped_column(Integer, nullable=False)
    to_type: Mapped[str] = mapped_column(String(16), nullable=False)
    to_id: Mapped[int] = mapped_column(Integer, nullable=False)
    relationship: Mapped[str] = mapped_column(String(32), nullable=False)
    private: Mapped[bool] = mapped_column(Boolean, nullable=False)


class ItemOrm(Base):
    __tablename__ = "item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(Integer, ForeignKey("character.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quality: Mapped[str] = mapped_column(String(32), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unique: Mapped[bool] = mapped_column(Boolean, nullable=False)


class LlmConnectionProfileOrm(Base):
    __tablename__ = "llm_connection_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=True)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), nullable=False)


class LocationOrm(Base):
    __tablename__ = "location"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), nullable=False)
    primary_location: Mapped[str] = mapped_column(String(255), nullable=False)
    detailed_location: Mapped[str] = mapped_column(String(255), nullable=False)
    scene: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    attributes: Mapped[dict] = mapped_column(JSON, nullable=False)
    stats: Mapped[dict] = mapped_column(JSON, nullable=False)


class SimulationOrm(Base):
    __tablename__ = "simulation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    world_id: Mapped[int] = mapped_column(Integer, ForeignKey("world.id"), nullable=False)
    agent_preset: Mapped[dict] = mapped_column(JSON, nullable=False)
    data_preset: Mapped[dict] = mapped_column(JSON, nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)


class SimulationStateOrm(Base):
    __tablename__ = "simulation_state"

    id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), primary_key=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("location.id"), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    time_label: Mapped[str] = mapped_column(String(32), nullable=False)
    recent_history_summary: Mapped[str] = mapped_column(Text, nullable=True)
    long_term_history_summary: Mapped[str] = mapped_column(Text, nullable=True)


class TurnRecordOrm(Base):
    __tablename__ = "turn_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    narration: Mapped[str] = mapped_column(Text, nullable=False)


class WorldOrm(Base):
    __tablename__ = "world"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
