from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest
from neo4j import AsyncGraphDatabase
from testcontainers.neo4j import Neo4jContainer

from world_simulation_engine.misc.enums import (
    ComponentType,
    ConnectionType,
    ContainerState,
    EventInvolvement,
    IntentHorizon,
    IntentStatus,
    IntentType,
    MemoryStance,
    MemorySupportType,
    Salience,
    SupportedLanguage,
    TurnType,
)
from world_simulation_engine.model import (
    Author,
    BackgroundCharacter,
    Character,
    Container,
    CurrentActivity,
    Equipment,
    Event,
    Intent,
    Item,
    ItemStack,
    Landmark,
    Location,
    MemoryAtom,
    ConnectionConfig,
    OllamaChatModelConfig,
    OllamaEmbedModelConfig,
    OpenAiChatModelConfig,
    OpenAiEmbedModelConfig,
    Simulation,
    Turn,
    World,
)
from world_simulation_engine.service import DatabaseService
from world_simulation_engine.service.embed_service import EmbedService
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    return default if value is None or value == "" else float(value)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return default if value is None or value == "" else int(value)


def _env_optional_int(name: str) -> int | None:
    value = os.getenv(name)
    return None if value is None or value == "" else int(value)


def _env_optional_float(name: str) -> float | None:
    value = os.getenv(name)
    return None if value is None or value == "" else float(value)


def _env_optional_str(name: str) -> str | None:
    value = os.getenv(name)
    return None if value is None or value == "" else value


@pytest.fixture(scope="session")
def evaluation_connection_config() -> ConnectionConfig:
    provider = os.getenv("WSE_EVAL_LLM_PROVIDER", "ollama").lower()
    if provider not in {"ollama", "openai"}:
        raise ValueError("WSE_EVAL_LLM_PROVIDER must be either 'ollama' or 'openai'")

    default_base_url = "http://localhost:11434" if provider == "ollama" else None
    return ConnectionConfig(
        id=os.getenv("WSE_EVAL_CONNECTION_ID", "eval_connection"),
        type=ConnectionType(provider),
        name=os.getenv("WSE_EVAL_CONNECTION_NAME", "Evaluation connection"),
        base_url=_env_optional_str("WSE_EVAL_LLM_BASE_URL") or default_base_url,
        api_key=_env_optional_str("WSE_EVAL_LLM_API_KEY"),
    )


@pytest.fixture(scope="session")
def evaluation_chat_model_config(evaluation_connection_config: ConnectionConfig):
    if evaluation_connection_config.type == ConnectionType.OPENAI:
        return OpenAiChatModelConfig(
            id=os.getenv("WSE_EVAL_CHAT_CONFIG_ID", "eval_chat"),
            name=os.getenv("WSE_EVAL_CHAT_CONFIG_NAME", "Evaluation chat"),
            model=os.getenv("WSE_EVAL_CHAT_MODEL", "gpt-4.1-mini"),
            temperature=_env_float("WSE_EVAL_CHAT_TEMPERATURE", 0),
            context_window=_env_int("WSE_EVAL_CHAT_CONTEXT_WINDOW", 65536),
            seed=_env_optional_int("WSE_EVAL_CHAT_SEED"),
            reasoning=_env_optional_str("WSE_EVAL_CHAT_REASONING"),
        )

    return OllamaChatModelConfig(
        id=os.getenv("WSE_EVAL_CHAT_CONFIG_ID", "eval_chat"),
        name=os.getenv("WSE_EVAL_CHAT_CONFIG_NAME", "Evaluation chat"),
        model=os.getenv("WSE_EVAL_CHAT_MODEL", "llama3"),
        temperature=_env_float("WSE_EVAL_CHAT_TEMPERATURE", 0),
        context_window=_env_int("WSE_EVAL_CHAT_CONTEXT_WINDOW", 8192),
        seed=_env_optional_int("WSE_EVAL_CHAT_SEED"),
        reasoning=_env_optional_str("WSE_EVAL_CHAT_REASONING"),
        mirostat=_env_optional_int("WSE_EVAL_OLLAMA_MIROSTAT"),
        mirostat_eta=_env_optional_float("WSE_EVAL_OLLAMA_MIROSTAT_ETA"),
        mirostat_tau=_env_optional_float("WSE_EVAL_OLLAMA_MIROSTAT_TAU"),
        num_predict=_env_optional_int("WSE_EVAL_OLLAMA_NUM_PREDICT"),
        repeat_penalty_window=_env_optional_int("WSE_EVAL_OLLAMA_REPEAT_PENALTY_WINDOW"),
        repeat_penalty=_env_optional_float("WSE_EVAL_OLLAMA_REPEAT_PENALTY"),
    )


@pytest.fixture(scope="session")
def evaluation_embed_model_config(evaluation_connection_config: ConnectionConfig):
    if evaluation_connection_config.type == ConnectionType.OPENAI:
        return OpenAiEmbedModelConfig(
            id=os.getenv("WSE_EVAL_EMBED_CONFIG_ID", "eval_embed"),
            model=os.getenv("WSE_EVAL_EMBED_MODEL", "text-embedding-3-small"),
            dimension=_env_optional_int("WSE_EVAL_EMBED_DIMENSION"),
        )

    return OllamaEmbedModelConfig(
        id=os.getenv("WSE_EVAL_EMBED_CONFIG_ID", "eval_embed"),
        model=os.getenv("WSE_EVAL_EMBED_MODEL", "nomic-embed-text"),
        dimension=_env_optional_int("WSE_EVAL_EMBED_DIMENSION"),
        context_window=_env_optional_int("WSE_EVAL_EMBED_CONTEXT_WINDOW"),
    )


