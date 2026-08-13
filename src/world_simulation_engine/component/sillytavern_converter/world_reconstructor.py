"""Top-level orchestrator for the SillyTavern import pipeline - mirrors `WorldSimulator`'s role as
the owner of the LangGraph `StateGraph` that wires every stage together end to end (§5).

Stages run strictly sequentially (§3.5/§9.6): stage 0 (`CardPreprocessor`) and stage 3
(`WorldAssembler`) are deterministic single nodes, stage 1 (`LorebookClassifier`) and every
stage-2 extractor are themselves internally fanned-out (`fan_out.run_fan_out`, capped by
`CONFIG.sillytavern_import_max_concurrency`) but run one stage after another here, never
concurrently with each other - later stages depend on earlier ones (`NarrativeExtractor`/
`IntentExtractor` need `CharacterExtractor`'s roster, while opening/spatial extraction needs the
assembled entity rosters) and a 50-entry card would otherwise fire
hundreds of simultaneous requests across stages at once.

`language` is supplied by the caller for the whole run (never guessed or auto-detected) - the
same language selects the correct prompt set for every stage and, per the user's intent, leaves
room for a future language-tuned model to be configured per component without any change here.

Two public entry points share the same graph: `reconstruct(card_bytes, ...)` for a raw upload, and
`reconstruct_from_card(card, ...)` for an already-parsed (and possibly user-edited)
`SillyTavernCardV3` - the router's review/edit workflow uses the latter, since the user reviews and
edits the card's *raw parsed fields* (via a separate `/parse` endpoint, no LLM involved) before this
pipeline ever runs on it, rather than re-uploading the original file.
"""

from pydantic import BaseModel, ConfigDict

from langgraph.constants import END, START
from langgraph.graph.state import CompiledStateGraph, StateGraph

from world_simulation_engine.misc.config import CONFIG
from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model.silly_tavern import SillyTavernCardV3

from .background_character_extractor import BackgroundCharacterExtraction, BackgroundCharacterExtractor
from .card_preprocessor import CardPreprocessor, PreprocessedCard
from .character_extractor import CharacterExtraction, CharacterExtractor
from .data_extractor import DataExtractor
from .equipment_extractor import EquipmentExtraction, EquipmentExtractor
from .intent_extractor import IntentExtraction, IntentExtractor
from .item_extractor import ItemExtraction, ItemExtractor
from .location_extractor import LocationExtraction, LocationExtractor
from .lorebook_classifier import LorebookClassification, LorebookClassifier
from .narrative_extractor import NarrativeExtraction, NarrativeExtractor
from .opening_turn_extractor import OpeningTurnExtraction, OpeningTurnExtractor
from .opening_narrative_extractor import OpeningNarrativeExtractor
from .private_knowledge_extractor import PrivateKnowledgeExtraction, PrivateKnowledgeExtractor
from .spatial_state_extractor import SpatialStateExtraction, SpatialStateExtractor
from .variable_schema_extractor import VariableSchemaExtraction, VariableSchemaExtractor
from .world_assembler import AssembledWorld, WorldAssembler
from .world_lore_extractor import WorldLoreExtraction, WorldLoreExtractor


