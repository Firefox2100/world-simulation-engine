import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from world_simulation_engine.misc.consts import PROMPTS, WORKFLOWS
from world_simulation_engine.misc.enums import ComponentType, ImageGenerationType, SupportedLanguage
from world_simulation_engine.model import GeneratedImageMediaFile, ImagePromptProposal, MediaFile, PromptMessage, \
    TransientImagePromptProposal
from world_simulation_engine.service import DatabaseService, ImageService, LlmService, StorageService
from world_simulation_engine.service.storage_service import FormatNormaliser
from ..prompt_loader import PromptLoader
from ..workflow_loader import WorkflowLoader

# Mirrors InputInterpreter's OOC marker syntax: raw user-input presentation blocks (and their
# owning Turn.content) store `[/OOC: ...]` commands verbatim, but they are player instructions to
# the simulator, not diegetic action - they must never leak into an image generation prompt.
_OOC_MARKER_PATTERN = re.compile(r"\[/OOC:.*?\]", flags=re.DOTALL)


def _strip_ooc_markers(text: str) -> str:
    return _OOC_MARKER_PATTERN.sub("", text).strip()


class ImageSubjectContext(BaseModel):
    entity_id: str
    kind: str
    name: str
    description: str
    details: str = ""
    pose_hint: str = ""
    canonical_tags: list[str] = Field(default_factory=list)
    canonical_description: str = ""


class ImagePromptBuildContext(BaseModel):
    purpose: str
    subjects: list[ImageSubjectContext] = Field(default_factory=list)
    narration: str = ""


class CanonicalIdentity(BaseModel):
    """An entity's permanent visual identity, established once and reused to prevent drift."""

    tags: list[str]
    description: str


@dataclass
class ImageParticipant:
    """One entity depicted in a generated image, with the generator that can establish its
    canonical identity if it does not already have one."""

    entity_id: str
    kind: str
    name: str
    description: str
    details: str
    pose_hint: str
    state_generator: "ImageGeneratorComponent"