@pytest.fixture
def evaluation_embed_service(
    evaluation_connection_config: ConnectionConfig,
    evaluation_embed_model_config,
) -> EmbedService:
    return EmbedService(
        model_config=evaluation_embed_model_config,
        connection_config=evaluation_connection_config,
    )


@pytest.fixture(scope="session")
def ollama_chat_model_config(evaluation_chat_model_config):
    return evaluation_chat_model_config


@pytest.fixture(scope="session")
def ollama_embed_model_config(evaluation_embed_model_config):
    return evaluation_embed_model_config


@pytest.fixture(scope="session")
def evaluation_neo4j_container():
    image = os.getenv("WSE_EVAL_NEO4J_IMAGE", "neo4j:2026.04.0")
    password = os.getenv("WSE_EVAL_NEO4J_PASSWORD", "testpassword")
    with Neo4jContainer(image, username="neo4j", password=password)\
            .with_env("NEO4J_PLUGINS", '["apoc","graph-data-science"]')\
            .with_env("NEO4J_apoc_export_file_enabled", "true")\
            .with_env("NEO4J_apoc_import_file_enabled", "true")\
            .with_env("NEO4J_apoc_import_file_use__neo4j__config", "true") as container:
        yield container


@pytest.fixture
async def evaluation_neo4j_driver(evaluation_neo4j_container):
    password = os.getenv("WSE_EVAL_NEO4J_PASSWORD", "testpassword")
    driver = AsyncGraphDatabase.driver(
        evaluation_neo4j_container.get_connection_url(),
        auth=("neo4j", password),
    )
    await driver.verify_connectivity()

    try:
        yield driver
    finally:
        await driver.close()


@pytest.fixture
async def evaluation_database(evaluation_neo4j_driver, evaluation_embed_service):
    await evaluation_neo4j_driver.execute_query("MATCH (n) DETACH DELETE n")
    database = DatabaseService(evaluation_neo4j_driver, embed_service=evaluation_embed_service)
    try:
        yield database
    finally:
        await evaluation_neo4j_driver.execute_query("MATCH (n) DETACH DELETE n")


@pytest.fixture
async def evaluation_seeded_database(
    evaluation_database,
    mock_graph_world_setup,
    evaluation_connection_config,
    evaluation_chat_model_config,
    evaluation_embed_model_config,
):
    await mock_graph_world_setup.load_into_database(evaluation_database)
    await evaluation_database.config.create_connection(evaluation_connection_config)
    await evaluation_database.config.create_chat(evaluation_chat_model_config)
    await evaluation_database.config.create_embed(evaluation_embed_model_config)
    await evaluation_database.config.link_connection(
        source_id=evaluation_chat_model_config.id,
        connection_id=evaluation_connection_config.id,
    )
    await evaluation_database.config.link_connection(
        source_id=evaluation_embed_model_config.id,
        connection_id=evaluation_connection_config.id,
    )
    await evaluation_database.config.link_chat(
        source_id=mock_graph_world_setup.simulation.id,
        config_id=evaluation_chat_model_config.id,
        component=ComponentType.INPUT_INTERPRETER,
    )
    await evaluation_database.config.link_embed(
        source_id=mock_graph_world_setup.simulation.id,
        config_id=evaluation_embed_model_config.id,
        component=ComponentType.CHARACTER_SIMULATOR,
    )

    return evaluation_database


@dataclass(frozen=True)
class CharacterPlacement:
    character_id: str
    location_id: str
    position: str | None = None
    landmark_id: str | None = None


@dataclass(frozen=True)
class ItemStackPlacement:
    item_id: str
    stack: ItemStack
    location_id: str | None = None
    holder_id: str | None = None
    owner_id: str | None = None
    position: str | None = None


@dataclass(frozen=True)
class EquipmentPlacement:
    equipment_id: str
    location_id: str | None = None
    holder_id: str | None = None
    owner_id: str | None = None
    equipped: bool = False
    equipped_position: str | None = None
    position: str | None = None


@dataclass(frozen=True)
class ContainerPlacement:
    container_id: str
    location_id: str
    position: str | None = None
    unlocking_item_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemorySeed:
    memory: MemoryAtom
    event_id: str
    support_type: MemorySupportType
    character_links: tuple[CharacterMemoryLink, ...]


@dataclass(frozen=True)
class EventInvolvementSeed:
    event_id: str
    character_id: str
    involvement: EventInvolvement