class _ReconstructionState(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    card: SillyTavernCardV3
    language: SupportedLanguage

    preprocessed: PreprocessedCard | None = None
    classification: LorebookClassification | None = None
    characters: CharacterExtraction | None = None
    background_characters: BackgroundCharacterExtraction | None = None
    locations: LocationExtraction | None = None
    world_lore: WorldLoreExtraction | None = None
    narrative: NarrativeExtraction | None = None
    intents: IntentExtraction | None = None
    variables: VariableSchemaExtraction | None = None
    items: ItemExtraction | None = None
    equipment: EquipmentExtraction | None = None
    opening_turns: OpeningTurnExtraction | None = None
    spatial_state: SpatialStateExtraction | None = None
    private_knowledge: PrivateKnowledgeExtraction | None = None
    opening_narrative: NarrativeExtraction | None = None
    assembled: AssembledWorld | None = None


class WorldReconstructor:
    def __init__(self, database):
        self._db = database
        self._graph = self._build_graph()

    def _build_graph(self) -> CompiledStateGraph:
        graph = StateGraph(_ReconstructionState)
        graph.add_node("preprocess", self._preprocess)
        graph.add_node("classify", self._classify)
        graph.add_node("extract_characters", self._extract_characters)
        graph.add_node("extract_background_characters", self._extract_background_characters)
        graph.add_node("extract_locations", self._extract_locations)
        graph.add_node("extract_world_lore", self._extract_world_lore)
        graph.add_node("extract_narrative", self._extract_narrative)
        graph.add_node("extract_intents", self._extract_intents)
        graph.add_node("extract_variables", self._extract_variables)
        graph.add_node("extract_items", self._extract_items)
        graph.add_node("extract_equipment", self._extract_equipment)
        graph.add_node("extract_opening_turns", self._extract_opening_turns)
        graph.add_node("extract_spatial_state", self._extract_spatial_state)
        graph.add_node("extract_private_knowledge", self._extract_private_knowledge)
        graph.add_node("extract_opening_narrative", self._extract_opening_narrative)
        graph.add_node("assemble", self._assemble)

        graph.add_edge(START, "preprocess")
        graph.add_edge("preprocess", "classify")
        graph.add_edge("classify", "extract_characters")
        graph.add_edge("extract_characters", "extract_background_characters")
        graph.add_edge("extract_background_characters", "extract_locations")
        graph.add_edge("extract_locations", "extract_world_lore")
        graph.add_edge("extract_world_lore", "extract_narrative")
        graph.add_edge("extract_narrative", "extract_intents")
        graph.add_edge("extract_intents", "extract_variables")
        graph.add_edge("extract_variables", "extract_items")
        graph.add_edge("extract_items", "extract_equipment")
        graph.add_edge("extract_equipment", "extract_opening_turns")
        graph.add_edge("extract_opening_turns", "extract_spatial_state")
        graph.add_edge("extract_spatial_state", "extract_opening_narrative")
        graph.add_edge("extract_opening_narrative", "extract_private_knowledge")
        graph.add_edge("extract_private_knowledge", "assemble")
        graph.add_edge("assemble", END)
        return graph.compile()

    @staticmethod
    def _preprocess(state: _ReconstructionState) -> dict:
        return {"preprocessed": CardPreprocessor.preprocess(state.card)}

    async def _classify(self, state: _ReconstructionState) -> dict:
        classification = await LorebookClassifier(database=self._db).classify(
            state.preprocessed, language=state.language,
        )
        return {"classification": classification}

    async def _extract_characters(self, state: _ReconstructionState) -> dict:
        characters = await CharacterExtractor(database=self._db).extract(
            state.preprocessed, state.classification, language=state.language,
        )
        return {"characters": characters}

    async def _extract_background_characters(self, state: _ReconstructionState) -> dict:
        background_characters = await BackgroundCharacterExtractor(database=self._db).extract(
            state.preprocessed, state.classification, state.characters, language=state.language,
        )
        return {"background_characters": background_characters}

    async def _extract_locations(self, state: _ReconstructionState) -> dict:
        locations = await LocationExtractor(database=self._db).extract(
            state.preprocessed, state.classification, language=state.language,
        )
        return {"locations": locations}

    async def _extract_world_lore(self, state: _ReconstructionState) -> dict:
        world_lore = await WorldLoreExtractor(database=self._db).extract(
            state.preprocessed, state.classification, language=state.language,
        )
        return {"world_lore": world_lore}

    async def _extract_narrative(self, state: _ReconstructionState) -> dict:
        narrative = await NarrativeExtractor(database=self._db).extract(
            state.preprocessed, state.classification, state.characters,
            state.background_characters, language=state.language,
        )
        return {"narrative": narrative}

    async def _extract_intents(self, state: _ReconstructionState) -> dict:
        intents = await IntentExtractor(database=self._db).extract(
            state.characters, state.narrative, language=state.language,
        )
        return {"intents": intents}

    async def _extract_variables(self, state: _ReconstructionState) -> dict:
        variables = await VariableSchemaExtractor(database=self._db).extract(
            state.preprocessed, state.classification, language=state.language,
        )
        return {"variables": variables}

    async def _extract_items(self, state: _ReconstructionState) -> dict:
        items = await ItemExtractor(database=self._db).extract(
            state.preprocessed, state.classification, language=state.language,
        )
        return {"items": items}

    async def _extract_equipment(self, state: _ReconstructionState) -> dict:
        equipment = await EquipmentExtractor(database=self._db).extract(
            state.preprocessed, state.classification, language=state.language,
        )
        return {"equipment": equipment}

    async def _extract_opening_turns(self, state: _ReconstructionState) -> dict:
        opening_turns = await OpeningTurnExtractor(database=self._db).extract(
            state.preprocessed, state.characters, language=state.language,
        )
        return {"opening_turns": opening_turns}

    async def _extract_spatial_state(self, state: _ReconstructionState) -> dict:
        spatial_state = await SpatialStateExtractor(database=self._db).extract(
            state.preprocessed, state.characters, state.locations, state.items, state.equipment,
            language=state.language,
        )
        return {"spatial_state": spatial_state}

    async def _extract_private_knowledge(self, state: _ReconstructionState) -> dict:
        narrative = self._combined_narrative(state)
        private_knowledge = await PrivateKnowledgeExtractor(database=self._db).extract(
            state.characters, state.locations, state.items, state.equipment, narrative,
            language=state.language,
        )
        return {"private_knowledge": private_knowledge}

    async def _extract_opening_narrative(self, state: _ReconstructionState) -> dict:
        opening_narrative = await OpeningNarrativeExtractor(database=self._db).extract(
            state.opening_turns, state.characters, state.background_characters,
            language=state.language,
        )
        return {"opening_narrative": opening_narrative}

    @staticmethod
    def _combined_narrative(state: _ReconstructionState) -> NarrativeExtraction:
        opening = state.opening_narrative or NarrativeExtraction()
        return NarrativeExtraction(
            events=[*state.narrative.events, *opening.events],
            memories=[*state.narrative.memories, *opening.memories],
            relationships=[*state.narrative.relationships, *opening.relationships],
        )

    @staticmethod
    def _assemble(state: _ReconstructionState) -> dict:
        assembled = WorldAssembler().assemble(
            state.preprocessed,
            language=state.language,
            characters=state.characters,
            background_characters=state.background_characters,
            locations=state.locations,
            world_lore=state.world_lore,
            narrative=state.narrative,
            intents=state.intents,
            variables=state.variables,
            items=state.items,
            equipment=state.equipment,
            opening_turns=state.opening_turns,
            spatial_state=state.spatial_state,
            private_knowledge=state.private_knowledge,
            opening_narrative=state.opening_narrative,
        )
        return {"assembled": assembled}

    async def reconstruct(
            self, card_bytes: bytes, *, language: SupportedLanguage,
    ) -> AssembledWorld:
        """Convenience entry point for a raw card upload - parses it, then delegates to
        `reconstruct_from_card`. No current router endpoint uses this path (the review/edit
        workflow always goes through `reconstruct_from_card` with a user-edited card), but it stays
        as a small, genuinely reusable capability rather than being merged away."""
        card = DataExtractor().extract(card_bytes).card
        return await self.reconstruct_from_card(card, language=language)

    async def reconstruct_from_card(
            self, card: SillyTavernCardV3, *, language: SupportedLanguage,
    ) -> AssembledWorld:
        final_state = await self._graph.ainvoke(
            _ReconstructionState(card=card, language=language),
            config={
                "max_concurrency": CONFIG.sillytavern_import_max_concurrency,
                "run_name": "world_reconstructor.reconstruct",
            },
        )
        if isinstance(final_state, dict):
            return final_state["assembled"]
        return final_state.assembled
