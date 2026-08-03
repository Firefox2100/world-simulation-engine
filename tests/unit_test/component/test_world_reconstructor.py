from unittest.mock import AsyncMock, Mock, patch

from world_simulation_engine.component.sillytavern_converter import world_reconstructor as wr_module
from world_simulation_engine.component.sillytavern_converter import AssembledWorld, CharacterExtraction, \
    ConversionReport, IntentExtraction, LocationExtraction, NarrativeExtraction, PreprocessedCard, \
    VariableSchemaExtraction, WorldLoreExtraction
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
    locations = LocationExtraction(locations=[])
    world_lore = WorldLoreExtraction()
    narrative = NarrativeExtraction()
    intents = IntentExtraction()
    variables = VariableSchemaExtraction()
    assembled = AssembledWorld(world={"name": "Card"}, sections={}, report=ConversionReport())

    with patch.object(wr_module, "CardPreprocessor") as card_preprocessor_cls, \
            patch.object(wr_module, "LorebookClassifier") as classifier_cls, \
            patch.object(wr_module, "CharacterExtractor") as character_extractor_cls, \
            patch.object(wr_module, "LocationExtractor") as location_extractor_cls, \
            patch.object(wr_module, "WorldLoreExtractor") as world_lore_extractor_cls, \
            patch.object(wr_module, "NarrativeExtractor") as narrative_extractor_cls, \
            patch.object(wr_module, "IntentExtractor") as intent_extractor_cls, \
            patch.object(wr_module, "VariableSchemaExtractor") as variable_extractor_cls, \
            patch.object(wr_module, "WorldAssembler") as assembler_cls:

        card_preprocessor_cls.preprocess.return_value = preprocessed
        classifier_cls.return_value.classify = AsyncMock(return_value=classification)
        character_extractor_cls.return_value.extract = AsyncMock(return_value=characters)
        location_extractor_cls.return_value.extract = AsyncMock(return_value=locations)
        world_lore_extractor_cls.return_value.extract = AsyncMock(return_value=world_lore)
        narrative_extractor_cls.return_value.extract = AsyncMock(return_value=narrative)
        intent_extractor_cls.return_value.extract = AsyncMock(return_value=intents)
        variable_extractor_cls.return_value.extract = AsyncMock(return_value=variables)
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
        location_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, classification, language=SupportedLanguage.ENGLISH,
        )
        world_lore_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, classification, language=SupportedLanguage.ENGLISH,
        )
        narrative_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, classification, characters, language=SupportedLanguage.ENGLISH,
        )
        intent_extractor_cls.return_value.extract.assert_awaited_once_with(
            characters, language=SupportedLanguage.ENGLISH,
        )
        variable_extractor_cls.return_value.extract.assert_awaited_once_with(
            preprocessed, classification, language=SupportedLanguage.ENGLISH,
        )
        assembler_cls.return_value.assemble.assert_called_once_with(
            preprocessed,
            language=SupportedLanguage.ENGLISH,
            characters=characters,
            locations=locations,
            world_lore=world_lore,
            narrative=narrative,
            intents=intents,
            variables=variables,
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