@dataclass(frozen=True)
class GraphWorldSetup:
    author: Author
    world: World
    simulation: Simulation
    initial_turn: Turn
    locations: tuple[Location, ...]
    location_parents: dict[str, str | None]
    landmarks_by_location: dict[str, tuple[Landmark, ...]]
    containers: tuple[Container, ...]
    container_placements: tuple[ContainerPlacement, ...]
    characters: tuple[Character, ...]
    background_characters: tuple[BackgroundCharacter, ...]
    character_placements: tuple[CharacterPlacement, ...]
    background_character_placements: tuple[CharacterPlacement, ...]
    items: tuple[Item, ...]
    item_stack_placements: tuple[ItemStackPlacement, ...]
    equipment: tuple[Equipment, ...]
    equipment_placements: tuple[EquipmentPlacement, ...]
    events: tuple[Event, ...]
    event_involvements: tuple[EventInvolvementSeed, ...]
    memories: tuple[MemorySeed, ...]
    intents: tuple[Intent, ...]
    intent_character_ids: dict[str, str]
    metadata: dict[str, str] = field(default_factory=dict)

    async def load_into_database(self, database):
        await database.world.create_author(self.author)
        await database.world.create_world(self.world, self.author.id)
        await database.simulation.create_simulation(self.simulation, self.world.id)
        await database.turn.create_turn(self.initial_turn, self.simulation.id)

        for location in self.locations:
            await database.location.create_location(
                location=location,
                source_id=self.world.id,
                contained_in=self.location_parents.get(location.id),
            )

        for location_id, landmarks in self.landmarks_by_location.items():
            for landmark in landmarks:
                await database.location.create_landmark(landmark, location_id)

        for container in self.containers:
            placement = next(p for p in self.container_placements if p.container_id == container.id)
            await database.container.create_container(
                container=container,
                source_id=self.simulation.id,
                location_id=placement.location_id,
                position=placement.position,
            )

        for character in self.characters:
            await database.character.create_character(character, self.simulation.id)

        for placement in self.character_placements:
            await database.character.move_to_location(
                character_id=placement.character_id,
                location_id=placement.location_id,
                position=placement.position,
            )
            if placement.landmark_id:
                await database.character.anchor_to_landmark(placement.character_id, placement.landmark_id)

        for background_character in self.background_characters:
            placement = next(
                p
                for p in self.background_character_placements
                if p.character_id == background_character.id
            )
            await database.character.create_background_character(
                background_character,
                source_id=self.simulation.id,
                location_id=placement.location_id,
                position=placement.position,
                landmark_id=placement.landmark_id,
            )

        for item in self.items:
            await database.item.create_item(item, self.world.id)

        for placement in self.item_stack_placements:
            await database.item.create_stack(
                item_id=placement.item_id,
                stack=placement.stack,
                location_id=placement.location_id,
                position=placement.position,
                source_id=self.simulation.id,
                holder_id=placement.holder_id,
                owner_id=placement.owner_id,
            )

        for equipment in self.equipment:
            placement = next(p for p in self.equipment_placements if p.equipment_id == equipment.id)
            await database.equipment.create_equipment(
                equipment,
                source_id=self.simulation.id,
                location_id=placement.location_id,
                position=placement.position,
            )
            if placement.owner_id:
                await database.equipment.change_owner(equipment.id, placement.owner_id)
            if placement.holder_id:
                await database.equipment.change_hold_state(
                    equipment_id=equipment.id,
                    holder_id=placement.holder_id,
                    equipped=placement.equipped,
                    equipped_position=placement.equipped_position,
                )

        for placement in self.container_placements:
            for item_id in placement.unlocking_item_ids:
                await database.container.add_unlocking_item(item_id, placement.container_id)

        for event in self.events:
            await database.event.create_event(event, turn_ids=[self.initial_turn.id])
        for involvement in self.event_involvements:
            await database.event.add_character_involvement(
                event_id=involvement.event_id,
                character_id=involvement.character_id,
                involvement=involvement.involvement,
            )
        for memory_seed in self.memories:
            await database.memory.create_memory_atom(
                memory=memory_seed.memory,
                event_id=memory_seed.event_id,
                support_type=memory_seed.support_type,
                character_links=list(memory_seed.character_links),
            )
        for intent in self.intents:
            await database.intent.create_intent(
                intent=intent,
                character_id=self.intent_character_ids[intent.id],
            )


@pytest.fixture(scope="session")
def mock_author() -> Author:
    return Author(
        id="author_blackwater_fixture",
        name="Development Test Fixture",
        url="https://example.test/worlds/blackwater-observatory",
    )


@pytest.fixture(scope="session")
def mock_world() -> World:
    return World(
        id="world_blackwater_observatory",
        name="The Blackwater Observatory",
        description=(
            "The year is 1912. The isolated mountain town of Blackwater Ridge was built around an "
            "astronomical observatory that once conducted secret government-funded research.\n\n"
            "Three weeks ago, the observatory's director vanished. Officially, he left without notice. "
            "However, nobody believes that. The player arrives in town during the annual Founder's "
            "Festival, where tensions between residents are beginning to surface."
        ),
        starting_time=datetime(1912, 9, 21, 19, 30, tzinfo=UTC),
        version=1,
        url="https://example.test/worlds/blackwater-observatory",
        language=SupportedLanguage.ENGLISH,
    )


@pytest.fixture(scope="session")
def mock_simulation(mock_world: World) -> Simulation:
    return Simulation(
        id="simulation_blackwater_observatory",
        name=mock_world.name,
        description=mock_world.description,
        current_time=datetime(1912, 9, 21, 19, 30, tzinfo=UTC),
    )


@pytest.fixture(scope="session")
def mock_initial_turn() -> Turn:
    return Turn(
        id="turn_blackwater_opening",
        sequence=0,
        type=TurnType.SYSTEM_RESPONSE,
        content=(
            "Arthur Moore has arrived at the Iron Stag Inn during the Founder's Festival. Clara Whitlock "
            "is behind the bar, managing guests while quietly observing him."
        ),
        start_time=datetime(1912, 9, 21, 19, 30, tzinfo=UTC),
    )


