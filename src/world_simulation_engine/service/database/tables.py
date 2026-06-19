from typing import Any
import numpy as np
from sqlalchemy import ForeignKey, String, Text, Integer, Float, JSON, LargeBinary, Boolean, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class NumpyArray(TypeDecorator):
    """Stores a numpy array as a binary blob."""
    impl = LargeBinary
    cache_ok = True

    def __init__(self, dtype=np.float32, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dtype = dtype

    def process_bind_param(self, value, dialect):
        if value is not None:
            # Ensure it's a numpy array and convert to bytes
            if not isinstance(value, np.ndarray):
                value = np.array(value, dtype=self.dtype)
            return value.tobytes()
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            # Reconstruct array from bytes
            return np.frombuffer(value, dtype=self.dtype)
        return value


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
    simulation_id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), nullable=False)
    character_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("character.id", ondelete="SET NULL"),
        nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quality: Mapped[str | None] = mapped_column(String(32), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unique: Mapped[bool] = mapped_column(Boolean, nullable=False)


class EquipmentOrm(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), nullable=False)
    character_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("character.id", ondelete="SET NULL"),
        nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    quality: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False)


class LlmConnectionProfileOrm(Base):
    __tablename__ = "llm_connection_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)


class ImageGenerationConnectionProfileOrm(Base):
    __tablename__ = "image_generation_connection_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)


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
    world_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("world.id", ondelete="SET NULL"),
        nullable=True
    )
    agent_preset: Mapped[dict] = mapped_column(JSON, nullable=False)
    data_preset: Mapped[dict] = mapped_column(JSON, nullable=False)
    embedding_profile: Mapped[dict] = mapped_column(JSON, nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False)
    act_for_user: Mapped[bool] = mapped_column(Boolean, nullable=False)
    enable_tts: Mapped[bool] = mapped_column(Boolean, nullable=False)
    enable_image_generation: Mapped[bool] = mapped_column(Boolean, nullable=False)


class SimulationStateOrm(Base):
    __tablename__ = "simulation_state"

    id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), primary_key=True)
    location_id: Mapped[int] = mapped_column(Integer, ForeignKey("location.id"), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    time_label: Mapped[str] = mapped_column(String(32), nullable=False)
    recent_history_summary: Mapped[str] = mapped_column(Text, nullable=True)
    long_term_history_summary: Mapped[str] = mapped_column(Text, nullable=True)


class TaskOrm(Base):
    __tablename__ = "task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_ids: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    private: Mapped[bool] = mapped_column(Boolean, nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    reward: Mapped[str] = mapped_column(String(255), nullable=False)


class TurnRecordOrm(Base):
    __tablename__ = "turn_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), nullable=False)
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(String(16), nullable=False)
    director_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    proposals: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    briefing_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    character_actions: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    character_reactions: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    resolver_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reaction_resolving: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    committer_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    narration: Mapped[str] = mapped_column(Text, nullable=False)
    summary_output: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class WorldOrm(Base):
    __tablename__ = "world"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_preset: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_preset: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    embedding_profile: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    language: Mapped[str | None] = mapped_column(String(8), nullable=True)
    act_for_user: Mapped[bool] = mapped_column(Boolean, nullable=False)
    enable_tts: Mapped[bool] = mapped_column(Boolean, nullable=False)
    enable_image_generation: Mapped[bool] = mapped_column(Boolean, nullable=False)
    state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    characters: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    locations: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    factions: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    faction_relationships: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    inventory: Mapped[dict[int, dict[str, list[dict]]] | None] = mapped_column(JSON, nullable=True)
    tasks: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    world_entries: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)
    turn_records: Mapped[list[dict] | None] = mapped_column(JSON, nullable=True)

class WorldEntryOrm(Base):
    __tablename__ = "world_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    simulation_id: Mapped[int] = mapped_column(Integer, ForeignKey("simulation.id"), nullable=False)
    scope: Mapped[list[int]] = mapped_column(JSON, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    narration_permission: Mapped[str] = mapped_column(String(16), nullable=False)
    recall_type: Mapped[str] = mapped_column(String(16), nullable=False)
    keywords: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    chained_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    semantic_instruction: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[np.ndarray | None] = mapped_column(NumpyArray(dtype=np.float32), nullable=True)
