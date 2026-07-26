from fastapi import BackgroundTasks

from world_simulation_engine.misc.logging import log_event
from .image_generator_component import ImageGeneratorComponent


def schedule_cover_image_generation(
        background_tasks: BackgroundTasks,
        *,
        generator: ImageGeneratorComponent,
        source_id: str,
        entity_id: str,
) -> None:
    """Fire-and-forget cover image generation for a newly created entity.

    Runs after the HTTP response is sent, so entity creation never waits on it. Failures (most
    commonly: no image model configured yet for this world/simulation) are logged and swallowed -
    entity creation must never be blocked or broken by image generation being unavailable.
    """
    background_tasks.add_task(
        _generate_cover_image_safely,
        generator=generator,
        source_id=source_id,
        entity_id=entity_id,
    )


async def _generate_cover_image_safely(
        *,
        generator: ImageGeneratorComponent,
        source_id: str,
        entity_id: str,
) -> None:
    try:
        await generator.generate_as_cover_image(source_id=source_id, entity_id=entity_id)
    except Exception as exc:
        log_event(
            "auto_cover_image_generation_failed",
            entity_id=entity_id,
            source_id=source_id,
            component=str(generator.COMPONENT_TYPE),
            error_type=type(exc).__name__,
        )