@pytest.fixture(scope="session")
def mock_characters() -> tuple[Character, ...]:
    return (
        Character(
            id="character_eleanor_graves",
            name="Eleanor Graves",
            gender="female",
            age=42,
            description=(
                "Eleanor Graves is the mayor of Blackwater Ridge. She is calculating, practical, and deeply "
                "attached to her office. It is difficult to tell whether she acts out of civic duty or personal "
                "instinct, because the two have become almost indistinguishable. She is fiercely protective of "
                "the town's reputation and prefers to contain trouble before it becomes public."
            ),
            appearance=(
                "A composed woman with sharp features, tired eyes, and an immaculate posture. She usually "
                "carries herself with formal restraint."
            ),
            public_state=(
                "Welcoming Arthur Moore to Blackwater Ridge while presenting the town as orderly, festive, "
                "and untroubled by Director Harlan's disappearance."
            ),
            private_state=(
                "Trying to determine what Arthur Moore is actually here for and whether his presence threatens "
                "altered property records, the town's finances, or her own position."
            ),
            current_activity=CurrentActivity(name="managing festival appearances"),
        ),
        Character(
            id="character_marcus_reed",
            name="Marcus Reed",
            gender="male",
            age=35,
            description=(
                "Marcus Reed is the assistant at Blackwater Observatory. He is intelligent, technically capable, "
                "and deeply anxious. His obsession with strange underground signals has begun to affect his judgement."
            ),
            appearance=(
                "A thin, pale man with restless hands, ink-stained fingers, and dark circles under his eyes."
            ),
            public_state=(
                "Continuing limited observatory work while insisting that Director Harlan's disappearance must "
                "have a rational explanation."
            ),
            private_state=(
                "Desperate to recover Harlan's missing notebook before Eleanor, Arthur, or anyone else uses it "
                "to expose his unauthorized experiments."
            ),
            current_activity=CurrentActivity(name="checking observatory instruments"),
        ),
        Character(
            id="character_clara_whitlock",
            name="Clara Whitlock",
            gender="female",
            age=29,
            description=(
                "Clara Whitlock is the innkeeper of the Iron Stag Inn. She is friendly, socially perceptive, "
                "and outwardly cheerful, but much sharper than she first appears. She quietly keeps track of "
                "gossip, strange visitors, debts, arguments, and overheard remarks."
            ),
            appearance=(
                "A lively woman with attentive eyes, quick expressions, and a practiced welcoming smile."
            ),
            public_state=(
                "Running the Iron Stag Inn during the Founder's Festival, serving guests, listening to rumours, "
                "and presenting herself as merely curious about Arthur Moore's arrival."
            ),
            private_state=(
                "Trying to uncover the truth behind Director Harlan's disappearance, partly out of concern and "
                "partly because she believes the story could be valuable to a newspaper."
            ),
            current_activity=CurrentActivity(name="serving festival guests"),
        ),
        Character(
            id="character_arthur_moore",
            user_controlled=True,
            name="Arthur Moore",
            gender="male",
            age=37,
            description=(
                "Arthur Moore is an independent investigator. He is competent, observant, and experienced enough "
                "to read people without immediately showing his conclusions. His politeness conceals deep distrust."
            ),
            appearance=(
                "A neatly kept man with a reserved expression, watchful eyes, and the habit of pausing before he answers."
            ),
            public_state=(
                "Arriving in Blackwater Ridge during the Founder's Festival as an independent investigator."
            ),
            private_state=(
                "Investigating who anonymously hired him, why payment depends on obtaining evidence, and whether "
                "Harlan's disappearance is connected to the observatory, the old mine, or the town's leadership."
            ),
            current_activity=CurrentActivity(name="questioning Clara at the bar"),
        ),
    )


@pytest.fixture(scope="session")
def mock_character_placements() -> tuple[CharacterPlacement, ...]:
    return (
        CharacterPlacement("character_eleanor_graves", "location_iron_stag_bar", "near the mayoral party"),
        CharacterPlacement("character_marcus_reed", "location_observatory_directors_office", "reviewing papers"),
        CharacterPlacement("character_clara_whitlock", "location_iron_stag_bar", "behind the bar"),
        CharacterPlacement("character_arthur_moore", "location_iron_stag_bar", "at the bar"),
    )


@pytest.fixture(scope="session")
def mock_background_characters() -> tuple[BackgroundCharacter, ...]:
    return (
        BackgroundCharacter(
            id="background_festival_guests",
            name="Festival Guests",
            description="A shifting crowd of locals and visitors drinking, laughing, and trading festival gossip.",
        ),
        BackgroundCharacter(
            id="background_town_clerks",
            name="Town Hall Clerks",
            description="Clerks who maintain municipal records and know when papers have been moved or replaced.",
        ),
    )


@pytest.fixture(scope="session")
def mock_background_character_placements() -> tuple[CharacterPlacement, ...]:
    return (
        CharacterPlacement("background_festival_guests", "location_iron_stag_bar", "throughout the common room"),
        CharacterPlacement("background_town_clerks", "location_town_hall_records_room", "between the shelves"),
    )


