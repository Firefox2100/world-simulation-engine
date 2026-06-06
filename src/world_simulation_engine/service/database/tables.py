from sqlalchemy import ForeignKey, String, Text, Integer, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class DataPresetModelTable(Base):
    __tablename__ = "data_preset_models"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    schema: Mapped[dict] = mapped_column(JSON, nullable=False)

    preset_id: Mapped[int] = mapped_column(Integer, ForeignKey("data_presets.id"), nullable=False)


class DataPresetTable(Base):
    __tablename__ = "data_presets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    preset_id: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
