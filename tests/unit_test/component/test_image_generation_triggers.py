import os
from unittest.mock import AsyncMock, Mock

os.environ.setdefault("WSE_NEO4J_PASSWORD", "testpassword")

from fastapi import BackgroundTasks

from world_simulation_engine.component.image_generator.triggers import _generate_cover_image_safely, \
    schedule_cover_image_generation
from world_simulation_engine.misc.enums import ComponentType


async def test_generate_cover_image_safely_calls_generate_as_cover_image():
    generator = Mock()
    generator.COMPONENT_TYPE = ComponentType.CHARACTER_IMAGE_GENERATOR
    generator.generate_as_cover_image = AsyncMock()

    await _generate_cover_image_safely(generator=generator, source_id="world_1", entity_id="character_1")

    generator.generate_as_cover_image.assert_awaited_once_with(source_id="world_1", entity_id="character_1")


async def test_generate_cover_image_safely_swallows_errors():
    generator = Mock()
    generator.COMPONENT_TYPE = ComponentType.CHARACTER_IMAGE_GENERATOR
    generator.generate_as_cover_image = AsyncMock(side_effect=ValueError("no image model configured"))

    # Must not raise: a failed auto-generation is never allowed to break entity creation.
    await _generate_cover_image_safely(generator=generator, source_id="world_1", entity_id="character_1")


async def test_schedule_cover_image_generation_adds_background_task():
    background_tasks = BackgroundTasks()
    generator = Mock()
    generator.COMPONENT_TYPE = ComponentType.CHARACTER_IMAGE_GENERATOR
    generator.generate_as_cover_image = AsyncMock()

    schedule_cover_image_generation(
        background_tasks, generator=generator, source_id="world_1", entity_id="character_1",
    )
    await background_tasks()

    generator.generate_as_cover_image.assert_awaited_once_with(source_id="world_1", entity_id="character_1")