@pytest.fixture(scope="session")
def mock_locations() -> tuple[Location, ...]:
    return (
        Location(
            id="location_blackwater_ridge",
            name="Blackwater Ridge",
            description="An isolated mountain town built around an old observatory, silver mine, and annual festival.",
        ),
        Location(
            id="location_observatory_directors_office",
            name="Blackwater Observatory - Director's Office",
            description=(
                "The private office of the missing Director Harlan. Tall windows face the mountains, while shelves "
                "of astronomical records, correspondence, and field notes line the walls."
            ),
        ),
        Location(
            id="location_observatory_telescope_chamber",
            name="Blackwater Observatory - Telescope Chamber",
            description=(
                "The main chamber of the observatory, dominated by a large brass-and-steel telescope mounted beneath "
                "the rotating dome."
            ),
        ),
        Location(
            id="location_iron_stag_bar",
            name="Iron Stag Inn - Bar",
            description=(
                "The busy ground-floor bar of the Iron Stag Inn. Locals gather here for drink, gossip, and festival talk."
            ),
        ),
        Location(
            id="location_iron_stag_room_7",
            name="Iron Stag Inn - Room 7",
            description="A modest guest room on the upper floor with a writing desk and a window over the side alley.",
        ),
        Location(
            id="location_town_hall_mayors_office",
            name="Town Hall - Mayor's Office",
            description="Eleanor Graves's formal, controlled, carefully arranged office inside Town Hall.",
        ),
        Location(
            id="location_town_hall_records_room",
            name="Town Hall - Records Room",
            description="A cramped archival room filled with deeds, survey papers, council minutes, and tax records.",
        ),
        Location(
            id="location_town_square_festival_monument",
            name="Town Square - Festival Monument",
            description="The decorated centre of Blackwater Ridge, where a stone monument marks the town's founding.",
        ),
        Location(
            id="location_old_mine_entrance",
            name="Old Mine - Mine Entrance",
            description="The boarded entrance to the abandoned silver mine north of town.",
        ),
        Location(
            id="location_old_mine_main_tunnel",
            name="Old Mine - Main Tunnel",
            description="A dark, unstable tunnel where old rails run into darkness and sounds echo strangely.",
        ),
        Location(
            id="location_north_forest_abandoned_cabin",
            name="North Forest - Abandoned Cabin",
            description="A small hunter's cabin hidden among the trees north of town, dusty and damp with old ash.",
        ),
    )


@pytest.fixture(scope="session")
def mock_location_parents() -> dict[str, str | None]:
    return {
        "location_blackwater_ridge": None,
        "location_observatory_directors_office": "location_blackwater_ridge",
        "location_observatory_telescope_chamber": "location_blackwater_ridge",
        "location_iron_stag_bar": "location_blackwater_ridge",
        "location_iron_stag_room_7": "location_iron_stag_bar",
        "location_town_hall_mayors_office": "location_blackwater_ridge",
        "location_town_hall_records_room": "location_blackwater_ridge",
        "location_town_square_festival_monument": "location_blackwater_ridge",
        "location_old_mine_entrance": "location_blackwater_ridge",
        "location_old_mine_main_tunnel": "location_old_mine_entrance",
        "location_north_forest_abandoned_cabin": "location_blackwater_ridge",
    }


@pytest.fixture(scope="session")
def mock_landmarks_by_location() -> dict[str, tuple[Landmark, ...]]:
    return {
        "location_observatory_directors_office": (
            Landmark(
                id="landmark_directors_desk",
                name="Director's Desk",
                description="A heavy oak desk used by Director Harlan. Its surface is neat and its drawers are closed.",
            ),
        ),
        "location_observatory_telescope_chamber": (
            Landmark(
                id="landmark_main_telescope",
                name="Main Telescope",
                description="The observatory's primary telescope, functional but not set to its resting alignment.",
            ),
            Landmark(
                id="landmark_signal_recording_apparatus",
                name="Signal Recording Apparatus",
                description="Coils, receivers, and paper rolls used to record strange underground signal patterns.",
            ),
        ),
        "location_iron_stag_bar": (
            Landmark(
                id="landmark_visitors_room_ledger",
                name="Visitor's Room Ledger",
                description="The inn's ledger of room usage, dates, names, payments, and Clara's occasional notes.",
            ),
            Landmark(
                id="landmark_notice_board",
                name="Notice Board",
                description="A public board covered with festival announcements, missing notices, and local messages.",
            ),
        ),
        "location_iron_stag_room_7": (
            Landmark(
                id="landmark_room_7_writing_desk",
                name="Room 7 Writing Desk",
                description="A small writing desk with faint pressure marks on the surface.",
            ),
            Landmark(
                id="landmark_guest_room_window",
                name="Guest Room Window",
                description="A window overlooking the side alley. It is closed but not latched.",
            ),
        ),
        "location_town_hall_mayors_office": (
            Landmark(
                id="landmark_mayors_desk",
                name="Mayor's Desk",
                description="A polished desk containing official correspondence and festival planning papers.",
            ),
        ),
        "location_town_hall_records_room": (
            Landmark(
                id="landmark_property_record_shelves",
                name="Property Record Shelves",
                description="Shelves containing land records, including folders near the old mine area.",
            ),
        ),
        "location_town_square_festival_monument": (
            Landmark(
                id="landmark_festival_monument",
                name="Festival Monument",
                description="A commemorative stone monument with a founding plaque, decorated for the festival.",
            ),
            Landmark(
                id="landmark_festival_stalls",
                name="Festival Stalls",
                description="Temporary market stalls selling food, trinkets, and local crafts.",
            ),
        ),
        "location_old_mine_entrance": (
            Landmark(
                id="landmark_boarded_mine_entrance",
                name="Boarded Mine Entrance",
                description="The sealed entrance to the old silver mine where eleven workers died twenty years ago.",
            ),
            Landmark(
                id="landmark_old_warning_sign",
                name="Old Warning Sign",
                description="A weathered municipal warning sign declaring the mine unsafe and closed by town order.",
            ),
        ),
        "location_old_mine_main_tunnel": (
            Landmark(
                id="landmark_collapsed_side_passage",
                name="Collapsed Side Passage",
                description="A partially collapsed passage branching from the main tunnel.",
            ),
        ),
        "location_north_forest_abandoned_cabin": (
            Landmark(
                id="landmark_cabin_hearth",
                name="Cabin Hearth",
                description="A cold stone hearth filled with ash.",
            ),
            Landmark(
                id="landmark_loose_floorboard",
                name="Loose Floorboard",
                description="A warped floorboard near the cabin wall, slightly raised from the surrounding floor.",
            ),
        ),
    }


