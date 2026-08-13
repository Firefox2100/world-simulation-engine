from unittest.mock import AsyncMock, Mock, patch

from world_simulation_engine.component.sillytavern_converter import world_reconstructor as wr_module
from world_simulation_engine.component.sillytavern_converter import AssembledWorld, \
    BackgroundCharacterExtraction, CharacterExtraction, ConversionReport, EquipmentExtraction, \
    IntentExtraction, ItemExtraction, LocationExtraction, NarrativeExtraction, OpeningTurnExtraction, \
    PreprocessedCard, PrivateKnowledgeExtraction, SpatialStateExtraction, VariableSchemaExtraction, \
    WorldLoreExtraction
from world_simulation_engine.component.sillytavern_converter.lorebook_classifier import LorebookClassification
from world_simulation_engine.component.sillytavern_converter.world_reconstructor import WorldReconstructor
from world_simulation_engine.misc.enums import SupportedLanguage
from world_simulation_engine.model.silly_tavern import SillyTavernCardV3, SillyTavernCardV3Data


def make_card(name: str = "Card") -> SillyTavernCardV3:
    return SillyTavernCardV3(spec="chara_card_v3", spec_version="3.0", data=SillyTavernCardV3Data(name=name))


async def test_reconstruct_from_card_wires_every_stage_in_order_and_returns_the_assembled_world():
    card = make_card()
    preprocessed = PreprocessedCard(name="Card", first_message="Hi")
    classification = LorebookClassification(items=[])
    characters = CharacterExtraction(characters=[])
    background_characters = BackgroundCharacterExtraction(characters=[])
    locations = LocationExtraction(locations=[])
    world_lore = WorldLoreExtraction()
    narrative = NarrativeExtraction()
    intents = IntentExtraction()
    variables = VariableSchemaExtraction()
    items = ItemExtraction()
    equipment = EquipmentExtraction()
    opening_turns = OpeningTurnExtraction()
    spatial_state = SpatialStateExtraction()
    opening_narrative = NarrativeExtraction()
    private_knowledge = PrivateKnowledgeExtraction()
    assembled = AssembledWorld(world={"name": "Card"}, sections={}, report=ConversionReport())

    with patch.object(wr_module, "CardPreprocessor") as card_preprocessor_cls, \
            patch.object(wr_module, "LorebookClassifier") as classifier_cls, \
            patch.object(wr_module, "CharacterExtractor") as character_extractor_cls, \
            patch.object(wr_module, "BackgroundCharacterExtractor") as background_character_extractor_cls, \
            patch.object(wr_module, "LocationExtractor") as location_extractor_cls, \
            patch.object(wr_module, "WorldLoreExtractor") as world_lore_extractor_cls, \
            patch.object(wr_module, "NarrativeExtractor") as narrative_extractor_cls, \
            patch.object(wr_module, "IntentExtractor") as intent_extractor_cls, \
            patch.object(wr_module, "VariableSchemaExtractor") as variable_extractor_cls, \
            patch.object(wr_module, "ItemExtractor") as item_extractor_cls, \
            patch.object(wr_module, "EquipmentExtractor") as equipment_extractor_cls, \
            patch.object(wr_module, "OpeningTurnExtractor") as opening_turn_extractor_cls, \
            patch.object(wr_module, "SpatialStateExtractor") as spatial_state_extractor_cls, \
            patch.object(wr_module, "OpeningNarrativeExtractor") as opening_narrative_extractor_cls, \
            patch.object(wr_module, "PrivateKnowledgeExtractor") as private_knowledge_extractor_cls, \
            patch.object(wr_module, "WorldAssembler") as assembler_cls:

        card_preprocessor_cls.preprocess.return_value = preprocessed
        classifier_cls.return_value.classify = AsyncMock(return_value=classification)
        character_extractor_cls.return_value.extract = AsyncMock(return_value=characters)
        background_character_extractor_cls.return_value.extract = AsyncMock(return_value=background_characters)
        location_extractor_cls.return_value.extract = AsyncMock(return_value=locations)
        world_lore_extractor_cls.return_value.extract = AsyncMock(return_value=world_lore)
        narrative_extractor_cls.return_value.extract = AsyncMock(return_value=narrative)
        intent_extractor_cls.return_value.extract = AsyncMock(return_value=intents)
        variable_extractor_cls.return_value.extract = AsyncMock(return_value=variables)
        item_extractor_cls.return_value.extract = AsyncMock(return_value=items)
        equipment_extractor_cls.return_value.extract = AsyncMock(return_value=equipment)
        opening_turn_extractor_cls.return_value.extract = AsyncMock(return_value=opening_turns)
        spatial_state_extractor_cls.return_value.extract = AsyncMock(return_value=spatial_state)
        opening_narrative_extractor_cls.return_value.extract = AsyncMock(return_value=opening_narrative)
        private_knowledge_extractor_cls.return_value.extract = AsyncMock(return_value=private_knowledge)
        assembler_cls.return_value.assemble.return_value = assembled

        reconstructor = WorldReconstructor(database=Mock())
        result = await reconstructor.reconstruct_from_card(card, language=SupportedLanguage.ENGLISH)

        assert result is assembled
        card_preprocessor_cls.preprocess.assert_called_once_with(card)
        classifier_cls.return_value.classify.assert_awaited_once_with(
            preprocessed, language=SupportedLanguage.ENGLISH,
        )
        character_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, classification, language=SupportedLanguage.ENGLISH,
        )
        background_character_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, classification, characters, language=SupportedLanguage.ENGLISH,
        )
        location_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, classification, language=SupportedLanguage.ENGLISH,
        )
        world_lore_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, classification, language=SupportedLanguage.ENGLISH,
        )
        narrative_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, classification, characters, background_characters,
            language=SupportedLanguage.ENGLISH,
        )
        intent_extractor_cls.return_value.extract.assert_awaited_once_with(
            characters, narrative, language=SupportedLanguage.ENGLISH,
        )
        variable_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, classification, language=SupportedLanguage.ENGLISH,
        )
        item_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, classification, language=SupportedLanguage.ENGLISH,
        )
        equipment_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, classification, language=SupportedLanguage.ENGLISH,
        )
        opening_turn_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, characters, language=SupportedLanguage.ENGLISH,
        )
        spatial_state_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, characters, locations, items, equipment,
            language=SupportedLanguage.ENGLISH,
        )
        opening_narrative_extractor_cls.return_value.extract.assert_awaited_once_with(
            opening_turns, characters, background_characters, language=SupportedLanguage.ENGLISH,
        )
        private_knowledge_extractor_cls.return_value.extract.assert_awaited_once_with(
            characters, locations, items, equipment, narrative,
            language=SupportedLanguage.ENGLISH,
        )
        assembler_cls.return_value.assemble.assert_called_once_with(
            preprocessed,
            language=SupportedLanguage.ENGLISH,
            characters=characters,
            background_characters=background_characters,
            locations=locations,
            world_lore=world_lore,
            narrative=narrative,
            intents=intents,
            variables=variables,
            items=items,
            equipment=equipment,
            opening_turns=opening_turns,
            spatial_state=spatial_state,
            opening_narrative=opening_narrative,
            private_knowledge=private_knowledge,
        )


async def test_reconstruct_parses_bytes_then_delegates_to_reconstruct_from_card():
    card = make_card()
    assembled = AssembledWorld(world={"name": "Card"}, sections={}, report=ConversionReport())

    with patch.object(wr_module, "DataExtractor") as data_extractor_cls:
        data_extractor_cls.return_value.extract.return_value = Mock(card=card)

        reconstructor = WorldReconstructor(database=Mock())
        reconstructor.reconstruct_from_card = AsyncMock(return_value=assembled)

        result = await reconstructor.reconstruct(b"card-bytes", language=SupportedLanguage.ENGLISH)

        assert result is assembled
        data_extractor_cls.return_value.extract.assert_called_once_with(b"card-bytes")
        reconstructor.reconstruct_from_card.assert_awaited_once_with(card, language=SupportedLanguage.ENGLISH)