class ImageGeneratorComponent:
    """Base class for components that generate an AI image depicting one or more entities.

    Subclasses declare COMPONENT_TYPE (the per-source image model and chat model lookup key,
    mirroring SimulatorComponent's chat/embed lookups) and WORKFLOW_NAME (which ComfyUI workflow
    template to compile against, mirroring PromptLoader's per-component prompt lookup), then
    implement _get_entity and _build_context for their entity type.

    Canonical identity: an entity's permanent visual traits (look, build, hair, fixed environment
    features, permanent objects) are generated once - the first time an entity is imaged - and
    then reused unchanged on every later generation to prevent drift. Only the transient part
    (clothing, expression, activity, time of day, temporary props) is generated fresh each time.
    Canonical identity is read from the entity's current cover image; if an entity involved in a
    generation does not have one yet, it is established first (generate() is called on its own
    single-entity generator) before the requested image is built.

    source_id may be either a World id or a Simulation id: model/workflow/prompt configuration is
    resolved the same way regardless (per-simulation overrides fall back to the owning world's,
    which fall back to the built-in default).
    """

    COMPONENT_TYPE: ComponentType = None
    WORKFLOW_NAME: str = None
    NEGATIVE_PROMPT: str | None = (
        "blurry, low quality, distorted anatomy, extra limbs, watermark, text"
    )

    def __init__(self,
                 database: DatabaseService,
                 storage: StorageService,
                 workflow_loader: WorkflowLoader | None = None,
                 prompt_loader: PromptLoader | None = None,
                 ):
        self._db = database
        self._storage = storage
        self._workflow_loader = workflow_loader
        self._prompt_loader = prompt_loader

    async def _resolve_language(self, source_id: str) -> SupportedLanguage:
        world = await self._db.world.get_world(source_id)
        if not world:
            world = await self._db.world.get_world_by_simulation(source_id)
        if not world:
            raise ValueError(f"World for source {source_id} not found")

        return world.language

    async def _prepare_workflow(self, source_id: str) -> dict[str, Any]:
        if self._workflow_loader:
            return await self._workflow_loader.load_workflow(
                simulation_id=source_id,
                workflow_name=self.WORKFLOW_NAME,
            )

        return WORKFLOWS[self.WORKFLOW_NAME]

    async def _prepare_prompt(self,
                              *,
                              source_id: str,
                              language: SupportedLanguage,
                              prompt_name: str,
                              ) -> list[PromptMessage]:
        if self._prompt_loader:
            return await self._prompt_loader.load_prompt(
                simulation_id=source_id,
                language=language,
                prompt_name=prompt_name,
            )

        prompt_data = PROMPTS[language][prompt_name]
        return [PromptMessage.model_validate(p) for p in prompt_data]

    async def _prepare_llm_service(self, source_id: str) -> LlmService:
        chat_config = await self._db.config.get_chat_by_source(
            source_id=source_id,
            component=self.COMPONENT_TYPE,
        )
        if not chat_config:
            raise ValueError(
                f"Source {source_id} does not have a chat model configured for {self.COMPONENT_TYPE}"
            )

        connection_config = await self._db.config.get_connection_by_source(
            source_id=chat_config.id,
        )
        if not connection_config:
            raise ValueError(
                f"Chat model config {chat_config.id} does not have a connection configured"
            )

        return LlmService(
            model_config=chat_config,
            connection_config=connection_config,
        )

    async def _prepare_image_service(self, source_id: str) -> ImageService:
        image_config = await self._db.config.get_image_by_source(
            source_id=source_id,
            component=self.COMPONENT_TYPE,
        )
        if not image_config:
            raise ValueError(
                f"Source {source_id} does not have an image model configured for {self.COMPONENT_TYPE}"
            )

        connection_config = await self._db.config.get_connection_by_image_source(
            source_id=image_config.id,
        )
        if not connection_config:
            raise ValueError(
                f"Image model config {image_config.id} does not have a connection configured"
            )

        workflow = await self._prepare_workflow(source_id)

        return ImageService(
            model_config=image_config,
            connection_config=connection_config,
            workflow=workflow,
        )

    async def _build_full_prompt(self,
                                 *,
                                 source_id: str,
                                 context: ImagePromptBuildContext,
                                 ) -> ImagePromptProposal:
        """Establish canonical + transient prompt content for a subject with no known identity yet."""
        language = await self._resolve_language(source_id)
        prompt = await self._prepare_prompt(
            source_id=source_id,
            language=language,
            prompt_name="image_prompt_builder",
        )
        llm = await self._prepare_llm_service(source_id)

        return await llm.invoke_structured_with_repair(
            output_model=ImagePromptProposal,
            messages=prompt,
            data=context.model_dump(),
            repair_instruction=(
                "Return one valid ImagePromptProposal JSON object only, with canonical_tags (3-25 short "
                "keywords for permanent identity), canonical_description (1-2 plain sentences of permanent "
                "identity only), transient_tags (3-25 short keywords for this image's situational state), "
                "and transient_description (1-2 plain sentences of pose/relationship/interaction)."
            ),
            run_name="image_generator.build_full_prompt",
        )

    async def _build_transient_prompt(self,
                                      *,
                                      source_id: str,
                                      context: ImagePromptBuildContext,
                                      ) -> TransientImagePromptProposal:
        """Generate only transient prompt content; every subject already has known canonical identity."""
        language = await self._resolve_language(source_id)
        prompt = await self._prepare_prompt(
            source_id=source_id,
            language=language,
            prompt_name="image_transient_prompt_builder",
        )
        llm = await self._prepare_llm_service(source_id)

        return await llm.invoke_structured_with_repair(
            output_model=TransientImagePromptProposal,
            messages=prompt,
            data=context.model_dump(),
            repair_instruction=(
                "Return one valid TransientImagePromptProposal JSON object only, with transient_tags (3-25 "
                "short keywords for this image's situational state only) and transient_description (1-2 "
                "plain sentences of pose/relationship/interaction). Do not restate or contradict the supplied "
                "canonical identity."
            ),
            run_name="image_generator.build_transient_prompt",
        )

    async def _get_existing_canonical_identity(self, entity_id: str) -> CanonicalIdentity | None:
        cover = await self._db.media.get_cover_image(entity_id)
        if (
                isinstance(cover, GeneratedImageMediaFile)
                and cover.canonical_tags
                and cover.canonical_description
        ):
            return CanonicalIdentity(tags=cover.canonical_tags, description=cover.canonical_description)

        return None

    async def _ensure_canonical_identity(self,
                                         *,
                                         state_generator: "ImageGeneratorComponent",
                                         source_id: str,
                                         entity_id: str,
                                         ) -> CanonicalIdentity:
        existing = await self._get_existing_canonical_identity(entity_id)
        if existing is not None:
            return existing

        media = await state_generator.generate_as_cover_image(source_id=source_id, entity_id=entity_id)
        return CanonicalIdentity(
            tags=media.canonical_tags if isinstance(media, GeneratedImageMediaFile) else [],
            description=media.canonical_description if isinstance(media, GeneratedImageMediaFile) else "",
        )

    async def _get_entity(self, entity_id: str) -> Any:
        raise NotImplementedError

    async def _build_context(self, entity: Any) -> ImagePromptBuildContext:
        raise NotImplementedError

    async def _store_generated_image(self,
                                      *,
                                      entity_ids: list[str],
                                      image_bytes: bytes,
                                      generation_type: ImageGenerationType,
                                      canonical_tags: list[str],
                                      canonical_description: str,
                                      transient_tags: list[str],
                                      transient_description: str,
                                      title: str | None = None,
                                      filename: str | None = None,
                                      turn_id: str | None = None,
                                      block_id: str | None = None,
                                      ) -> MediaFile:
        normalised = FormatNormaliser.normalise_image(image_bytes)
        stored = await self._storage.save_bytes(normalised)
        media = await self._db.media.create_media(
            GeneratedImageMediaFile(
                title=title,
                hash=stored.digest,
                filename=filename or entity_ids[0],
                generation_type=generation_type,
                component=self.COMPONENT_TYPE,
                workflow_name=self.WORKFLOW_NAME,
                canonical_tags=canonical_tags,
                canonical_description=canonical_description,
                transient_tags=transient_tags,
                transient_description=transient_description,
                negative_prompt=self.NEGATIVE_PROMPT,
            )
        )
        for entity_id in entity_ids:
            await self._db.media.add_generated_image_link(source_id=entity_id, media_id=media.id)
        if turn_id:
            await self._db.media.link_turn_generated_image(turn_id=turn_id, media_id=media.id)
        if block_id:
            await self._db.media.link_presentation_block_image(block_id=block_id, media_id=media.id)

        return media

    async def _generate_from_parts(self,
                                   *,
                                   source_id: str,
                                   entity_ids: list[str],
                                   canonical_tags: list[str],
                                   canonical_description: str,
                                   transient_tags: list[str],
                                   transient_description: str,
                                   generation_type: ImageGenerationType,
                                   title: str | None = None,
                                   filename: str | None = None,
                                   turn_id: str | None = None,
                                   block_id: str | None = None,
                                   ) -> MediaFile:
        positive_prompt = (
            f"{', '.join([*canonical_tags, *transient_tags])}. {canonical_description} {transient_description}"
        ).strip()
        image_service = await self._prepare_image_service(source_id)
        image_bytes = await image_service.generate_image(
            positive_prompt=positive_prompt,
            negative_prompt=self.NEGATIVE_PROMPT,
        )

        return await self._store_generated_image(
            entity_ids=entity_ids,
            image_bytes=image_bytes,
            generation_type=generation_type,
            canonical_tags=canonical_tags,
            canonical_description=canonical_description,
            transient_tags=transient_tags,
            transient_description=transient_description,
            title=title,
            filename=filename,
            turn_id=turn_id,
            block_id=block_id,
        )

    async def _ensure_participants(self,
                                   *,
                                   source_id: str,
                                   participants: list[ImageParticipant],
                                   ) -> list[ImageSubjectContext]:
        subjects = []
        for participant in participants:
            identity = await self._ensure_canonical_identity(
                state_generator=participant.state_generator,
                source_id=source_id,
                entity_id=participant.entity_id,
            )
            subjects.append(
                ImageSubjectContext(
                    entity_id=participant.entity_id,
                    kind=participant.kind,
                    name=participant.name,
                    description=participant.description,
                    details=participant.details,
                    pose_hint=participant.pose_hint,
                    canonical_tags=identity.tags,
                    canonical_description=identity.description,
                )
            )

        return subjects

    async def _generate_composite(self,
                                  *,
                                  source_id: str,
                                  purpose: str,
                                  participants: list[ImageParticipant],
                                  generation_type: ImageGenerationType,
                                  narration: str = "",
                                  title: str | None = None,
                                  filename: str | None = None,
                                  turn_id: str | None = None,
                                  block_id: str | None = None,
                                  ) -> MediaFile:
        """Generate an image depicting several participants, each with its own canonical identity."""
        subjects = await self._ensure_participants(source_id=source_id, participants=participants)
        context = ImagePromptBuildContext(purpose=purpose, subjects=subjects, narration=narration)
        transient_proposal = await self._build_transient_prompt(source_id=source_id, context=context)

        canonical_tags = [tag for subject in subjects for tag in subject.canonical_tags]
        canonical_description = " ".join(
            subject.canonical_description for subject in subjects if subject.canonical_description
        )

        return await self._generate_from_parts(
            source_id=source_id,
            entity_ids=[participant.entity_id for participant in participants],
            canonical_tags=canonical_tags,
            canonical_description=canonical_description,
            transient_tags=transient_proposal.transient_tags,
            transient_description=transient_proposal.transient_description,
            generation_type=generation_type,
            title=title,
            filename=filename,
            turn_id=turn_id,
            block_id=block_id,
        )

    async def _narration_for_turn(self, turn_id: str) -> str:
        turn = await self._db.turn.get_turn(turn_id)
        if not turn:
            return ""

        blocks = await self._db.turn_presentation.list_blocks(turn_ids=[turn_id])
        texts = [_strip_ooc_markers(block.text) for block in blocks if block.text]
        texts = [text for text in texts if text]
        if texts:
            return "\n".join(texts)

        return _strip_ooc_markers(turn.content)

    async def generate(self,
                       *,
                       source_id: str,
                       entity_id: str,
                       ) -> MediaFile:
        """Generate a standalone reference/state image for one entity.

        Establishes canonical identity on the entity's first generation; every later call reuses
        the existing canonical identity and only generates fresh transient content, so repeated
        state generations do not drift.
        """
        entity = await self._get_entity(entity_id)
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        context = await self._build_context(entity)
        existing_identity = await self._get_existing_canonical_identity(entity_id)

        if existing_identity is None:
            proposal = await self._build_full_prompt(source_id=source_id, context=context)
            canonical_tags, canonical_description = proposal.canonical_tags, proposal.canonical_description
            transient_tags, transient_description = proposal.transient_tags, proposal.transient_description
        else:
            canonical_tags, canonical_description = existing_identity.tags, existing_identity.description
            context.subjects[0].canonical_tags = canonical_tags
            context.subjects[0].canonical_description = canonical_description
            transient_proposal = await self._build_transient_prompt(source_id=source_id, context=context)
            transient_tags = transient_proposal.transient_tags
            transient_description = transient_proposal.transient_description

        return await self._generate_from_parts(
            source_id=source_id,
            entity_ids=[entity_id],
            canonical_tags=canonical_tags,
            canonical_description=canonical_description,
            transient_tags=transient_tags,
            transient_description=transient_description,
            generation_type=ImageGenerationType.STATE,
            title=getattr(entity, "name", None),
            filename=entity_id,
        )

    async def generate_as_cover_image(self,
                                      *,
                                      source_id: str,
                                      entity_id: str,
                                      ) -> MediaFile:
        media = await self.generate(source_id=source_id, entity_id=entity_id)
        await self._db.media.set_cover_image(entity_id, media.id)

        return media