@pytest.fixture(scope="session")
def mock_containers() -> tuple[Container, ...]:
    return (
        Container(
            id="container_locked_filing_cabinet",
            name="Locked Filing Cabinet",
            description="A reinforced metal cabinet for observatory administrative records and research paperwork.",
            state=ContainerState.LOCKED,
        ),
        Container(
            id="container_municipal_lockbox",
            name="Municipal Lockbox",
            description="A compact iron lockbox for sensitive town documents and private administrative records.",
            state=ContainerState.LOCKED,
        ),
        Container(
            id="container_survey_archive_cabinet",
            name="Survey Archive Cabinet",
            description="A cabinet containing older surveyor records and historical mine documentation.",
            state=ContainerState.UNLOCKED,
        ),
        Container(
            id="container_rusting_mine_cart",
            name="Rusting Mine Cart",
            description="An old ore cart on warped rails, half-filled with stone fragments and rotting wood.",
            state=ContainerState.OPEN,
        ),
    )


@pytest.fixture(scope="session")
def mock_container_placements() -> tuple[ContainerPlacement, ...]:
    return (
        ContainerPlacement("container_locked_filing_cabinet", "location_observatory_directors_office"),
        ContainerPlacement("container_municipal_lockbox", "location_town_hall_mayors_office"),
        ContainerPlacement("container_survey_archive_cabinet", "location_town_hall_records_room"),
        ContainerPlacement("container_rusting_mine_cart", "location_old_mine_main_tunnel"),
    )


@pytest.fixture(scope="session")
def mock_items() -> tuple[Item, ...]:
    return (
        Item(
            id="item_harlans_notebook",
            name="Harlan's Notebook",
            description=(
                "Director Harlan's missing notebook, containing research notes, rough mine sketches, observatory "
                "calculations, and several encoded entries."
            ),
            unique=True,
        ),
        Item(
            id="item_brass_laboratory_key",
            name="Brass Laboratory Key",
            description="A small brass key that opens the locked laboratory in Blackwater Observatory.",
            unique=True,
        ),
        Item(
            id="item_silver_pocket_watch",
            name="Silver Pocket Watch",
            description="Director Harlan's silver pocket watch. It stopped at 11:17 PM.",
            unique=True,
        ),
        Item(
            id="item_unknown_visitors_note_fragment",
            name="Unknown Visitor's Note Fragment",
            description="A torn paper fragment connected to the unknown visitor who rented Room 7.",
            unique=True,
        ),
        Item(
            id="item_surveyors_map",
            name="Surveyor's Map",
            description="An old surveyor's map showing a tunnel not present on official town records.",
            unique=True,
        ),
        Item(
            id="item_mayors_administrative_seal",
            name="Mayor's Administrative Seal",
            description="Eleanor Graves's official municipal seal, used to authenticate town documents.",
            unique=True,
        ),
        Item(
            id="item_signal_recording_strip",
            name="Signal Recording Strip",
            description="A paper strip marked with irregular signal patterns detected beneath Blackwater Ridge.",
            unique=True,
        ),
        Item(
            id="item_marcus_calibration_notes",
            name="Marcus's Calibration Notes",
            description="Marcus Reed's notes on telescope alignment and unauthorized signal experiments.",
            unique=True,
        ),
        Item(
            id="item_claras_gossip_notebook",
            name="Clara's Gossip Notebook",
            description="Clara Whitlock's private notebook of rumours, guest observations, and overheard conversations.",
            unique=True,
        ),
        Item(
            id="item_room_7_cash_receipt",
            name="Room 7 Cash Receipt",
            description="A receipt for the unknown visitor's payment for Room 7. The name is believed to be false.",
            unique=True,
        ),
        Item(
            id="item_anonymous_letter",
            name="Anonymous Letter",
            description=(
                "The letter that brought Arthur Moore to Blackwater Ridge, requesting an investigation into "
                "Director Harlan's disappearance."
            ),
            unique=True,
        ),
        Item(
            id="item_investigators_notebook",
            name="Investigator's Notebook",
            description="Arthur Moore's notebook for case notes, witness statements, deductions, and timelines.",
            unique=True,
        ),
    )


@pytest.fixture(scope="session")
def mock_item_stack_placements() -> tuple[ItemStackPlacement, ...]:
    return (
        ItemStackPlacement(
            item_id="item_harlans_notebook",
            stack=ItemStack(id="stack_harlans_notebook", quantity=1),
            location_id="location_old_mine_main_tunnel",
            position="not immediately visible",
        ),
        ItemStackPlacement(
            item_id="item_brass_laboratory_key",
            stack=ItemStack(id="stack_brass_laboratory_key", quantity=1),
            location_id="location_town_square_festival_monument",
            position="hidden behind the monument plaque",
        ),
        ItemStackPlacement(
            item_id="item_silver_pocket_watch",
            stack=ItemStack(id="stack_silver_pocket_watch", quantity=1, quality="damaged"),
            location_id="location_observatory_directors_office",
        ),
        ItemStackPlacement(
            item_id="item_unknown_visitors_note_fragment",
            stack=ItemStack(id="stack_unknown_visitors_note_fragment", quantity=1, quality="torn"),
            location_id="location_iron_stag_room_7",
            position="inside the desk drawer",
        ),
        ItemStackPlacement(
            item_id="item_surveyors_map",
            stack=ItemStack(id="stack_surveyors_map", quantity=1, quality="aged"),
            holder_id="character_eleanor_graves",
            owner_id="character_eleanor_graves",
        ),
        ItemStackPlacement(
            item_id="item_mayors_administrative_seal",
            stack=ItemStack(id="stack_mayors_administrative_seal", quantity=1),
            holder_id="character_eleanor_graves",
            owner_id="character_eleanor_graves",
        ),
        ItemStackPlacement(
            item_id="item_signal_recording_strip",
            stack=ItemStack(id="stack_signal_recording_strip", quantity=1),
            holder_id="character_marcus_reed",
            owner_id="character_marcus_reed",
        ),
        ItemStackPlacement(
            item_id="item_marcus_calibration_notes",
            stack=ItemStack(id="stack_marcus_calibration_notes", quantity=1),
            holder_id="character_marcus_reed",
            owner_id="character_marcus_reed",
        ),
        ItemStackPlacement(
            item_id="item_claras_gossip_notebook",
            stack=ItemStack(id="stack_claras_gossip_notebook", quantity=1),
            holder_id="character_clara_whitlock",
            owner_id="character_clara_whitlock",
        ),
        ItemStackPlacement(
            item_id="item_room_7_cash_receipt",
            stack=ItemStack(id="stack_room_7_cash_receipt", quantity=1),
            holder_id="character_clara_whitlock",
            owner_id="character_clara_whitlock",
        ),
        ItemStackPlacement(
            item_id="item_anonymous_letter",
            stack=ItemStack(id="stack_anonymous_letter", quantity=1),
            holder_id="character_arthur_moore",
            owner_id="character_arthur_moore",
        ),
        ItemStackPlacement(
            item_id="item_investigators_notebook",
            stack=ItemStack(id="stack_investigators_notebook", quantity=1),
            holder_id="character_arthur_moore",
            owner_id="character_arthur_moore",
        ),
    )


@pytest.fixture(scope="session")
def mock_equipment() -> tuple[Equipment, ...]:
    return (
        Equipment(
            id="equipment_pocket_revolver",
            name="Pocket Revolver",
            description="Arthur Moore's compact personal revolver, carried for protection rather than intimidation.",
        ),
        Equipment(
            id="equipment_investigators_coat",
            name="Investigator's Coat",
            description="A practical dark travelling coat with deep pockets for papers, tools, and evidence.",
        ),
    )


@pytest.fixture(scope="session")
def mock_equipment_placements() -> tuple[EquipmentPlacement, ...]:
    return (
        EquipmentPlacement(
            equipment_id="equipment_pocket_revolver",
            holder_id="character_arthur_moore",
            owner_id="character_arthur_moore",
            equipped=True,
            equipped_position="inside coat pocket",
        ),
        EquipmentPlacement(
            equipment_id="equipment_investigators_coat",
            holder_id="character_arthur_moore",
            owner_id="character_arthur_moore",
            equipped=True,
            equipped_position="torso",
        ),
    )


@pytest.fixture(scope="session")
def mock_events() -> tuple[Event, ...]:
    return (
        Event(
            id="event_harlan_disappearance",
            name="Director Harlan disappeared",
            summary=(
                "Director Harlan disappeared three weeks before the Founder's Festival. Officially he left without "
                "notice, but many residents doubt this."
            ),
        ),
        Event(
            id="event_arthur_arrival",
            name="Arthur arrived at the Iron Stag Inn",
            summary=(
                "Arthur Moore arrived at the Iron Stag Inn during the Founder's Festival and began asking careful "
                "questions about Harlan's disappearance."
            ),
        ),
    )


@pytest.fixture(scope="session")
def mock_event_involvements() -> tuple[EventInvolvementSeed, ...]:
    return (
        EventInvolvementSeed("event_harlan_disappearance", "character_eleanor_graves", EventInvolvement.SUSPECT),
        EventInvolvementSeed("event_harlan_disappearance", "character_marcus_reed", EventInvolvement.BELIEVE),
        EventInvolvementSeed("event_harlan_disappearance", "character_clara_whitlock", EventInvolvement.HEAR),
        EventInvolvementSeed("event_arthur_arrival", "character_arthur_moore", EventInvolvement.PARTICIPATE),
        EventInvolvementSeed("event_arthur_arrival", "character_clara_whitlock", EventInvolvement.WITNESS),
        EventInvolvementSeed("event_arthur_arrival", "character_eleanor_graves", EventInvolvement.WITNESS),
    )


@pytest.fixture(scope="session")
def mock_memories() -> tuple[MemorySeed, ...]:
    return (
        MemorySeed(
            memory=MemoryAtom(
                id="memory_disappearance_threads",
                summary=(
                    "The observatory, old mine, altered property records, unknown visitor, and Harlan's missing "
                    "notebook are unresolved investigation threads."
                ),
                keywords=[
                    "Director Harlan",
                    "old mine",
                    "property records",
                    "unknown visitor",
                    "missing notebook",
                ],
                embedding=None,
            ),
            event_id="event_harlan_disappearance",
            support_type=MemorySupportType.REPORTED,
            character_links=(
                CharacterMemoryLink(
                    character_id="character_arthur_moore",
                    confidence=0.9,
                    salience=Salience.CRITICAL,
                    behavioural_relevance="Use these as active investigative leads.",
                    stance=MemoryStance.BELIEVE,
                ),
                CharacterMemoryLink(
                    character_id="character_clara_whitlock",
                    confidence=0.75,
                    salience=Salience.HIGH,
                    behavioural_relevance="Watch for links between visitors, gossip, and Harlan.",
                    stance=MemoryStance.SUSPECT if hasattr(MemoryStance, "SUSPECT") else MemoryStance.BELIEVE,
                ),
            ),
        ),
        MemorySeed(
            memory=MemoryAtom(
                id="memory_arthur_has_not_revealed_letter",
                summary="Arthur has not yet revealed the anonymous letter that brought him to Blackwater Ridge.",
                keywords=["Arthur Moore", "anonymous letter", "unrevealed evidence"],
                embedding=None,
            ),
            event_id="event_arthur_arrival",
            support_type=MemorySupportType.DIRECT,
            character_links=(
                CharacterMemoryLink(
                    character_id="character_arthur_moore",
                    confidence=1.0,
                    salience=Salience.HIGH,
                    behavioural_relevance="Avoid casually disclosing the letter unless it serves the investigation.",
                    stance=MemoryStance.REMEMBER,
                ),
            ),
        ),
    )


@pytest.fixture(scope="session")
def mock_intents() -> tuple[Intent, ...]:
    return (
        Intent(
            id="intent_arthur_investigate_harlan",
            type=IntentType.QUEST,
            name="Investigate Harlan's disappearance",
            description="Determine what happened to Director Harlan and who anonymously hired Arthur.",
            keywords=["Harlan", "anonymous letter", "evidence"],
            priority=0.9,
            urgency=0.7,
            status=IntentStatus.ACTIVE,
            horizon=IntentHorizon.SHORT,
            current_plan=[
                "Question Clara about Room 7",
                "Learn who rented the room before Harlan vanished",
                "Avoid revealing the anonymous letter too early",
            ],
            open_threads=[
                "Who hired Arthur?",
                "What happened to Harlan?",
                "How are the observatory and old mine connected?",
            ],
        ),
        Intent(
            id="intent_clara_uncover_truth",
            type=IntentType.AGENDA,
            name="Uncover the truth behind Harlan's disappearance",
            description="Use inn gossip and guest records to learn what officials are hiding.",
            keywords=["Room 7", "gossip", "visitor ledger"],
            priority=0.7,
            urgency=0.5,
            status=IntentStatus.ACTIVE,
            horizon=IntentHorizon.SHORT,
            current_plan=["Watch Arthur", "Check the Visitor's Room Ledger", "Compare rumours"],
        ),
        Intent(
            id="intent_marcus_recover_notebook",
            type=IntentType.NEED,
            name="Recover Harlan's missing notebook",
            description="Find Harlan's notebook before it exposes Marcus's unauthorized signal experiments.",
            keywords=["Harlan's Notebook", "signal experiments", "observatory"],
            priority=0.85,
            urgency=0.8,
            status=IntentStatus.ACTIVE,
            horizon=IntentHorizon.IMMEDIATE,
            blockers=["Arthur's investigation", "Eleanor's scrutiny"],
        ),
        Intent(
            id="intent_eleanor_contain_scandal",
            type=IntentType.AGENDA,
            name="Contain public scandal",
            description="Protect the town's reputation and prevent dangerous property-record details from surfacing.",
            keywords=["town reputation", "property records", "festival"],
            priority=0.8,
            urgency=0.6,
            status=IntentStatus.ACTIVE,
            horizon=IntentHorizon.SHORT,
            constraints=["Avoid direct lies when possible", "Keep festival order intact"],
        ),
    )


@pytest.fixture(scope="session")
def mock_intent_character_ids() -> dict[str, str]:
    return {
        "intent_arthur_investigate_harlan": "character_arthur_moore",
        "intent_clara_uncover_truth": "character_clara_whitlock",
        "intent_marcus_recover_notebook": "character_marcus_reed",
        "intent_eleanor_contain_scandal": "character_eleanor_graves",
    }


@pytest.fixture(scope="session")
def mock_graph_world_setup(
    mock_author: Author,
    mock_world: World,
    mock_simulation: Simulation,
    mock_initial_turn: Turn,
    mock_locations: tuple[Location, ...],
    mock_location_parents: dict[str, str | None],
    mock_landmarks_by_location: dict[str, tuple[Landmark, ...]],
    mock_containers: tuple[Container, ...],
    mock_container_placements: tuple[ContainerPlacement, ...],
    mock_characters: tuple[Character, ...],
    mock_background_characters: tuple[BackgroundCharacter, ...],
    mock_character_placements: tuple[CharacterPlacement, ...],
    mock_background_character_placements: tuple[CharacterPlacement, ...],
    mock_items: tuple[Item, ...],
    mock_item_stack_placements: tuple[ItemStackPlacement, ...],
    mock_equipment: tuple[Equipment, ...],
    mock_equipment_placements: tuple[EquipmentPlacement, ...],
    mock_events: tuple[Event, ...],
    mock_event_involvements: tuple[EventInvolvementSeed, ...],
    mock_memories: tuple[MemorySeed, ...],
    mock_intents: tuple[Intent, ...],
    mock_intent_character_ids: dict[str, str],
) -> GraphWorldSetup:
    return GraphWorldSetup(
        author=mock_author,
        world=mock_world,
        simulation=mock_simulation,
        initial_turn=mock_initial_turn,
        locations=mock_locations,
        location_parents=mock_location_parents,
        landmarks_by_location=mock_landmarks_by_location,
        containers=mock_containers,
        container_placements=mock_container_placements,
        characters=mock_characters,
        background_characters=mock_background_characters,
        character_placements=mock_character_placements,
        background_character_placements=mock_background_character_placements,
        items=mock_items,
        item_stack_placements=mock_item_stack_placements,
        equipment=mock_equipment,
        equipment_placements=mock_equipment_placements,
        events=mock_events,
        event_involvements=mock_event_involvements,
        memories=mock_memories,
        intents=mock_intents,
        intent_character_ids=mock_intent_character_ids,
        metadata={
            "source_branch": "main",
            "source_fixture": "tests/conftest.py development world setup",
            "converted_for": "graph-centric evaluation tests",
        },
    )
